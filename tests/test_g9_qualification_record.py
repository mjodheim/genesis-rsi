from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesis.evolution import successor_generation
from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "experiment" / "g9_qualification"


def _load(name: str) -> dict:
    return json.loads((QUAL / name).read_text(encoding="utf-8"))


def test_g9_successor_freeze_is_content_addressed_and_pre_holdout() -> None:
    freeze = _load("SUCCESSOR.json")
    payload = dict(freeze)
    recorded = payload.pop("freeze_digest")

    assert digest_of(payload) == recorded
    proposal = successor_generation.validate_proposal(freeze["proposal"])
    assert proposal["proposal_digest"] == freeze["proposal_digest"]
    assert freeze["prospective_g9_holdout_visible"] is False
    assert freeze["external_model_calls"] == 0
    assert proposal["material_change_count"] == 3
    assert [item["component_id"] for item in proposal["material_changes"]] == [
        "universal_operator_ir",
        "local_repair_specialist",
        "candidate_router",
    ]
    assert proposal["lineage_produced"] is True
    assert proposal["mutable_lineage_owns_verdict"] is False


def test_g9_preregistration_reproduces() -> None:
    prereg = _load("PREREGISTRATION.json")
    payload = dict(prereg)
    recorded = payload.pop("preregistration_digest")

    assert digest_of(payload) == recorded
    assert prereg["holdout"]["contents_visible_to_lineage_at_freeze"] is False
    assert prereg["resource_budget"]["candidate_executions_per_case"] == 4
    assert prereg["resource_budget"]["external_model_calls_per_case"] == 0
    assert len(prereg["qualification_rule"]["required"]) == 21


def test_g9_revealed_holdout_and_seed_match_frozen_commitments() -> None:
    prereg = _load("PREREGISTRATION.json")
    holdout_path = QUAL / "HOLDOUT_REVEALED.json"
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    seed = (QUAL / "SEED_REVEALED.txt").read_text(encoding="utf-8").strip()

    assert hashlib.sha256(holdout_path.read_bytes()).hexdigest() == prereg["holdout"]["sha256"]
    assert hashlib.sha256(seed.encode("utf-8")).hexdigest() == holdout["seed_commitment"]
    assert holdout["case_count"] == 12
    assert holdout["group_counts"] == {
        "parent_retention": 4,
        "g6_component_gain": 4,
        "g8_specialist_gain": 4,
    }


def test_g9_result_passes_every_frozen_predicate() -> None:
    prereg = _load("PREREGISTRATION.json")
    result = _load("RESULT.json")
    payload = dict(result)
    recorded = payload.pop("result_digest")

    assert digest_of(payload) == recorded
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert result["verdict"] == "G9_SCIENTIFIC_GATE_PASSED"
    assert result["gate_passed"] is True
    assert len(result["requirements"]) == 21
    assert set(result["requirements"]) == set(prereg["qualification_rule"]["required"])
    assert all(result["requirements"].values())


def test_g9_parent_successor_and_ablations_decompose_gain() -> None:
    result = _load("RESULT.json")
    parent = result["parent"]
    successor = result["successor"]
    no_g6 = result["without_g6_ablation"]
    no_g8 = result["without_g8_ablation"]

    assert parent["solved"] == 4
    assert parent["group_solved"] == {
        "parent_retention": 4,
        "g6_component_gain": 0,
        "g8_specialist_gain": 0,
    }

    assert successor["solved"] == 12
    assert successor["group_solved"] == {
        "parent_retention": 4,
        "g6_component_gain": 4,
        "g8_specialist_gain": 4,
    }

    assert no_g6["solved"] == 8
    assert no_g6["group_solved"] == {
        "parent_retention": 4,
        "g6_component_gain": 0,
        "g8_specialist_gain": 4,
    }

    assert no_g8["solved"] == 8
    assert no_g8["group_solved"] == {
        "parent_retention": 4,
        "g6_component_gain": 4,
        "g8_specialist_gain": 0,
    }


def test_g9_retains_parent_successes_and_uses_matched_zero_model_budget() -> None:
    result = _load("RESULT.json")
    parent_pass = {
        case["case_id"] for case in result["parent"]["cases"] if case["passed"]
    }
    successor_pass = {
        case["case_id"] for case in result["successor"]["cases"] if case["passed"]
    }

    assert parent_pass <= successor_pass
    for key in ("parent", "successor", "without_g6_ablation", "without_g8_ablation"):
        arm = result[key]
        assert arm["candidate_budget_per_case"] == 4
        assert arm["candidate_budget_total"] == 48
        assert arm["within_candidate_budget"] is True
        assert arm["external_model_calls"] == 0
        assert "controller_cpu_process_time_ns" in arm
        assert "wall_time_seconds" in arm
