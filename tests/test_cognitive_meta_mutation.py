from __future__ import annotations

import pytest

from genesis.cognitive_meta_mutation import CognitiveMetaMutationError, apply_policy_mutation, enumerate_policy_descendants
from genesis.cognitive_search import create_policy


def policy():
    return create_policy(
        mutation_kinds=["replace_primitive", "add_edge", "remove_edge"],
        primitive_order=["identity", "sum", "sink"],
        candidate_limit=8,
    )


def test_mutation_machinery_can_change_its_mutation_order_content_addressably():
    parent = policy()
    child, record = apply_policy_mutation(
        parent, {"kind": "swap_mutation_kinds", "left": 0, "right": 1}, max_candidate_limit=16
    )
    assert child["mutation_kinds"][:2] == ["add_edge", "replace_primitive"]
    assert child["parent_policy_digest"] == parent["policy_digest"]
    assert record["parent_policy_digest"] == parent["policy_digest"]
    assert record["child_policy_digest"] == child["policy_digest"]
    assert len(record["mutation_record_digest"]) == 64


def test_mutation_machinery_can_change_primitive_order():
    parent = policy()
    child, _ = apply_policy_mutation(
        parent, {"kind": "swap_primitives", "left": 0, "right": 2}, max_candidate_limit=16
    )
    assert child["primitive_order"] == ["sink", "sum", "identity"]


def test_mutation_machinery_cannot_widen_external_candidate_ceiling():
    parent = policy()
    with pytest.raises(CognitiveMetaMutationError, match="external admitted bounds"):
        apply_policy_mutation(
            parent, {"kind": "set_candidate_limit", "candidate_limit": 17}, max_candidate_limit=16
        )


def test_mutation_machinery_refuses_noop_or_unknown_mutations():
    parent = policy()
    with pytest.raises(CognitiveMetaMutationError, match="indices"):
        apply_policy_mutation(
            parent, {"kind": "swap_mutation_kinds", "left": 1, "right": 1}, max_candidate_limit=16
        )
    with pytest.raises(CognitiveMetaMutationError, match="unsupported"):
        apply_policy_mutation(parent, {"kind": "rewrite_evaluator"}, max_candidate_limit=16)


def test_meta_search_enumeration_is_deterministic_bounded_and_parent_linked():
    parent = policy()
    first = enumerate_policy_descendants(
        parent, max_candidate_limit=16, max_descendants=4
    )
    second = enumerate_policy_descendants(
        parent, max_candidate_limit=16, max_descendants=4
    )
    assert first == second
    assert len(first) == 4
    assert len({child["policy_digest"] for child, _ in first}) == 4
    assert all(child["parent_policy_digest"] == parent["policy_digest"] for child, _ in first)
    assert all(record["parent_policy_digest"] == parent["policy_digest"] for _, record in first)


def test_meta_search_descendant_ceiling_is_external_and_required():
    with pytest.raises(CognitiveMetaMutationError, match="descendant ceiling"):
        enumerate_policy_descendants(policy(), max_candidate_limit=16, max_descendants=0)
