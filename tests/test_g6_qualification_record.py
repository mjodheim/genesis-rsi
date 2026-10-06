from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "experiment" / "g6_qualification"


def _load(name: str) -> dict:
    return json.loads((QUAL / name).read_text(encoding="utf-8"))


def test_g6_preregistration_is_self_consistent() -> None:
    prereg = _load("PREREGISTRATION.json")
    recorded = prereg["preregistration_digest"]
    payload = dict(prereg)
    payload.pop("preregistration_digest")

    assert digest_of(payload) == recorded
    assert prereg["holdout"]["contents_visible_to_lineage_before_descendant_freeze"] is False
    assert prereg["evolution_apparatus"]["external_model_calls"] == 0


def test_g6_descendant_was_material_and_frozen_before_reveal() -> None:
    prereg = _load("PREREGISTRATION.json")
    descendant = _load("DESCENDANT.json")
    source_path = QUAL / "descendant" / "universal.py"
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()

    assert descendant["preregistration_digest"] == prereg["preregistration_digest"]
    assert descendant["hidden_holdout_visible"] is False
    assert descendant["external_model_calls"] == 0
    assert descendant["selected_source_sha256"] == source_sha
    assert descendant["selected_source_sha256"] != prereg["parent_component"]["source_sha256"]
    assert descendant["selection"]["training_evidence_only"] is True
    assert descendant["selection"]["selected_descendant"]["mutation_id"] == "structural_delimiter_anchors"


def test_g6_revealed_holdout_matches_preregistered_identity() -> None:
    prereg = _load("PREREGISTRATION.json")
    holdout_path = QUAL / "HOLDOUT_REVEALED.json"
    sha = hashlib.sha256(holdout_path.read_bytes()).hexdigest()
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))

    assert sha == prereg["holdout"]["sha256"]
    assert len(holdout["cases"]) == prereg["holdout"]["case_count"] == 8


def test_g6_qualification_result_reproduces_frozen_gate() -> None:
    prereg = _load("PREREGISTRATION.json")
    result = _load("RESULT.json")
    descendant = _load("DESCENDANT.json")

    recorded = result["result_digest"]
    payload = dict(result)
    payload.pop("result_digest")

    assert digest_of(payload) == recorded
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert result["descendant_record_digest"] == descendant["descendant_record_digest"]
    assert result["verdict"] == "G6_SCIENTIFIC_GATE_PASSED"
    assert result["gate_passed"] is True
    assert all(result["requirements"].values())
    assert result["parent"]["solved"] == 2
    assert result["descendant"]["solved"] == 8
    assert result["descendant"]["case_count"] == 8
    assert result["descendant"]["external_model_calls"] == 0
    assert result["descendant"]["candidate_executions"] <= 8
    assert result["selected_mutation_id"] == "structural_delimiter_anchors"
    assert result["parent_source_sha256"] != result["descendant_source_sha256"]
