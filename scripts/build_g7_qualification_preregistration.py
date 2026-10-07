"""Build the prospective Genesis G7 qualification record before holdout reveal."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from genesis.trust_root import digest_of

SCHEMA = "genesis-g7-qualification-preregistration-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--holdout-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    candidate_payload = {
        key: value
        for key, value in candidates.items()
        if key != "candidate_set_digest"
    }
    if candidates.get("candidate_set_digest") != digest_of(candidate_payload):
        raise SystemExit("candidate set digest does not reproduce")

    holdout_sha = args.holdout_sha256.strip().lower()
    if len(holdout_sha) != 64 or any(c not in "0123456789abcdef" for c in holdout_sha):
        raise SystemExit("invalid holdout SHA-256")

    lineage_path = root / "genesis/evolution/lineage_promotion.py"
    evaluator_path = root / "scripts/run_g7_qualification.py"
    rule = {
        "version": 1,
        "adopt_requires_strict_capability_gain": True,
        "adopt_requires_parent_success_preservation": True,
        "adopt_requires_matched_candidate_budget": True,
        "adopt_requires_zero_external_model_calls": True,
        "ties_or_regressions": "reject",
    }
    rule_digest = digest_of(rule)
    evaluator_source_sha = _sha(evaluator_path)
    evaluator_digest = digest_of(
        {
            "kind": "external-python-exitcode-component-evaluator",
            "version": 1,
            "source_sha256": evaluator_source_sha,
            "candidate_budget_per_round": 4,
        }
    )
    authority_digest = digest_of(
        {
            "kind": "external-g7-promotion-authority",
            "version": 1,
            "rule_digest": rule_digest,
            "evaluator_digest": evaluator_digest,
            "mutable_lineage_owns_verdict": False,
        }
    )
    rollback_authority_digest = digest_of(
        {
            "kind": "external-g7-rollback-authority",
            "version": 1,
            "restore_policy": "exact_recorded_parent_only",
            "mutable_lineage_owns_verdict": False,
        }
    )
    rollback_challenge_digest = digest_of(
        {
            "kind": "g7-exact-rollback-challenge",
            "version": 1,
            "after_round": "B",
            "purpose": "prove exact parent restoration and replay",
        }
    )

    payload = {
        "schema": SCHEMA,
        "apparatus_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip(),
        "lineage_apparatus": {
            "path": "genesis/evolution/lineage_promotion.py",
            "source_sha256": _sha(lineage_path),
        },
        "external_evaluator": {
            "path": "scripts/run_g7_qualification.py",
            "source_sha256": evaluator_source_sha,
            "evaluator_digest": evaluator_digest,
            "mutable_lineage_owns_evaluator": False,
        },
        "authority": {
            "authority_digest": authority_digest,
            "rollback_authority_digest": rollback_authority_digest,
            "mutable_lineage_owns_verdict": False,
        },
        "decision_rule": {
            "rule": rule,
            "rule_digest": rule_digest,
            "candidate_budget_per_round": 4,
        },
        "candidate_set_digest": candidates["candidate_set_digest"],
        "candidate_identities": {
            "seed": candidates["seed"]["artifact_digest"],
            "D1": candidates["candidate_d1"]["artifact_digest"],
            "R1": candidates["candidate_reversion"]["artifact_digest"],
            "D2": candidates["candidate_d2"]["artifact_digest"],
        },
        "sequence": [
            {
                "step": "round_A",
                "parent": "seed",
                "candidate": "D1",
                "decision": "frozen_external_rule",
            },
            {
                "step": "round_B",
                "parent": "D1",
                "candidate": "R1",
                "decision": "frozen_external_rule",
            },
            {
                "step": "rollback",
                "from": "D1",
                "restore": "seed",
                "authority": "external_exact_parent_rollback",
            },
            {
                "step": "round_C",
                "parent": "seed",
                "candidate": "D2",
                "decision": "frozen_external_rule",
            },
        ],
        "rollback_challenge_digest": rollback_challenge_digest,
        "holdout": {
            "sha256": holdout_sha,
            "round_count": 3,
            "case_count": 12,
            "contents_visible_to_mutable_lineage_before_freeze": False,
            "location_at_freeze": "external_to_repository",
        },
        "qualification_rule": {
            "required": [
                "holdout_sha256_matches_preregistered_identity",
                "all_raw_holdout_cases_fail_before_repair",
                "all_candidates_are_isolated_before_decision",
                "round_A_is_adopted_by_frozen_rule",
                "round_B_regression_is_rejected_by_frozen_rule",
                "round_B_rejection_does_not_mutate_active_state",
                "external_rollback_restores_exact_A_parent",
                "restart_replay_succeeds_after_each_transition",
                "round_C_is_adopted_after_rollback",
                "final_active_artifact_is_D2",
                "lineage_generation_is_monotonic_and_expected",
                "artifact_tampering_is_rejected",
                "decision_tampering_is_rejected",
                "journal_tampering_is_rejected",
                "state_tampering_is_rejected",
                "all_measurements_use_zero_external_model_calls",
                "all_decisions_bind_frozen_authority_rule_and_evaluator",
            ],
            "pass_label": "G7_SCIENTIFIC_GATE_PASSED",
            "fail_label": "G7_SCIENTIFIC_GATE_OPEN",
        },
        "claim_boundary": (
            "Bounded project-defined G7 causal promotion/rollback qualification only. "
            "Passing does not establish G8, G9, recursive successor chains, general RSI, "
            "AGI, ASI, or independent third-party validation."
        ),
    }
    payload["preregistration_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
