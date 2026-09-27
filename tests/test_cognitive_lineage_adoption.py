from __future__ import annotations

from types import SimpleNamespace

import pytest

from genesis import state as lineage_state
from genesis.cognitive_adoption import create_adoption_record, create_rollback_record
from genesis.cognitive_architecture import architecture_digest
from genesis.cognitive_lineage_adoption import (
    CognitiveLineageAdoptionError,
    admit_seed_architecture,
    apply_external_adoption,
    apply_external_rollback,
    held_architecture,
)
from genesis.cognitive_measurement import ExternalBudget, create_measurement
from genesis.journal import Journal


BUDGET = ExternalBudget(case_limit=1, max_node_executions_per_case=4)


def architecture(primitive: str):
    return {
        "schema": "genesis-cognitive-architecture-v1",
        "nodes": [{"id": "n", "primitive": primitive, "config": {}}],
        "edges": [],
        "inputs": ["n"],
        "outputs": ["n"],
    }


def runtime():
    state = lineage_state.create_state(
        body_digest="body", components=[], vocabulary=[], tools=[], acquisitions=[], observations=[]
    )
    return SimpleNamespace(state=state, journal=Journal())


def measurement(arch, passed):
    return create_measurement(
        architecture_digest=architecture_digest(arch),
        evaluator_digest="external-evaluator",
        case_set_digest="held-cases",
        budget=BUDGET,
        case_results=[{"case_digest": "case-a", "passed": passed, "node_executions": 1}],
        cpu_process_time_ns=1,
    )


def adoption(parent, child, *, decision="adopt"):
    return create_adoption_record(
        parent_measurement=measurement(parent, False),
        candidate_measurement=measurement(child, True),
        decision=decision,
        authority_digest="external-authority",
        rule_digest="prospective-rule",
        proposal_digest="proposal",
    )


def test_external_adoption_changes_only_the_exact_held_parent():
    genesis = runtime()
    parent, child = architecture("identity"), architecture("sum")
    assert admit_seed_architecture(genesis, parent)
    record = adoption(parent, child)

    entry = apply_external_adoption(genesis, child, adoption_record=record)

    assert architecture_digest(held_architecture(genesis)) == architecture_digest(child)
    assert entry["kind"] == "candidate_accepted"
    assert entry["payload"]["adoption_digest"] == record["adoption_digest"]
    held_tool = next(tool for tool in genesis.state["tools"] if tool["name"] == "cognitive_architecture")
    assert held_tool["provenance"]["class"] == "external"
    assert "measurement" not in held_tool
    assert "authority_digest" not in held_tool


def test_rejection_cannot_mutate_lineage():
    genesis = runtime()
    parent, child = architecture("identity"), architecture("sum")
    admit_seed_architecture(genesis, parent)
    before = genesis.state["state_digest"]

    with pytest.raises(CognitiveLineageAdoptionError, match="rejection"):
        apply_external_adoption(genesis, child, adoption_record=adoption(parent, child, decision="reject"))

    assert genesis.state["state_digest"] == before


def test_adoption_refuses_wrong_current_parent():
    genesis = runtime()
    actual, recorded_parent, child = (
        architecture("identity"),
        architecture("sink"),
        architecture("sum"),
    )
    admit_seed_architecture(genesis, actual)
    with pytest.raises(CognitiveLineageAdoptionError, match="another parent"):
        apply_external_adoption(genesis, child, adoption_record=adoption(recorded_parent, child))


def test_external_rollback_restores_exact_recorded_parent():
    genesis = runtime()
    parent, child = architecture("identity"), architecture("sum")
    admit_seed_architecture(genesis, parent)
    adopted = adoption(parent, child)
    apply_external_adoption(genesis, child, adoption_record=adopted)
    rollback = create_rollback_record(
        adoption_record=adopted,
        authority_digest="rollback-authority",
        reason_evidence_digest="regression-evidence",
    )

    entry = apply_external_rollback(
        genesis, parent, adoption_record=adopted, rollback_record=rollback
    )

    assert architecture_digest(held_architecture(genesis)) == architecture_digest(parent)
    assert entry["kind"] == "rollback"
    assert entry["payload"]["rollback_digest"] == rollback["rollback_digest"]


def test_rollback_refuses_seeded_candidate_from_unapplied_adoption():
    genesis = runtime()
    parent, child = architecture("identity"), architecture("sum")
    admit_seed_architecture(genesis, child)
    adopted = adoption(parent, child)
    rollback = create_rollback_record(
        adoption_record=adopted,
        authority_digest="rollback-authority",
        reason_evidence_digest="regression-evidence",
    )
    before = genesis.state["state_digest"]

    with pytest.raises(CognitiveLineageAdoptionError, match="installed"):
        apply_external_rollback(
            genesis, parent, adoption_record=adopted, rollback_record=rollback
        )

    assert genesis.state["state_digest"] == before
    assert architecture_digest(held_architecture(genesis)) == architecture_digest(child)


def test_rollback_refuses_same_candidate_installed_by_different_adoption():
    genesis = runtime()
    parent_a, parent_b, child = (
        architecture("identity"),
        architecture("sink"),
        architecture("sum"),
    )
    admit_seed_architecture(genesis, parent_b)
    actual_adoption = adoption(parent_b, child)
    apply_external_adoption(genesis, child, adoption_record=actual_adoption)

    unrelated_adoption = adoption(parent_a, child)
    unrelated_rollback = create_rollback_record(
        adoption_record=unrelated_adoption,
        authority_digest="rollback-authority",
        reason_evidence_digest="regression-evidence",
    )
    before = genesis.state["state_digest"]

    with pytest.raises(CognitiveLineageAdoptionError, match="installed"):
        apply_external_rollback(
            genesis,
            parent_a,
            adoption_record=unrelated_adoption,
            rollback_record=unrelated_rollback,
        )

    assert genesis.state["state_digest"] == before
    assert architecture_digest(held_architecture(genesis)) == architecture_digest(child)


def test_rollback_refuses_a_substitute_parent():
    genesis = runtime()
    parent, child, substitute = (
        architecture("identity"),
        architecture("sum"),
        architecture("sink"),
    )
    admit_seed_architecture(genesis, parent)
    adopted = adoption(parent, child)
    apply_external_adoption(genesis, child, adoption_record=adopted)
    rollback = create_rollback_record(
        adoption_record=adopted,
        authority_digest="rollback-authority",
        reason_evidence_digest="regression-evidence",
    )
    with pytest.raises(CognitiveLineageAdoptionError, match="exact recorded parent"):
        apply_external_rollback(
            genesis, substitute, adoption_record=adopted, rollback_record=rollback
        )
