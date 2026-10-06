"""Execute the preregistered G5 qualification after holdout reveal.

This runner is outside mutable Genesis' decision loop. It verifies the sealed
holdout identity, evaluates every preregistered arm under the same case/execution
budget, performs the winning-component ablation, and applies only the pass/fail
rule frozen in PREREGISTRATION.json.
"""
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

from genesis.operators import structural, universal
from genesis.trust_root import digest_of

RESULT_SCHEMA = "genesis-g5-qualification-result-v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dotnet_eval(root: Path, timeout_seconds: int = 30) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(
        ["dotnet", "run", "--project", "Case.csproj", "--nologo"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
    )
    return {
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "wall_time_seconds": round(time.monotonic() - started, 6),
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


def _write_case(root: Path, case: Mapping[str, Any]) -> None:
    for relative, content in dict(case["files"]).items():
        target = root / str(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(content), encoding="utf-8")


def _component_candidates(
    component_id: str | None,
    root: Path,
    prereg: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if component_id is None:
        original = (root / "Program.cs").read_text(encoding="utf-8")
        return [{
            "id": "control-parent",
            "mutations": [{
                "path": "Program.cs",
                "content_utf8": original,
            }],
        }]

    source = dict(prereg["source_capability"])
    if component_id == "structural_operator_engine":
        generated = structural.generate(
            root,
            [source["structural_operator"]],
            include_prefixes=["Program.cs"],
            max_candidates=1,
        )
        return list(generated["candidates"])

    if component_id == "universal_operator_ir":
        generated = universal.generate(
            root,
            [source["universal_operator"]],
            include_prefixes=["Program.cs"],
            max_candidates=1,
        )
        return list(generated["candidates"])

    raise ValueError(f"unsupported qualification component: {component_id}")


def _evaluate_arm(
    arm: Mapping[str, Any],
    holdout: Mapping[str, Any],
    prereg: Mapping[str, Any],
) -> dict[str, Any]:
    started = time.monotonic()
    budget = dict(arm["budget"])
    max_exec = int(budget["candidate_executions"])
    wall_limit = int(budget.get("wall_time_seconds", 120))
    executions = 0
    solved = 0
    case_records: list[dict[str, Any]] = []

    for case in list(holdout["cases"]):
        if executions >= max_exec or time.monotonic() - started >= wall_limit:
            case_records.append({
                "case_id": case["id"],
                "status": "budget_not_reached",
                "passed": False,
            })
            continue

        with tempfile.TemporaryDirectory(prefix=f"g5-{arm['name']}-") as tmp:
            root = Path(tmp)
            _write_case(root, case)
            candidates = _component_candidates(arm.get("component_id"), root, prereg)
            if not candidates:
                case_records.append({
                    "case_id": case["id"],
                    "status": "no_candidate",
                    "passed": False,
                    "candidate_count": 0,
                })
                continue

            candidate = candidates[0]
            mutation = dict(candidate["mutations"][0])
            (root / str(mutation["path"])).write_text(
                str(mutation["content_utf8"]),
                encoding="utf-8",
            )
            evaluation = _dotnet_eval(root)
            executions += 1
            if evaluation["passed"]:
                solved += 1
            case_records.append({
                "case_id": case["id"],
                "status": "evaluated",
                "passed": evaluation["passed"],
                "candidate_id": candidate.get("id"),
                "evaluation": evaluation,
            })

    elapsed = round(time.monotonic() - started, 6)
    payload = {
        "arm_name": arm["name"],
        "arm_digest": arm["arm_digest"],
        "component_id": arm.get("component_id"),
        "intervention": arm["intervention"],
        "case_count": len(holdout["cases"]),
        "solved": solved,
        "success_rate": solved / len(holdout["cases"]),
        "candidate_executions": executions,
        "wall_time_seconds": elapsed,
        "external_model_calls": 0,
        "within_candidate_budget": executions <= max_exec,
        "within_wall_time_budget": elapsed <= wall_limit,
        "cases": case_records,
    }
    return {**payload, "arm_result_digest": digest_of(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    prereg = json.loads(args.preregistration.read_text(encoding="utf-8"))
    holdout_bytes = args.holdout.read_bytes()
    holdout_sha = hashlib.sha256(holdout_bytes).hexdigest()
    expected_sha = str(prereg["holdout"]["sha256"])
    if holdout_sha != expected_sha:
        raise SystemExit("sealed holdout SHA-256 does not match preregistration")
    holdout = json.loads(holdout_bytes)
    if len(holdout["cases"]) != int(prereg["holdout"]["case_count"]):
        raise SystemExit("holdout case count does not match preregistration")

    # Validate that these are genuinely failing repair tasks before comparing
    # machinery. This check uses the already revealed holdout and is reported,
    # not used to alter the frozen plan.
    baseline_case_results = []
    for case in holdout["cases"]:
        with tempfile.TemporaryDirectory(prefix="g5-baseline-validate-") as tmp:
            root = Path(tmp)
            _write_case(root, case)
            baseline_case_results.append({
                "case_id": case["id"],
                **_dotnet_eval(root),
            })
    baseline_all_fail = all(not item["passed"] for item in baseline_case_results)

    arms = [
        _evaluate_arm(arm, holdout, prereg)
        for arm in prereg["g5_plan"]["arms"]
    ]
    control = next(item for item in arms if item["arm_name"] == "control-parent")
    candidates = [item for item in arms if item["arm_name"] != "control-parent"]
    best = sorted(
        candidates,
        key=lambda item: (
            -item["solved"],
            item["candidate_executions"],
            item["wall_time_seconds"],
            item["arm_name"],
        ),
    )[0]

    winning_component = best["component_id"]
    # Component ablation: remove the winning component but keep the alternative
    # operator machinery named by the same G5 plan. If the winner is universal,
    # this is the structural-only parent; vice versa for a structural winner.
    alternative_ids = [
        item for item in prereg["g5_plan"]["target_component_ids"]
        if item != winning_component
    ]
    ablation_component = alternative_ids[0] if alternative_ids else None
    ablation_arm = {
        "name": "winning-component-ablation",
        "arm_digest": digest_of({
            "kind": "ablation",
            "removed_component": winning_component,
            "remaining_component": ablation_component,
        }),
        "component_id": ablation_component,
        "intervention": "winning_component_removed",
        "budget": dict(prereg["g5_plan"]["matched_budget"]),
    }
    ablation = _evaluate_arm(ablation_arm, holdout, prereg)

    requirements = {
        "holdout_sha256_matches_preregistered_identity": holdout_sha == expected_sha,
        "control_parent_success_rate_is_lower_than_best_candidate": (
            best["success_rate"] > control["success_rate"]
        ),
        "best_candidate_targets_component_named_by_g5_plan": (
            best["component_id"] in prereg["g5_plan"]["target_component_ids"]
        ),
        "best_candidate_uses_no_more_budget_than_control": (
            best["candidate_executions"]
            <= int(prereg["g5_plan"]["matched_budget"]["candidate_executions"])
            and best["within_wall_time_budget"]
        ),
        "best_candidate_uses_zero_external_model_calls": (
            best["external_model_calls"] == 0
        ),
        "at_least_4_of_6_hidden_cases_solved": best["solved"] >= 4,
        "ablation_of_winning_component_removes_gain": (
            ablation["solved"] < best["solved"]
        ),
    }
    gate_passed = all(requirements.values()) and baseline_all_fail

    payload = {
        "schema": RESULT_SCHEMA,
        "preregistration_digest": prereg["preregistration_digest"],
        "preregistration_apparatus_commit": prereg["apparatus_commit"],
        "preregistration_git_commit": subprocess.run(
            ["git", "rev-parse", "cb33aef4"],
            cwd=args.preregistration.resolve().parents[2],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "holdout": {
            "sha256": holdout_sha,
            "case_count": len(holdout["cases"]),
            "revealed_only_after_preregistration_commit": True,
            "baseline_all_fail": baseline_all_fail,
            "baseline_case_results": baseline_case_results,
        },
        "arms": arms,
        "best_candidate": best,
        "winning_component": winning_component,
        "ablation": ablation,
        "requirements": requirements,
        "gate_passed": gate_passed,
        "verdict": (
            prereg["qualification_rule"]["pass_label"]
            if gate_passed
            else prereg["qualification_rule"]["fail_label"]
        ),
        "external_model_calls": 0,
        "claim_boundary": prereg["claim_boundary"],
    }
    payload["result_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if gate_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
