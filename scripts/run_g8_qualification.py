"""Run the prospectively frozen Genesis G8 distillation qualification.

Two arms receive the same fresh tasks and evaluator:
- external baseline: one Claude Code invocation per task, read-only, no evaluator access;
- local specialist: deterministic candidate generation from the frozen distilled artifact.

Project accounting follows A6b: one non-interactive fallback session counts as one
external model call even if the provider internally performs multiple turns.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping

from genesis import patch_templates
from genesis.learning import distillation
from genesis.trust_root import digest_of

RESULT_SCHEMA = "genesis-g8-qualification-result-v1"
CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "edits": {
            "type": "array",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old": {"type": "string"},
                    "new": {"type": "string"},
                },
                "required": ["path", "old", "new"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "edits"],
    "additionalProperties": False,
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _single_changed_line(original: str, candidate: str, expected_new: str) -> bool:
    before = original.splitlines()
    after = candidate.splitlines()
    if len(before) != len(after):
        return False
    changed = [i for i, (left, right) in enumerate(zip(before, after)) if left != right]
    if len(changed) != 1:
        return False
    index = changed[0]
    return patch_templates.tokenize(after[index].strip()) == patch_templates.tokenize(
        expected_new.strip()
    )


def _run_program(kind: str, path: Path) -> dict[str, Any]:
    if kind == "python_exit_zero":
        argv = ["python3", str(path)]
    elif kind == "node_exit_zero":
        argv = ["node", str(path)]
    elif kind == "static_exact_replacement":
        return {"passed": True, "argv": None, "returncode": 0, "stdout": "", "stderr": ""}
    else:
        raise RuntimeError(f"unknown G8 runtime kind {kind!r}")
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=20,
        check=False,
    )
    return {
        "passed": completed.returncode == 0,
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout[-800:],
        "stderr": completed.stderr[-800:],
        "wall_time_seconds": round(time.monotonic() - started, 6),
    }


def evaluate_source(case: Mapping[str, Any], candidate_source: str) -> dict[str, Any]:
    original = str(case["source_utf8"])
    replacement = dict(case["allowed_replacement"])
    old = str(replacement["old"])
    expected_new = str(replacement["new"])
    if original.count(old) != 1:
        raise RuntimeError("frozen G8 task old line is not unique")
    expected_source = original.replace(old, expected_new, 1)

    local_change = _single_changed_line(original, candidate_source, expected_new)
    protected = case.get("runtime", {}).get("protected_substring")
    protected_ok = True if not protected else str(protected) in candidate_source

    with tempfile.TemporaryDirectory(prefix="genesis-g8-eval-") as tmp:
        target = Path(tmp) / str(case["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(candidate_source, encoding="utf-8")
        runtime = _run_program(str(case["runtime"]["kind"]), target)

    # exact_source is diagnostic only; token-equivalent whitespace remains admissible.
    passed = local_change and protected_ok and runtime["passed"]
    return {
        "passed": passed,
        "single_changed_line": local_change,
        "protected_invariant": protected_ok,
        "runtime": runtime,
        "exact_expected_source": candidate_source == expected_source,
    }


def _apply_structured_edits(
    case: Mapping[str, Any],
    structured: Mapping[str, Any],
) -> tuple[str | None, str | None]:
    source = str(case["source_utf8"])
    target_path = Path(str(case["path"])).as_posix()
    edits = structured.get("edits")
    if not isinstance(edits, list) or not edits:
        return None, "no structured edits"
    current = source
    for edit in edits:
        if not isinstance(edit, Mapping):
            return None, "edit is not a mapping"
        supplied = Path(str(edit.get("path") or "")).as_posix()
        if supplied != target_path:
            return None, "edit targets a file outside the frozen task"
        old = str(edit.get("old") or "")
        new = str(edit.get("new") or "")
        if not old or current.count(old) != 1:
            return None, "edit old text is not unique"
        current = current.replace(old, new, 1)
    return current, None


def _claude_prompt(case: Mapping[str, Any]) -> str:
    return (
        "You are the single frozen external repair proposer for a Genesis G8 qualification.\n\n"
        f"Target file: {case['path']}\n"
        f"Public task contract:\n{case['public_contract']}\n\n"
        "Inspect only the current workspace and return the smallest source-only repair. "
        "Do not run tests or commands. Do not use the web. Do not modify files. "
        "Preserve unrelated source. Return only structured output matching the supplied schema."
    )


def run_external_baseline(
    case: Mapping[str, Any],
    *,
    model: str,
    max_budget_usd: float,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="genesis-g8-claude-") as tmp:
        root = Path(tmp)
        target = root / str(case["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(case["source_utf8"]), encoding="utf-8")

        argv = [
            "claude",
            "-p",
            _claude_prompt(case),
            "--output-format",
            "json",
            "--json-schema",
            json.dumps(CLAUDE_SCHEMA, sort_keys=True, separators=(",", ":")),
            "--model",
            model,
            "--tools",
            "Read,Glob,Grep",
            "--permission-mode",
            "dontAsk",
            "--permission-prompts",
            "none",
            "--restricted",
            "--max-budget-usd",
            str(max_budget_usd),
        ]
        started_wall = time.monotonic()
        started_cpu = time.process_time_ns()
        completed = subprocess.run(
            argv,
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
            check=False,
        )
        wall = time.monotonic() - started_wall
        cpu = time.process_time_ns() - started_cpu

    raw: dict[str, Any] | None = None
    parse_error = None
    if completed.stdout.strip():
        try:
            raw = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            parse_error = str(exc)

    structured = raw.get("structured_output") if isinstance(raw, Mapping) else None
    candidate_source = None
    apply_error = None
    if isinstance(structured, Mapping):
        candidate_source, apply_error = _apply_structured_edits(case, structured)
    elif parse_error is None:
        apply_error = "Claude result has no structured_output"

    evaluation = (
        evaluate_source(case, candidate_source)
        if candidate_source is not None
        else {"passed": False}
    )
    return {
        "case_id": case["id"],
        "family": case["family"],
        "passed": bool(evaluation.get("passed")),
        "external_model_calls": 1,
        "cost_usd": (
            float(raw["total_cost_usd"])
            if isinstance(raw, Mapping) and raw.get("total_cost_usd") is not None
            else None
        ),
        "wall_time_seconds": round(wall, 6),
        "controller_cpu_process_time_ns": int(cpu),
        "process_returncode": completed.returncode,
        "model": model,
        "model_usage": raw.get("modelUsage") if isinstance(raw, Mapping) else None,
        "num_turns": raw.get("num_turns") if isinstance(raw, Mapping) else None,
        "structured_output": structured,
        "parse_error": parse_error,
        "apply_error": apply_error,
        "stderr_tail": completed.stderr[-1200:],
        "evaluation": evaluation,
    }


def run_local_specialist(
    case: Mapping[str, Any],
    *,
    specialist: Mapping[str, Any],
    max_candidates: int,
) -> dict[str, Any]:
    started_wall = time.monotonic()
    started_cpu = time.process_time_ns()
    with tempfile.TemporaryDirectory(prefix="genesis-g8-local-") as tmp:
        root = Path(tmp)
        target = root / str(case["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(case["source_utf8"]), encoding="utf-8")
        generated = distillation.generate(
            root,
            specialist,
            max_candidates=max_candidates,
        )

    passed = False
    winner = None
    evaluations = []
    executions = 0
    for candidate in generated["candidates"]:
        if executions >= max_candidates:
            break
        mutations = candidate.get("mutations") or []
        if len(mutations) != 1 or mutations[0].get("path") != case["path"]:
            continue
        executions += 1
        evaluation = evaluate_source(case, str(mutations[0]["content_utf8"]))
        evaluations.append(
            {
                "candidate_id": candidate["id"],
                "candidate_digest": candidate["candidate_digest"],
                "template_digest": candidate["provenance"]["template_digest"],
                "passed": evaluation["passed"],
                "evaluation": evaluation,
            }
        )
        if evaluation["passed"]:
            passed = True
            winner = evaluations[-1]
            break

    return {
        "case_id": case["id"],
        "family": case["family"],
        "passed": passed,
        "external_model_calls": 0,
        "cost_usd": 0.0,
        "candidate_count": generated["candidate_count"],
        "candidate_executions": executions,
        "max_candidates": max_candidates,
        "winner": winner,
        "evaluations": evaluations,
        "wall_time_seconds": round(time.monotonic() - started_wall, 6),
        "controller_cpu_process_time_ns": int(time.process_time_ns() - started_cpu),
        "generation_digest": generated["generation_digest"],
    }


def _aggregate(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    solved = sum(1 for item in records if item.get("passed"))
    calls = sum(int(item.get("external_model_calls", 0)) for item in records)
    known_costs = [float(item["cost_usd"]) for item in records if item.get("cost_usd") is not None]
    total_cost = sum(known_costs) if len(known_costs) == len(records) else None
    wall = sum(float(item.get("wall_time_seconds", 0.0)) for item in records)
    cpu = sum(int(item.get("controller_cpu_process_time_ns", 0)) for item in records)
    return {
        "solved": solved,
        "case_count": len(records),
        "external_model_calls": calls,
        "external_model_calls_per_solved_task": (calls / solved if solved else None),
        "cost_usd": total_cost,
        "cost_usd_per_solved_task": (
            total_cost / solved if total_cost is not None and solved else None
        ),
        "wall_time_seconds": wall,
        "wall_time_seconds_per_solved_task": (wall / solved if solved else None),
        "controller_cpu_process_time_ns": cpu,
    }


def _ablated_specialist(specialist: Mapping[str, Any]) -> dict[str, Any]:
    held = distillation.validate_specialist(specialist)
    payload = {k: v for k, v in held.items() if k != "specialist_digest"}
    payload["templates"] = []
    payload["template_count"] = 0
    return {**payload, "specialist_digest": digest_of(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--specialist-freeze", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    freeze = json.loads(args.specialist_freeze.read_text(encoding="utf-8"))
    freeze_payload = {k: v for k, v in freeze.items() if k != "freeze_digest"}
    if freeze.get("freeze_digest") != digest_of(freeze_payload):
        raise SystemExit("G8 specialist freeze digest does not reproduce")
    specialist = distillation.validate_specialist(freeze["specialist"])
    if specialist["specialist_digest"] != prereg["specialist"]["specialist_digest"]:
        raise SystemExit("G8 specialist differs from preregistration")

    holdout_bytes = args.holdout.read_bytes()
    holdout_sha = hashlib.sha256(holdout_bytes).hexdigest()
    if holdout_sha != prereg["holdout"]["sha256"]:
        raise SystemExit("G8 holdout SHA-256 differs from preregistration")
    holdout = json.loads(holdout_bytes)
    cases = list(holdout["cases"])
    if len(cases) != prereg["holdout"]["case_count"]:
        raise SystemExit("G8 holdout case count differs from preregistration")

    apparatus_checks = {}
    for label, record in prereg["apparatus"].items():
        path = root / record["path"]
        apparatus_checks[label] = _sha(path) == record["source_sha256"]
    if not all(apparatus_checks.values()):
        raise SystemExit("G8 frozen apparatus source changed after preregistration")

    raw = [
        {
            "case_id": case["id"],
            "passed": evaluate_source(case, str(case["source_utf8"]))["passed"],
        }
        for case in cases
    ]

    external_records = []
    for case in cases:
        external_records.append(
            run_external_baseline(
                case,
                model=prereg["external_baseline"]["model"],
                max_budget_usd=float(prereg["external_baseline"]["max_budget_usd_per_case"]),
            )
        )

    local_records = [
        run_local_specialist(
            case,
            specialist=specialist,
            max_candidates=int(prereg["local_specialist"]["max_candidates_per_case"]),
        )
        for case in cases
    ]
    ablated = _ablated_specialist(specialist)
    ablation_records = [
        run_local_specialist(
            case,
            specialist=ablated,
            max_candidates=int(prereg["local_specialist"]["max_candidates_per_case"]),
        )
        for case in cases
    ]

    external = _aggregate(external_records)
    local = _aggregate(local_records)
    ablation = _aggregate(ablation_records)
    external_calls_rate = external["external_model_calls_per_solved_task"]
    local_calls_rate = local["external_model_calls_per_solved_task"]

    requirements = {
        "holdout_sha256_matches_preregistered_identity": holdout_sha == prereg["holdout"]["sha256"],
        "all_raw_tasks_fail_before_repair": all(not item["passed"] for item in raw),
        "holdout_has_four_families_and_eight_cases": len(cases) == 8 and len({case["family"] for case in cases}) == 4,
        "specialist_is_content_addressed_and_valid": specialist["specialist_digest"] == prereg["specialist"]["specialist_digest"],
        "specialist_was_distilled_from_repeated_expensive_reasoning": specialist["source_external_model_calls"] >= 4,
        "external_baseline_attempts_exactly_one_model_call_per_case": external["external_model_calls"] == len(cases),
        "local_specialist_uses_zero_external_model_calls": local["external_model_calls"] == 0,
        "local_specialist_solves_at_least_seven_of_eight": local["solved"] >= 7,
        "local_specialist_retains_or_improves_external_baseline_success": local["solved"] >= external["solved"],
        "external_model_calls_per_solved_task_strictly_decrease": (
            external_calls_rate is not None
            and local_calls_rate is not None
            and local_calls_rate < external_calls_rate
        ),
        "runtime_dollar_cost_per_solved_task_strictly_decreases": (
            external["cost_usd_per_solved_task"] is not None
            and local["cost_usd_per_solved_task"] is not None
            and local["cost_usd_per_solved_task"] < external["cost_usd_per_solved_task"]
        ),
        "local_specialist_is_materially_faster_in_wall_time": (
            external["wall_time_seconds_per_solved_task"] is not None
            and local["wall_time_seconds_per_solved_task"] is not None
            and local["wall_time_seconds_per_solved_task"]
            < external["wall_time_seconds_per_solved_task"]
        ),
        "empty_specialist_ablation_loses_capability": ablation["solved"] < local["solved"],
        "empty_specialist_ablation_solves_zero_tasks": ablation["solved"] == 0,
        "specialist_has_no_holdout_visibility_at_freeze": freeze["hidden_g8_holdout_visible"] is False,
        "distillation_itself_used_zero_external_model_calls": freeze["external_model_calls_for_distillation"] == 0,
        "mutable_specialist_does_not_own_evaluator_or_verdict": prereg["authority"]["mutable_specialist_owns_evaluator_or_verdict"] is False,
    }
    passed = all(requirements.values())

    payload = {
        "schema": RESULT_SCHEMA,
        "preregistration_digest": prereg["preregistration_digest"],
        "specialist_freeze_digest": freeze["freeze_digest"],
        "specialist_digest": specialist["specialist_digest"],
        "holdout": {
            "sha256": holdout_sha,
            "content_digest": holdout["holdout_content_digest"],
            "case_count": len(cases),
            "families": holdout["families"],
            "raw_results": raw,
        },
        "apparatus_checks": apparatus_checks,
        "external_baseline": {
            "aggregate": external,
            "cases": external_records,
        },
        "local_specialist": {
            "aggregate": local,
            "cases": local_records,
        },
        "empty_specialist_ablation": {
            "aggregate": ablation,
            "cases": ablation_records,
        },
        "requirements": requirements,
        "gate_passed": passed,
        "verdict": (
            prereg["qualification_rule"]["pass_label"]
            if passed
            else prereg["qualification_rule"]["fail_label"]
        ),
        "claim_boundary": prereg["claim_boundary"],
    }
    payload["result_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
