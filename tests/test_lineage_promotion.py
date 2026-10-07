from __future__ import annotations

import json

import pytest

from genesis.evolution import lineage_promotion as promotion


def artifact(
    source: str,
    *,
    parent: str | None = None,
    proposal: str = "proposal",
) -> dict:
    return promotion.create_source_artifact(
        component_id="universal_operator_ir",
        source_utf8=source,
        source_path="genesis/operators/universal.py",
        parent_artifact_digest=parent,
        producer="genesis-component-evolution",
        proposal_digest=proposal,
    )


def decision(parent: dict, child: dict, *, verdict: str = "adopt", suffix: str = "a") -> dict:
    return promotion.create_external_decision(
        parent_artifact=parent,
        candidate_artifact=child,
        decision=verdict,
        authority_digest="authority-" + suffix,
        rule_digest="rule-v1",
        evaluator_digest="evaluator-" + suffix,
        case_set_digest="cases-" + suffix,
        parent_measurement_digest="parent-measurement-" + suffix,
        candidate_measurement_digest="candidate-measurement-" + suffix,
        ablation_evidence_digest="ablation-" + suffix,
    )


def test_g7_candidate_is_isolated_until_external_adoption(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    child = artifact(
        "CHILD\n",
        parent=parent["artifact_digest"],
        proposal="child-proposal",
    )

    before = store.state["state_digest"]
    store.stage_candidate(child)

    assert store.state["active_artifact_digest"] == parent["artifact_digest"]
    assert store.state["state_digest"] == before

    adopted = decision(parent, child, verdict="adopt")
    entry = store.apply_external_decision(adopted)

    assert entry["kind"] == "candidate_accepted"
    assert store.state["active_artifact_digest"] == child["artifact_digest"]
    assert store.state["generation"] == 1
    assert store.active_artifact()["source_utf8"] == "CHILD\n"

    reloaded = promotion.ComponentLineageStore.load(tmp_path / "lineage")
    assert reloaded.state == store.state
    assert reloaded.journal.head == store.journal.head
    assert reloaded.active_artifact()["artifact_digest"] == child["artifact_digest"]


def test_g7_rejection_is_first_class_history_but_does_not_mutate_active_state(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    child = artifact("LOSER\n", parent=parent["artifact_digest"], proposal="loser")
    store.stage_candidate(child)

    before = dict(store.state)
    rejected = decision(parent, child, verdict="reject")
    entry = store.apply_external_decision(rejected)

    assert entry["kind"] == "candidate_rejected"
    assert store.state == before
    assert len(store.journal.of_kind("candidate_rejected")) == 1

    reloaded = promotion.ComponentLineageStore.load(tmp_path / "lineage")
    assert reloaded.state == before


def test_g7_rollback_restores_exact_parent_and_replay_survives_restart(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    child = artifact("CHILD\n", parent=parent["artifact_digest"], proposal="child")
    store.stage_candidate(child)
    adopted = decision(parent, child, verdict="adopt")
    store.apply_external_decision(adopted)

    rollback = promotion.create_external_rollback(
        adoption_decision=adopted,
        authority_digest="rollback-authority",
        reason_evidence_digest="rollback-challenge",
    )
    entry = store.apply_external_rollback(
        rollback,
        adoption_decision=adopted,
    )

    assert entry["kind"] == "rollback"
    assert store.state["active_artifact_digest"] == parent["artifact_digest"]
    assert store.state["generation"] == 2
    assert store.active_artifact()["source_utf8"] == "PARENT\n"

    reloaded = promotion.ComponentLineageStore.load(tmp_path / "lineage")
    assert reloaded.state["active_artifact_digest"] == parent["artifact_digest"]
    assert reloaded.state["generation"] == 2


def test_g7_refuses_decision_for_another_active_parent(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    child = artifact("CHILD\n", parent=parent["artifact_digest"], proposal="child")
    store.stage_candidate(child)
    adopted = decision(parent, child)
    store.apply_external_decision(adopted)

    stale = artifact("STALE\n", parent=parent["artifact_digest"], proposal="stale")
    # Stage is already refused because isolation binds a candidate to the active parent.
    with pytest.raises(promotion.LineagePromotionError, match="active artifact"):
        store.stage_candidate(stale)


def test_g7_detects_artifact_tampering_on_reload(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    path = store.artifacts_dir / f"{parent['artifact_digest']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["source_utf8"] = "TAMPERED\n"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(promotion.LineagePromotionError, match="artifact"):
        promotion.ComponentLineageStore.load(tmp_path / "lineage")


def test_g7_detects_decision_tampering_on_replay(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    child = artifact("CHILD\n", parent=parent["artifact_digest"], proposal="child")
    store.stage_candidate(child)
    adopted = decision(parent, child)
    store.apply_external_decision(adopted)

    path = store.decisions_dir / f"{adopted['decision_digest']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["case_set_digest"] = "substitute"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(promotion.LineagePromotionError, match="decision"):
        promotion.ComponentLineageStore.load(tmp_path / "lineage")


def test_g7_detects_journal_tampering_on_reload(tmp_path) -> None:
    parent = artifact("PARENT\n")
    store = promotion.ComponentLineageStore.initialize(tmp_path / "lineage", seed_artifact=parent)
    raw = json.loads(store.journal_path.read_text(encoding="utf-8"))
    raw["entries"][0]["payload"]["artifact_digest"] = "0" * 64
    store.journal_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(promotion.LineagePromotionError, match="cannot be loaded"):
        promotion.ComponentLineageStore.load(tmp_path / "lineage")
