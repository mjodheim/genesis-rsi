"""Freeze the prospective Genesis v2 G9 whole-successor qualification."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from genesis.evolution import successor_generation
from genesis.trust_root import digest_of

SCHEMA = "genesis-g9-qualification-preregistration-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--successor-freeze", type=Path, required=True)
    parser.add_argument("--holdout-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    freeze = json.loads(args.successor_freeze.read_text(encoding="utf-8"))
    freeze_payload = {k: v for k, v in freeze.items() if k != "freeze_digest"}
    if freeze.get("freeze_digest") != digest_of(freeze_payload):
        raise SystemExit("G9 successor freeze digest does not reproduce")
    proposal = successor_generation.validate_proposal(freeze["proposal"])

    holdout_sha = args.holdout_sha256.strip().lower()
    if len(holdout_sha) != 64 or any(c not in "0123456789abcdef" for c in holdout_sha):
        raise SystemExit("invalid holdout SHA-256")

    apparatus_paths = {
        "successor_generator": "genesis/evolution/successor_generation.py",
        "profile_executor": "genesis/runtime/profile_executor.py",
        "self_model": "genesis/core/self_model.py",
        "successor_builder": "scripts/build_g9_successor.py",
        "holdout_builder": "scripts/build_g9_holdout.py",
        "qualification_runner": "scripts/run_g9_qualification.py",
    }
    apparatus = {
        name: {"path": rel, "source_sha256": _sha(root / rel)}
        for name, rel in apparatus_paths.items()
    }

    required = [
        "holdout_sha256_matches_preregistered_identity",
        "all_raw_tasks_fail_before_repair",
        "holdout_has_three_balanced_blocks",
        "successor_proposal_is_content_addressed_and_valid",
        "successor_is_lineage_produced",
        "successor_contains_multiple_material_machinery_changes",
        "successor_was_generated_without_g9_holdout_visibility",
        "successor_generation_is_exactly_parent_plus_one",
        "successor_improves_fresh_success_rate",
        "successor_solves_at_least_11_of_12_fresh_cases",
        "successor_preserves_every_parent_success",
        "successor_preserves_all_parent_retention_cases",
        "matched_candidate_budgets_are_identical",
        "all_profiles_use_zero_external_model_calls",
        "all_profiles_stay_within_matched_candidate_budget",
        "g6_ablation_removes_g6_block_gain",
        "g8_ablation_removes_g8_block_gain",
        "each_causal_ablation_is_worse_than_whole_successor",
        "whole_successor_inherits_unchanged_component_inventory",
        "mutable_lineage_does_not_own_evaluator_or_verdict",
        "resource_accounting_records_candidate_cpu_and_wall_axes",
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
        "successor": {
            "freeze_digest": freeze["freeze_digest"],
            "proposal_digest": proposal["proposal_digest"],
            "parent_profile_digest": proposal["parent_profile"]["profile_digest"],
            "successor_profile_digest": proposal["successor_profile"]["profile_digest"],
            "parent_generation": proposal["parent_profile"]["generation"],
            "successor_generation": proposal["successor_profile"]["generation"],
            "material_change_count": proposal["material_change_count"],
            "material_changes": proposal["material_changes"],
            "lineage_produced": proposal["lineage_produced"],
            "prospective_holdout_visible": proposal["prospective_holdout_visible"],
            "external_model_calls": proposal["external_model_calls"],
        },
        "holdout": {
            "sha256": holdout_sha,
            "case_count": 12,
            "group_counts": {
                "parent_retention": 4,
                "g6_component_gain": 4,
                "g8_specialist_gain": 4,
            },
            "generated_after_successor_freeze": True,
            "contents_visible_to_lineage_at_freeze": False,
            "location_at_freeze": "external_to_repository",
        },
        "resource_budget": {
            "candidate_executions_per_case": 4,
            "external_model_calls_per_case": 0,
            "same_budget_for_parent_successor_and_ablations": True,
        },
        "authority": {
            "mutable_lineage_owns_evaluator_or_verdict": False,
            "same_frozen_evaluator_for_parent_successor_and_ablations": True,
            "promotion_authority": "external_trust_root",
        },
        "qualification_rule": {
            "required": required,
            "pass_label": "G9_SCIENTIFIC_GATE_PASSED",
            "fail_label": "G9_SCIENTIFIC_GATE_OPEN",
        },
        "claim_boundary": (
            "Bounded project-defined G9 whole-successor qualification only. Passing shows one "
            "lineage-produced Genesis N -> Genesis N+1 transition with multiple material machinery "
            "changes, fresh matched-budget improvement, causal ablations and retained parent "
            "capability. A single transition is not recursive self-improvement and does not "
            "establish G10, general RSI, AGI, ASI or independent third-party validation."
        ),
    }
    payload["preregistration_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
