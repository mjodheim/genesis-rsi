from __future__ import annotations

import hashlib
import json
from pathlib import Path

from genesis.evolution import lineage_promotion
from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]
QUAL = ROOT / "experiment" / "g7_qualification"


def _load(name: str) -> dict:
    return json.loads((QUAL / name).read_text(encoding="utf-8"))


def test_g7_preregistration_and_candidates_are_self_consistent() -> None:
    prereg = _load("PREREGISTRATION.json")
    candidates = _load("CANDIDATES.json")

    prereg_payload = dict(prereg)
    prereg_digest = prereg_payload.pop("preregistration_digest")
    candidate_payload = dict(candidates)
    candidate_digest = candidate_payload.pop("candidate_set_digest")

    assert digest_of(prereg_payload) == prereg_digest
    assert digest_of(candidate_payload) == candidate_digest
    assert prereg["candidate_set_digest"] == candidate_digest
    assert prereg["authority"]["mutable_lineage_owns_verdict"] is False
    assert prereg["external_evaluator"]["mutable_lineage_owns_evaluator"] is False
    assert candidates["hidden_g7_holdout_visible"] is False
    assert candidates["external_model_calls"] == 0


def test_g7_revealed_holdout_matches_frozen_identity() -> None:
    prereg = _load("PREREGISTRATION.json")
    holdout_path = QUAL / "HOLDOUT_REVEALED.json"
    sha = hashlib.sha256(holdout_path.read_bytes()).hexdigest()
    holdout = json.loads(holdout_path.read_text(encoding="utf-8"))

    assert sha == prereg["holdout"]["sha256"]
    assert len(holdout["rounds"]) == prereg["holdout"]["round_count"] == 3
    assert sum(len(item["cases"]) for item in holdout["rounds"]) == 12


def test_g7_result_reproduces_every_frozen_predicate() -> None:
    prereg = _load("PREREGISTRATION.json")
    candidates = _load("CANDIDATES.json")
    result = _load("RESULT.json")

    payload = dict(result)
    recorded = payload.pop("result_digest")

    assert digest_of(payload) == recorded
    assert result["preregistration_digest"] == prereg["preregistration_digest"]
    assert result["candidate_set_digest"] == candidates["candidate_set_digest"]
    assert result["verdict"] == "G7_SCIENTIFIC_GATE_PASSED"
    assert result["gate_passed"] is True
    assert all(result["requirements"].values())
    assert len(result["requirements"]) == len(prereg["qualification_rule"]["required"]) == 17

    assert result["decisions"]["A"]["decision"] == "adopt"
    assert result["decisions"]["B"]["decision"] == "reject"
    assert result["decisions"]["C"]["decision"] == "adopt"
    assert result["rejection_state_unchanged"] is True
    assert result["rollback_exact"] is True
    assert result["tamper_probes"] == {
        "artifact": True,
        "decision": True,
        "journal": True,
        "state": True,
    }
    assert result["external_model_calls"] == 0


def test_g7_measurements_show_accept_reject_accept_under_same_frozen_rule() -> None:
    result = _load("RESULT.json")

    assert result["measurements"]["A"]["parent"]["passed"] == 1
    assert result["measurements"]["A"]["candidate"]["passed"] == 4
    assert result["measurements"]["B"]["parent"]["passed"] == 4
    assert result["measurements"]["B"]["candidate"]["passed"] == 1
    assert result["measurements"]["C"]["parent"]["passed"] == 2
    assert result["measurements"]["C"]["candidate"]["passed"] == 4

    for round_id in ("A", "B", "C"):
        parent = result["measurements"][round_id]["parent"]
        candidate = result["measurements"][round_id]["candidate"]
        assert parent["candidate_budget"] == candidate["candidate_budget"] == 4
        assert parent["external_model_calls"] == candidate["external_model_calls"] == 0
        assert parent["evaluator_digest"] == candidate["evaluator_digest"]
        assert parent["case_set_digest"] == candidate["case_set_digest"]


def test_g7_persisted_lineage_store_replays_to_final_D2() -> None:
    candidates = _load("CANDIDATES.json")
    result = _load("RESULT.json")
    store = lineage_promotion.ComponentLineageStore.load(QUAL / "LINEAGE_STORE")

    assert store.state == result["final_state"]
    assert store.journal.head == result["final_journal_head"]
    assert store.state["generation"] == 3
    assert store.state["active_artifact_digest"] == candidates["candidate_d2"]["artifact_digest"]
    assert store.active_artifact()["source_sha256"] == candidates["candidate_d2"]["source_sha256"]

    kinds = [entry["kind"] for entry in store.journal.entries()]
    assert kinds == [
        "seed",
        "candidate_proposed",
        "candidate_accepted",
        "candidate_proposed",
        "candidate_rejected",
        "rollback",
        "candidate_proposed",
        "candidate_accepted",
    ]


def test_g7_decisions_bind_exact_frozen_authority_rule_and_evaluator() -> None:
    prereg = _load("PREREGISTRATION.json")
    result = _load("RESULT.json")

    for decision in result["decisions"].values():
        assert lineage_promotion.validate_decision(decision) == decision
        assert decision["authority_digest"] == prereg["authority"]["authority_digest"]
        assert decision["rule_digest"] == prereg["decision_rule"]["rule_digest"]
        assert decision["evaluator_digest"] == prereg["external_evaluator"]["evaluator_digest"]

    rollback = result["rollback"]
    assert lineage_promotion.validate_rollback(
        rollback,
        adoption_decision=result["decisions"]["A"],
    ) == rollback
    assert rollback["authority_digest"] == prereg["authority"]["rollback_authority_digest"]
    assert rollback["reason_evidence_digest"] == prereg["rollback_challenge_digest"]
