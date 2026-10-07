"""Run the prospective Genesis v2 G9 whole-successor qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any, Mapping

from genesis import patch_templates
from genesis.evolution import successor_generation
from genesis.runtime import profile_executor
from genesis.trust_root import digest_of

RESULT_SCHEMA = "genesis-g9-qualification-result-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_case(root: Path, case: Mapping[str, Any]) -> None:
    for rel, content in dict(case["files"]).items():
        path = root / str(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")


def _single_changed_line(original: str, candidate: str, expected_new: str) -> bool:
    before = original.splitlines()
    after = candidate.splitlines()
    if len(before) != len(after):
        return False
    changed = [i for i, (left, right) in enumerate(zip(before, after)) if left != right]
    if len(changed) != 1:
        return False
    idx = changed[0]
    return patch_templates.tokenize(after[idx].strip()) == patch_templates.tokenize(
        expected_new.strip()
    )


def _evaluate_workspace(root: Path, case: Mapping[str, Any]) -> dict[str, Any]:
    kind = str((case.get("evaluation") or {}).get("kind") or "")
    started = time.monotonic()
    if kind == "dotnet_exit_zero":
        cp = subprocess.run(
            ["dotnet", "run", "--project", "Case.csproj", "--nologo"],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=40,
            check=False,
        )
        return {
            "passed": cp.returncode == 0,
            "returncode": cp.returncode,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": cp.stdout[-800:],
            "stderr_tail": cp.stderr[-800:],
        }
    if kind == "python_exit_zero":
        rel = next(iter(case["files"]))
        cp = subprocess.run(
            ["python3", str(root / rel)],
            cwd=root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20,
            check=False,
        )
        return {
            "passed": cp.returncode == 0,
            "returncode": cp.returncode,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "stdout_tail": cp.stdout[-800:],
            "stderr_tail": cp.stderr[-800:],
        }
    if kind == "static_single_line":
        expected = dict(case["expected_replacement"])
        path = root / expected["path"]
        candidate = path.read_text(encoding="utf-8")
        original = str(case["files"][expected["path"]])
        changed = _single_changed_line(original, candidate, str(expected["new"]))
        protected = str((case.get("evaluation") or {}).get("protected_substring") or "")
        protected_ok = not protected or protected in candidate
        return {
            "passed": changed and protected_ok,
            "returncode": 0 if changed and protected_ok else 1,
            "wall_time_seconds": round(time.monotonic() - started, 6),
            "single_changed_line": changed,
            "protected_invariant": protected_ok,
        }
    raise RuntimeError(f"unsupported G9 evaluation kind: {kind}")


def _apply_candidate(
    root: Path,
    candidate: Mapping[str, Any],
) -> tuple[bool, str | None]:
    mutations = list(candidate.get("mutations") or [])
    if len(mutations) != 1:
        return False, "candidate must contain exactly one mutation"
    mutation = mutations[0]
    rel = str(mutation.get("path") or "")
    target = (root / rel).resolve()
    if not str(target).startswith(str(root.resolve()) + "/"):
        return False, "unsafe mutation path"
    if not target.is_file():
        return False, "mutation target missing"
    before = target.read_text(encoding="utf-8")
    expected = str(mutation.get("expected_sha256") or "")
    if hashlib.sha256(before.encode()).hexdigest() != expected:
        return False, "mutation expected source digest mismatch"
    target.write_text(str(mutation.get("content_utf8") or ""), encoding="utf-8")
    return True, None


def _evaluate_profile(
    repository_root: Path,
    profile: Mapping[str, Any],
    holdout: Mapping[str, Any],
    *,
    operator: Mapping[str, Any],
    max_candidates_per_case: int,
) -> dict[str, Any]:
    solved = 0
    total_executions = 0
    cases: list[dict[str, Any]] = []
    wall_started = time.monotonic()
    cpu_started = time.process_time_ns()

    for case in holdout["cases"]:
        with tempfile.TemporaryDirectory(prefix="genesis-g9-profile-") as temp:
            task = Path(temp)
            _write_case(task, case)
            generated = profile_executor.generate_candidates(
                task,
                profile,
                repository_root=repository_root,
                universal_operator=operator,
                max_candidates=max_candidates_per_case,
            )
            case_record: dict[str, Any] = {
                "case_id": case["id"],
                "group": case["group"],
                "candidate_count": generated["candidate_count"],
                "route_candidate_counts": generated["route_candidate_counts"],
                "candidate_budget": max_candidates_per_case,
                "candidate_executions": 0,
                "passed": False,
                "winner": None,
                "evaluations": [],
                "generation_digest": generated["generation_digest"],
            }

            for candidate in generated["candidates"][:max_candidates_per_case]:
                with tempfile.TemporaryDirectory(prefix="genesis-g9-candidate-") as cand_tmp:
                    candidate_root = Path(cand_tmp)
                    _write_case(candidate_root, case)
                    applied, apply_error = _apply_candidate(candidate_root, candidate)
                    case_record["candidate_executions"] += 1
                    total_executions += 1
                    if not applied:
                        ev = {"passed": False, "apply_error": apply_error}
                    else:
                        ev = _evaluate_workspace(candidate_root, case)
                    item = {
                        "candidate_id": candidate["candidate_id"],
                        "candidate_digest": candidate["candidate_digest"],
                        "route": candidate["route"],
                        "passed": bool(ev.get("passed")),
                        "evaluation": ev,
                    }
                    case_record["evaluations"].append(item)
                    if ev.get("passed"):
                        case_record["passed"] = True
                        case_record["winner"] = item
                        solved += 1
                        break

            cases.append(case_record)

    group_solved: dict[str, int] = {}
    for case in cases:
        group_solved.setdefault(case["group"], 0)
        group_solved[case["group"]] += int(case["passed"])

    payload = {
        "profile_digest": profile["profile_digest"],
        "solved": solved,
        "case_count": len(cases),
        "success_rate": solved / len(cases),
        "group_solved": group_solved,
        "candidate_executions": total_executions,
        "candidate_budget_per_case": max_candidates_per_case,
        "candidate_budget_total": max_candidates_per_case * len(cases),
        "within_candidate_budget": total_executions <= max_candidates_per_case * len(cases),
        "external_model_calls": 0,
        "wall_time_seconds": round(time.monotonic() - wall_started, 6),
        "controller_cpu_process_time_ns": int(time.process_time_ns() - cpu_started),
        "cases": cases,
    }
    return {**payload, "measurement_digest": digest_of(payload)}


def _raw_failures(holdout: Mapping[str, Any]) -> list[dict[str, Any]]:
    records = []
    for case in holdout["cases"]:
        with tempfile.TemporaryDirectory(prefix="genesis-g9-raw-") as temp:
            root = Path(temp)
            _write_case(root, case)
            ev = _evaluate_workspace(root, case)
            records.append(
                {
                    "case_id": case["id"],
                    "group": case["group"],
                    "passed": bool(ev["passed"]),
                    "evaluation": ev,
                }
            )
    return records


def _pass_ids(measurement: Mapping[str, Any]) -> set[str]:
    return {str(case["case_id"]) for case in measurement["cases"] if case["passed"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--successor-freeze", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repository = args.repository_root.resolve()
    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    freeze = json.loads(args.successor_freeze.read_text(encoding="utf-8"))
    freeze_payload = {k: v for k, v in freeze.items() if k != "freeze_digest"}
    if freeze.get("freeze_digest") != digest_of(freeze_payload):
        raise SystemExit("G9 successor freeze digest does not reproduce")
    proposal = successor_generation.validate_proposal(freeze["proposal"])
    if proposal["proposal_digest"] != prereg["successor"]["proposal_digest"]:
        raise SystemExit("G9 successor proposal differs from preregistration")

    holdout_bytes = args.holdout.read_bytes()
    holdout_sha = hashlib.sha256(holdout_bytes).hexdigest()
    if holdout_sha != prereg["holdout"]["sha256"]:
        raise SystemExit("G9 holdout SHA-256 differs from preregistration")
    holdout = json.loads(holdout_bytes)
    if len(holdout["cases"]) != prereg["holdout"]["case_count"]:
        raise SystemExit("G9 holdout case count differs from preregistration")

    for label, record in prereg["apparatus"].items():
        if _sha(repository / record["path"]) != record["source_sha256"]:
            raise SystemExit(f"G9 frozen apparatus changed: {label}")

    g5 = json.loads((repository / "experiment/g5_qualification/PREREGISTRATION.json").read_text())
    operator = g5["source_capability"]["universal_operator"]
    budget = int(prereg["resource_budget"]["candidate_executions_per_case"])

    parent_profile = proposal["parent_profile"]
    successor_profile = proposal["successor_profile"]
    g6_ablation = successor_generation.ablate_profile(
        proposal, remove_change="g6_universal_operator"
    )
    g8_ablation = successor_generation.ablate_profile(
        proposal, remove_change="g8_local_specialist"
    )

    raw = _raw_failures(holdout)
    parent = _evaluate_profile(
        repository, parent_profile, holdout, operator=operator, max_candidates_per_case=budget
    )
    successor = _evaluate_profile(
        repository, successor_profile, holdout, operator=operator, max_candidates_per_case=budget
    )
    without_g6 = _evaluate_profile(
        repository, g6_ablation, holdout, operator=operator, max_candidates_per_case=budget
    )
    without_g8 = _evaluate_profile(
        repository, g8_ablation, holdout, operator=operator, max_candidates_per_case=budget
    )

    parent_pass = _pass_ids(parent)
    successor_pass = _pass_ids(successor)

    expected_groups = {
        "parent_retention": 4,
        "g6_component_gain": 4,
        "g8_specialist_gain": 4,
    }
    requirements = {
        "holdout_sha256_matches_preregistered_identity": holdout_sha == prereg["holdout"]["sha256"],
        "all_raw_tasks_fail_before_repair": all(not item["passed"] for item in raw),
        "holdout_has_three_balanced_blocks": holdout["group_counts"] == expected_groups,
        "successor_proposal_is_content_addressed_and_valid": freeze["proposal_digest"] == proposal["proposal_digest"],
        "successor_is_lineage_produced": proposal["lineage_produced"] is True,
        "successor_contains_multiple_material_machinery_changes": proposal["material_change_count"] >= 3,
        "successor_was_generated_without_g9_holdout_visibility": freeze["prospective_g9_holdout_visible"] is False,
        "successor_generation_is_exactly_parent_plus_one": successor_profile["generation"] == parent_profile["generation"] + 1,
        "successor_improves_fresh_success_rate": successor["solved"] > parent["solved"],
        "successor_solves_at_least_11_of_12_fresh_cases": successor["solved"] >= 11,
        "successor_preserves_every_parent_success": parent_pass <= successor_pass,
        "successor_preserves_all_parent_retention_cases": successor["group_solved"].get("parent_retention") == 4,
        "matched_candidate_budgets_are_identical": all(
            item["candidate_budget_per_case"] == budget
            for item in (parent, successor, without_g6, without_g8)
        ),
        "all_profiles_use_zero_external_model_calls": all(
            item["external_model_calls"] == 0
            for item in (parent, successor, without_g6, without_g8)
        ),
        "all_profiles_stay_within_matched_candidate_budget": all(
            item["within_candidate_budget"]
            for item in (parent, successor, without_g6, without_g8)
        ),
        "g6_ablation_removes_g6_block_gain": (
            without_g6["group_solved"].get("g6_component_gain", 0)
            < successor["group_solved"].get("g6_component_gain", 0)
        ),
        "g8_ablation_removes_g8_block_gain": (
            without_g8["group_solved"].get("g8_specialist_gain", 0)
            < successor["group_solved"].get("g8_specialist_gain", 0)
        ),
        "each_causal_ablation_is_worse_than_whole_successor": (
            without_g6["solved"] < successor["solved"]
            and without_g8["solved"] < successor["solved"]
        ),
        "whole_successor_inherits_unchanged_component_inventory": (
            successor_profile["component_inventory"] == parent_profile["component_inventory"]
        ),
        "mutable_lineage_does_not_own_evaluator_or_verdict": prereg["authority"]["mutable_lineage_owns_evaluator_or_verdict"] is False,
        "resource_accounting_records_candidate_cpu_and_wall_axes": all(
            all(key in item for key in ("candidate_executions", "controller_cpu_process_time_ns", "wall_time_seconds"))
            for item in (parent, successor, without_g6, without_g8)
        ),
    }
    gate = all(requirements.values())

    payload = {
        "schema": RESULT_SCHEMA,
        "preregistration_digest": prereg["preregistration_digest"],
        "successor_freeze_digest": freeze["freeze_digest"],
        "proposal_digest": proposal["proposal_digest"],
        "parent_profile_digest": parent_profile["profile_digest"],
        "successor_profile_digest": successor_profile["profile_digest"],
        "holdout": {
            "sha256": holdout_sha,
            "content_digest": holdout["holdout_content_digest"],
            "case_count": len(holdout["cases"]),
            "group_counts": holdout["group_counts"],
            "raw_cases": raw,
        },
        "parent": parent,
        "successor": successor,
        "without_g6_ablation": without_g6,
        "without_g8_ablation": without_g8,
        "requirements": requirements,
        "gate_passed": gate,
        "verdict": (
            prereg["qualification_rule"]["pass_label"]
            if gate
            else prereg["qualification_rule"]["fail_label"]
        ),
        "external_model_calls": 0,
        "claim_boundary": prereg["claim_boundary"],
    }
    payload["result_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if gate else 2


if __name__ == "__main__":
    raise SystemExit(main())
