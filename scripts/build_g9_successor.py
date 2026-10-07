"""Build and freeze a whole Genesis N -> N+1 proposal from prior qualified evidence only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from genesis.evolution import successor_generation
from genesis.trust_root import digest_of


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    parent = successor_generation.build_parent_profile(root)

    g6_result = json.loads((root / "experiment/g6_qualification/RESULT.json").read_text())
    g6_descendant = json.loads((root / "experiment/g6_qualification/DESCENDANT.json").read_text())
    g8_result = json.loads((root / "experiment/g8_qualification/RESULT.json").read_text())
    g8_freeze = json.loads((root / "experiment/g8_qualification/SPECIALIST.json").read_text())

    proposal = successor_generation.generate_successor(
        parent,
        g6_result=g6_result,
        g6_descendant=g6_descendant,
        g8_result=g8_result,
        g8_specialist_freeze=g8_freeze,
    )
    successor_generation.validate_proposal(proposal)

    g6_source = root / "experiment/g6_qualification/descendant/universal.py"
    g6_expected = proposal["successor_profile"]["active_overrides"]["universal_operator_ir"]["source_sha256"]
    if hashlib.sha256(g6_source.read_bytes()).hexdigest() != g6_expected:
        raise SystemExit("qualified G6 source bytes do not match generated successor")

    specialist_path = root / "experiment/g8_qualification/SPECIALIST.json"
    freeze_payload = json.loads(specialist_path.read_text())
    expected_specialist = proposal["successor_profile"]["active_overrides"]["local_repair_specialist"]["specialist_digest"]
    if freeze_payload["specialist"]["specialist_digest"] != expected_specialist:
        raise SystemExit("qualified G8 specialist does not match generated successor")

    payload = {
        "schema": "genesis-g9-successor-freeze-v1",
        "proposal": proposal,
        "proposal_digest": proposal["proposal_digest"],
        "parent_profile_digest": proposal["parent_profile"]["profile_digest"],
        "successor_profile_digest": proposal["successor_profile"]["profile_digest"],
        "qualified_artifact_bindings": {
            "g6_source_path": "experiment/g6_qualification/descendant/universal.py",
            "g6_source_sha256": g6_expected,
            "g8_specialist_path": "experiment/g8_qualification/SPECIALIST.json",
            "g8_specialist_digest": expected_specialist,
        },
        "prospective_g9_holdout_visible": False,
        "external_model_calls": 0,
    }
    payload["freeze_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
