"""Freeze the prospective Genesis G8 qualification before holdout reveal."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from genesis.learning import distillation
from genesis.trust_root import digest_of

SCHEMA = "genesis-g8-qualification-preregistration-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--specialist-freeze", type=Path, required=True)
    parser.add_argument("--holdout-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    freeze = json.loads(args.specialist_freeze.read_text(encoding="utf-8"))
    freeze_payload = {k: v for k, v in freeze.items() if k != "freeze_digest"}
    if freeze.get("freeze_digest") != digest_of(freeze_payload):
        raise SystemExit("specialist freeze digest does not reproduce")
    specialist = distillation.validate_specialist(freeze["specialist"])

    holdout_sha = args.holdout_sha256.strip().lower()
    if len(holdout_sha) != 64 or any(c not in "0123456789abcdef" for c in holdout_sha):
        raise SystemExit("invalid holdout SHA-256")

    claude_version = subprocess.run(
        ["claude", "--version"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    apparatus_paths = {
        "distillation": "genesis/learning/distillation.py",
        "specialist_builder": "scripts/build_g8_specialist.py",
        "holdout_generator": "scripts/build_g8_holdout.py",
        "qualification_runner": "scripts/run_g8_qualification.py",
    }
    apparatus = {
        key: {"path": rel, "source_sha256": _sha(root / rel)}
        for key, rel in apparatus_paths.items()
    }

    required = [
        "holdout_sha256_matches_preregistered_identity",
        "all_raw_tasks_fail_before_repair",
        "holdout_has_four_families_and_eight_cases",
        "specialist_is_content_addressed_and_valid",
        "specialist_was_distilled_from_repeated_expensive_reasoning",
        "external_baseline_attempts_exactly_one_model_call_per_case",
        "local_specialist_uses_zero_external_model_calls",
        "local_specialist_solves_at_least_seven_of_eight",
        "local_specialist_retains_or_improves_external_baseline_success",
        "external_model_calls_per_solved_task_strictly_decrease",
        "runtime_dollar_cost_per_solved_task_strictly_decreases",
        "local_specialist_is_materially_faster_in_wall_time",
        "empty_specialist_ablation_loses_capability",
        "empty_specialist_ablation_solves_zero_tasks",
        "specialist_has_no_holdout_visibility_at_freeze",
        "distillation_itself_used_zero_external_model_calls",
        "mutable_specialist_does_not_own_evaluator_or_verdict",
    ]

    payload = {
        "schema": SCHEMA,
        "preregistration_commit_parent": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "apparatus": apparatus,
        "specialist": {
            "freeze_digest": freeze["freeze_digest"],
            "specialist_digest": specialist["specialist_digest"],
            "specialist_id": specialist["specialist_id"],
            "template_count": specialist["template_count"],
            "source_external_model_calls": specialist["source_external_model_calls"],
            "source_cost_usd": specialist["source_cost_usd"],
            "runtime_external_model_calls": specialist["runtime_external_model_calls"],
            "distillation_sources": specialist["distilled_from"],
        },
        "external_baseline": {
            "provider": "Claude Code",
            "cli_version": claude_version,
            "model": "claude-sonnet-5-5",
            "invocations_per_case": 1,
            "max_budget_usd_per_case": 0.5,
            "tools": ["Read", "Glob", "Grep"],
            "commands_or_tests_allowed": False,
            "web_allowed": False,
            "evaluator_visible": False,
            "model_call_accounting": (
                "one non-interactive fallback session equals one external_model_call, "
                "matching the A6b project convention even if provider-internal turns exceed one"
            ),
        },
        "local_specialist": {
            "max_candidates_per_case": 16,
            "external_model_calls": 0,
            "runtime_cost_usd": 0.0,
            "evaluator_visible": False,
        },
        "authority": {
            "mutable_specialist_owns_evaluator_or_verdict": False,
            "same_frozen_evaluator_for_external_and_local_arms": True,
        },
        "holdout": {
            "sha256": holdout_sha,
            "case_count": 8,
            "family_count": 4,
            "generated_after_specialist_freeze": True,
            "contents_visible_to_specialist_at_freeze": False,
            "location_at_freeze": "external_to_repository",
        },
        "qualification_rule": {
            "required": required,
            "pass_label": "G8_SCIENTIFIC_GATE_PASSED",
            "fail_label": "G8_SCIENTIFIC_GATE_OPEN",
        },
        "claim_boundary": (
            "Bounded project-defined G8 distillation/local-specialization qualification only. "
            "Passing shows that previously expensive validated repair reasoning can be compiled "
            "into cheaper retained local machinery on fresh related families. It does not establish "
            "G9 whole-successor generation, G10 recursive successor chains, general RSI, AGI, ASI, "
            "or independent third-party validation."
        ),
    }
    payload["preregistration_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
