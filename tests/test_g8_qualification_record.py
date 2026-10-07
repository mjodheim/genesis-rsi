from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesis.learning import distillation
from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "experiment" / "g8_qualification"


def _load(name: str) -> dict:
    return json.loads((QUAL / name).read_text(encoding="utf-8"))


def test_g8_specialist_freeze_is_content_addressed_and_pre_holdout() -> None:
    freeze = _load("SPECIALIST.json")
    payload = dict(freeze)
    recorded = payload.pop("freeze_digest")

    assert digest_of(payload) == recorded
    assert freeze["hidden_g8_holdout_visible"] is False
    assert freeze["external_model_calls_for_distillation"] == 0

    specialist = distillation.validate_specialist(freeze["specialist"])
    assert specialist["template_count"] == 6
    assert specialist["source_external_model_calls"] == 5
    assert specialist["source_cost_usd"] == 0.474032
    assert specialist["runtime_external_model_calls"] == 0
    assert [row["task_id"] for row in specialist["distilled_from"]] == [1, 4, 6, 7, 11]


def test_g8_preregistration_reproduces() -> None:
    prereg = _load("PREREGISTRATION.json")
    payload = dict(prereg)
    recorded = payload.pop("preregistration_digest")

    assert digest_of(payload) == recorded
    assert prereg["holdout"]["contents_visible_to_specialist_at_freeze"] is False
    assert prereg["external_baseline"]["invocations_per_case"] == 1
    assert prereg["local_specialist"]["external_model_calls"] == 0
    assert len(prereg["qualification_rule"]["required"]) == 17


def test_g8_revealed_holdout_and_seed_match_frozen_commitments() -> None:
    prereg = _load("PREREGISTRATION.json")
    holdout_path = QUAL / "HOLDOUT_REVEALED.json"
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))
    seed = (QUAL / "SEED_REVEALED.txt").read_text(encoding="utf-8").strip()

    assert hashlib.sha256(holdout_path.read_bytes()).hexdigest() == prereg["holdout"]["sha256"]
    assert hashlib.sha256(seed.encode("utf-8")).hexdigest() == holdout["seed_commitment"]
    assert holdout["case_count"] == 8
    assert len(holdout["families"]) == 4


def test_g8_result_passes_every_frozen_predicate() -> None:
    prereg = _load("PREREGISTRATION.json")
    result = _load("RESULT.json")
    payload = dict(result)
    recorded = payload.pop("result_digest")

    assert digest_of(payload) == recorded
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert result["verdict"] == "G8_SCIENTIFIC_GATE_PASSED"
    assert result["gate_passed"] is True
    assert len(result["requirements"]) == 17
    assert set(result["requirements"]) == set(prereg["qualification_rule"]["required"])
    assert all(result["requirements"].values())


def test_g8_fresh_efficiency_comparison_and_ablation() -> None:
    result = _load("RESULT.json")
    external = result["external_baseline"]["aggregate"]
    local = result["local_specialist"]["aggregate"]
    ablated = result["empty_specialist_ablation"]["aggregate"]

    assert external["solved"] == 7
    assert external["case_count"] == 8
    assert external["external_model_calls"] == 8
    assert external["external_model_calls_per_solved_task"] > 1.0
    assert external["cost_usd"] == 0.23002640000000002
    assert external["cost_usd_per_solved_task"] > 0

    assert local["solved"] == 8
    assert local["external_model_calls"] == 0
    assert local["external_model_calls_per_solved_task"] == 0.0
    assert local["cost_usd"] == 0.0
    assert local["wall_time_seconds_per_solved_task"] < external["wall_time_seconds_per_solved_task"]

    assert ablated["solved"] == 0
    assert all(case["candidate_executions"] == 1 for case in result["local_specialist"]["cases"])


def test_g8_external_baseline_format_miss_is_not_needed_for_efficiency_claim() -> None:
    result = _load("RESULT.json")
    misses = [case for case in result["external_baseline"]["cases"] if not case["passed"]]

    assert len(misses) == 1
    miss = misses[0]
    assert miss["case_id"] == "rust-boundary-1"
    assert miss["structured_output"]["edits"][0]["new"].find(">=") >= 0
    assert miss["apply_error"] == "edit targets a file outside the frozen task"

    # Even under the conservative counterfactual that credits this semantically
    # correct proposal, the external arm would be 8/8 but still use 8 calls and
    # positive dollar cost versus local 8/8 with 0 calls and 0 dollars.
    external = result["external_baseline"]["aggregate"]
    local = result["local_specialist"]["aggregate"]
    hypothetical_external_calls_per_solved = external["external_model_calls"] / 8
    hypothetical_external_cost_per_solved = external["cost_usd"] / 8

    assert hypothetical_external_calls_per_solved == 1.0
    assert hypothetical_external_calls_per_solved > local["external_model_calls_per_solved_task"]
    assert hypothetical_external_cost_per_solved > local["cost_usd_per_solved_task"]
