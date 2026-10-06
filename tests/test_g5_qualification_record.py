from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesis.evolution import experiment_design
from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "experiment" / "g5_qualification"


def _load(name: str) -> dict:
    return json.loads((QUAL / name).read_text(encoding="utf-8"))


def test_g5_preregistration_is_self_consistent() -> None:
    prereg = _load("PREREGISTRATION.json")
    recorded = prereg["preregistration_digest"]
    payload = dict(prereg)
    payload.pop("preregistration_digest")

    assert digest_of(payload) == recorded
    assert prereg["holdout"]["contents_visible_to_mutable_lineage"] is False
    assert prereg["g5_plan"]["fresh_case_contents_visible_to_lineage"] is False
    assert prereg["g5_plan"]["mutable_lineage_owns_verdict"] is False
    assert experiment_design.validate_plan(prereg["g5_plan"]) == prereg["g5_plan"]


def test_g5_revealed_holdout_matches_frozen_identity() -> None:
    prereg = _load("PREREGISTRATION.json")
    holdout_path = QUAL / "HOLDOUT_REVEALED.json"
    sha = hashlib.sha256(holdout_path.read_bytes()).hexdigest()

    assert sha == prereg["holdout"]["sha256"]
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    assert len(holdout["cases"]) == prereg["holdout"]["case_count"] == 6


def test_g5_qualification_result_reproduces_frozen_gate() -> None:
    prereg = _load("PREREGISTRATION.json")
    result = _load("RESULT.json")

    recorded = result["result_digest"]
    payload = dict(result)
    payload.pop("result_digest")

    assert digest_of(payload) == recorded
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert result["verdict"] == "G5_SCIENTIFIC_GATE_PASSED"
    assert result["gate_passed"] is True
    assert all(result["requirements"].values())

    control = next(
        arm for arm in result["arms"]
        if arm["arm_name"] == "control-parent"
    )
    best = result["best_candidate"]
    ablation = result["ablation"]

    assert control["solved"] == 0
    assert best["component_id"] == "universal_operator_ir"
    assert best["solved"] == 5
    assert best["case_count"] == 6
    assert best["external_model_calls"] == 0
    assert best["candidate_executions"] <= 6
    assert ablation["solved"] == 0
    assert result["winning_component"] == "universal_operator_ir"
    assert result["external_model_calls"] == 0
