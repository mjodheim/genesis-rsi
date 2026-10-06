"""Freeze the prospective Genesis G5 qualification before holdout reveal."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from genesis.core import self_model
from genesis.evolution import experiment_design
from genesis.languages import toolchains
from genesis.learning import failure_model
from genesis.operators import structural, universal
from genesis.trust_root import digest_of

SCHEMA = "genesis-g5-qualification-preregistration-v1"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--holdout-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repository_root.resolve()
    holdout_sha = args.holdout_sha256.strip().lower()
    if len(holdout_sha) != 64 or any(c not in "0123456789abcdef" for c in holdout_sha):
        raise SystemExit("invalid holdout sha256")

    source_before = "def pick(items):\n    return items[1]\n"
    source_after = "def pick(items):\n    return items[0]\n"
    source_result = {
        "evaluator": "python-function-contract-v1",
        "before_expected_failure": True,
        "after_expected_pass": True,
        "before_sha256": sha256_text(source_before),
        "after_sha256": sha256_text(source_after),
    }
    source_result_digest = digest_of(source_result)

    structural_operator = structural.synthesize_operator(
        source_before,
        source_after,
        source_result_digest=source_result_digest,
        source_path="source.py",
        context_lines=0,
    )
    universal_operator = universal.learn_from_validated_pair(
        source_before,
        source_after,
        source_path="source.py",
        source_result_digest=source_result_digest,
    )

    with tempfile.TemporaryDirectory(prefix="genesis-g5-calibration-") as tmp:
        root = Path(tmp)
        (root / "Calibration.csproj").write_text(
            '<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup>'
            '<OutputType>Exe</OutputType><TargetFramework>net10.0</TargetFramework>'
            '<ImplicitUsings>disable</ImplicitUsings><Nullable>disable</Nullable>'
            '</PropertyGroup></Project>\n',
            encoding="utf-8",
        )
        program = (
            "using System;\n"
            "class Program { static int Pick(int[] values) => values[1]; "
            "static int Main() => Pick(new[]{41,99}) == 41 ? 0 : 17; }\n"
        )
        (root / "Program.cs").write_text(program, encoding="utf-8")

        baseline = subprocess.run(
            ["dotnet", "run", "--project", "Calibration.csproj", "--nologo"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=90,
        )
        structural_result = structural.generate(
            root,
            [structural_operator],
            include_prefixes=["Program.cs"],
            max_candidates=64,
        )
        if baseline.returncode == 0:
            raise SystemExit("calibration baseline unexpectedly passes")
        if structural_result["candidate_count"] != 0:
            raise SystemExit("calibration structural parent unexpectedly emits C# candidate")

        run_record = {
            "report_digest": digest_of({
                "calibration_source_sha256": sha256_text(program),
                "baseline_returncode": baseline.returncode,
                "structural_candidate_count": structural_result["candidate_count"],
            }),
            "candidate_budget": 64,
            "charged_candidate_executions": 0,
            "winner": None,
            "autonomous_passed": False,
            "schedule": {
                "scheduled_count": 0,
                "family_input_counts": {
                    "learned": 0,
                    "retained": 0,
                    "structural": structural_result["candidate_count"],
                },
                "family_scheduled_counts": {},
            },
        }

        tc = toolchains.capability_report(root)
        diagnosis = failure_model.diagnose(
            root,
            run_record,
            target_prefixes=["Program.cs"],
            toolchain_report=tc,
        )

    if diagnosis["primary_failure_class"] != "operator":
        raise SystemExit(
            f"calibration failure was not attributed to operator: {diagnosis['primary_failure_class']}"
        )

    model = self_model.build_self_model(repo)
    target = self_model.choose_intervention_target(model, diagnosis)
    if set(target["candidate_component_ids"]) != {
        "structural_operator_engine",
        "universal_operator_ir",
    }:
        raise SystemExit("unexpected G4 candidate components")

    plan = experiment_design.design_experiment(
        model,
        diagnosis,
        evaluator_id="external-dotnet-exitcode-evaluator-v1",
        fresh_case_set_id=f"sha256:{holdout_sha}",
        budget={
            "candidate_executions": 6,
            "wall_time_seconds": 120,
            "external_model_calls": 0,
        },
        metrics=(
            "task_success",
            "candidate_executions",
            "wall_time",
            "external_model_calls",
        ),
    )

    payload = {
        "schema": SCHEMA,
        "apparatus_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "holdout": {
            "sha256": holdout_sha,
            "case_count": 6,
            "contents_visible_to_mutable_lineage": False,
            "location_at_freeze": "external_to_repository",
        },
        "source_capability": {
            "source_language": "python",
            "source_result": source_result,
            "source_result_digest": source_result_digest,
            "structural_operator": structural_operator,
            "universal_operator": universal_operator,
        },
        "calibration": {
            "baseline_failed": True,
            "structural_parent_candidate_count": 0,
            "failure_record": diagnosis,
            "intervention_target": target,
        },
        "g5_plan": plan,
        "qualification_rule": {
            "required": [
                "holdout_sha256_matches_preregistered_identity",
                "control_parent_success_rate_is_lower_than_best_candidate",
                "best_candidate_targets_component_named_by_g5_plan",
                "best_candidate_uses_no_more_budget_than_control",
                "best_candidate_uses_zero_external_model_calls",
                "at_least_4_of_6_hidden_cases_solved",
                "ablation_of_winning_component_removes_gain",
            ],
            "pass_label": "G5_SCIENTIFIC_GATE_PASSED",
            "fail_label": "G5_SCIENTIFIC_GATE_OPEN",
        },
        "claim_boundary": (
            "Prospective G5 qualification only. Passing establishes autonomous "
            "experiment-generation evidence for one internal software mechanism; "
            "it does not establish G6, general RSI, AGI, or ASI."
        ),
    }
    payload["preregistration_digest"] = digest_of(payload)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
