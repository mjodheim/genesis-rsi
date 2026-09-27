from __future__ import annotations

from types import SimpleNamespace

import pytest

from genesis import state as lineage_state
from genesis.cognitive_meta_mutation import apply_policy_mutation
from genesis.cognitive_policy_evolution import (
    CognitivePolicyEvolutionError,
    apply_external_policy_adoption,
    create_external_policy_adoption,
)
from genesis.cognitive_search import create_policy
from genesis.cognitive_search_controller import admit_seed_policy, bound_policy
from genesis.journal import Journal


def runtime():
    return SimpleNamespace(
        state=lineage_state.create_state(
            body_digest="body", components=[], vocabulary=[], tools=[], acquisitions=[], observations=[]
        ),
        journal=Journal(),
    )


def seed():
    return create_policy(
        mutation_kinds=["replace_primitive", "add_edge", "remove_edge"],
        primitive_order=["identity", "sum", "sink"],
        candidate_limit=8,
    )


def descendant(parent):
    return apply_policy_mutation(
        parent,
        {"kind": "swap_mutation_kinds", "left": 0, "right": 1},
        max_candidate_limit=16,
    )


def decision(parent, child, mutation, value="adopt"):
    return create_external_policy_adoption(
        parent_policy=parent,
        candidate_policy=child,
        mutation_record=mutation,
        decision=value,
        authority_digest="external-authority",
        rule_digest="prospective-rule",
    )


def test_lineage_mutation_machinery_evolves_only_after_external_adoption():
    genesis = runtime()
    parent = seed()
    admit_seed_policy(genesis, parent)
    child, mutation = descendant(parent)
    adoption = decision(parent, child, mutation)

    entry = apply_external_policy_adoption(
        genesis, child, mutation_record=mutation, adoption_record=adoption
    )

    assert bound_policy(genesis) == child
    assert entry["payload"]["kind"] == "cognitive_mutation_machinery"
    tool = next(tool for tool in genesis.state["tools"] if tool["name"] == "cognitive_architecture_search_policy")
    assert tool["provenance"]["class"] == "external"
    assert "authority_digest" not in tool
    assert "rule_digest" not in tool


def test_rejected_mutation_machinery_descendant_cannot_change_lineage():
    genesis = runtime()
    parent = seed()
    admit_seed_policy(genesis, parent)
    child, mutation = descendant(parent)
    before = genesis.state["state_digest"]
    with pytest.raises(CognitivePolicyEvolutionError, match="rejected"):
        apply_external_policy_adoption(
            genesis,
            child,
            mutation_record=mutation,
            adoption_record=decision(parent, child, mutation, "reject"),
        )
    assert genesis.state["state_digest"] == before


def test_external_adoption_must_bind_exact_held_parent_and_meta_mutation():
    genesis = runtime()
    parent = seed()
    admit_seed_policy(genesis, parent)
    child, mutation = descendant(parent)
    adoption = decision(parent, child, mutation)
    other_parent = create_policy(
        mutation_kinds=["add_edge", "replace_primitive", "remove_edge"],
        primitive_order=["identity", "sum", "sink"],
        candidate_limit=8,
    )
    other_child, other_mutation = descendant(other_parent)

    with pytest.raises(CognitivePolicyEvolutionError):
        apply_external_policy_adoption(
            genesis, other_child, mutation_record=other_mutation, adoption_record=adoption
        )
    assert bound_policy(genesis) == parent
