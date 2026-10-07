"""Build the frozen candidate set used by the Genesis G7 qualification.

No G7 holdout content is consumed here. Candidates come only from already
revealed G5/G6 evidence and the frozen G6 component-evolution apparatus.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from genesis.evolution import component_evolution, lineage_promotion
from genesis.trust_root import digest_of

SCHEMA = "genesis-g7-candidate-set-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository_root.resolve()

    parent_source = (root / "genesis/operators/universal.py").read_text(encoding="utf-8")
    g6 = json.loads((root / "experiment/g6_qualification/DESCENDANT.json").read_text())
    g6_prereg = json.loads(
        (root / "experiment/g6_qualification/PREREGISTRATION.json").read_text()
    )
    g5_prereg = json.loads(
        (root / "experiment/g5_qualification/PREREGISTRATION.json").read_text()
    )
    operator = g5_prereg["source_capability"]["universal_operator"]

    if hashlib.sha256(parent_source.encode("utf-8")).hexdigest() != g6_prereg[
        "parent_component"
    ]["source_sha256"]:
        raise SystemExit("current parent source is not the frozen G6 parent")

    seed = lineage_promotion.create_source_artifact(
        component_id="universal_operator_ir",
        source_utf8=parent_source,
        source_path="genesis/operators/universal.py",
        parent_artifact_digest=None,
        producer="genesis-v2-seed",
        proposal_digest="seed:" + g6_prereg["parent_component"]["source_sha256"],
    )

    d1_source = str(g6["selection"]["selected_descendant"]["source_utf8"])
    d1 = lineage_promotion.create_source_artifact(
        component_id="universal_operator_ir",
        source_utf8=d1_source,
        source_path="genesis/operators/universal.py",
        parent_artifact_digest=seed["artifact_digest"],
        producer="genesis-component-evolution",
        proposal_digest=g6["descendant_record_digest"],
    )

    diagnosis = g6["selection"]["diagnosis"]
    descendants = component_evolution.generate_descendants(
        parent_source,
        operator=operator,
        diagnosis=diagnosis,
    )
    alternate = next(
        item
        for item in descendants
        if item["mutation_id"] == "drop_wildcard_identifier_anchors"
    )
    d2 = lineage_promotion.create_source_artifact(
        component_id="universal_operator_ir",
        source_utf8=str(alternate["source_utf8"]),
        source_path="genesis/operators/universal.py",
        parent_artifact_digest=seed["artifact_digest"],
        producer="genesis-component-evolution",
        proposal_digest=alternate["descendant_digest"],
    )

    reversion = lineage_promotion.create_source_artifact(
        component_id="universal_operator_ir",
        source_utf8=parent_source,
        source_path="genesis/operators/universal.py",
        parent_artifact_digest=d1["artifact_digest"],
        producer="genesis-component-evolution",
        proposal_digest=digest_of(
            {
                "kind": "exact_source_reversion_candidate",
                "from_artifact_digest": d1["artifact_digest"],
                "restore_source_sha256": seed["source_sha256"],
            }
        ),
    )

    payload = {
        "schema": SCHEMA,
        "hidden_g7_holdout_visible": False,
        "source_evidence": {
            "g6_descendant_record_digest": g6["descendant_record_digest"],
            "g6_preregistration_digest": g6_prereg["preregistration_digest"],
            "g6_training_only": True,
        },
        "seed": seed,
        "candidate_d1": d1,
        "candidate_reversion": reversion,
        "candidate_d2": d2,
        "candidate_roles": {
            "round_A": "candidate_d1",
            "round_B": "candidate_reversion",
            "round_C": "candidate_d2",
        },
        "external_model_calls": 0,
    }
    payload["candidate_set_digest"] = digest_of(payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
