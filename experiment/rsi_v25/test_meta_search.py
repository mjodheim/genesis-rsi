"""Structural tests for the prospective V25 public meta-search."""
from __future__ import annotations

from meta_search import (
    PUBLIC_DEV_ROUNDS,
    development_utility,
    mechanism_ablations,
    pre_holdout_gate,
    select_successor,
)
from exploration_grammar import ExplorationMechanism, ROOT


def test_public_meta_search_is_deterministic_and_pre_holdout():
    a = select_successor()
    b = select_successor()
    assert a == b
    assert a["holdout_consumed"] is False
    assert a["selected_mechanism_sha256"] == b["selected_mechanism_sha256"]


def test_selected_mechanism_is_behaviorally_distinct_and_publicly_better():
    result = select_successor()
    assert result["strict_public_improvement"] is True
    assert result["behaviorally_distinct_from_root"] is True
    assert tuple(result["selected_development_utility"]) > tuple(result["root_development_utility"])


def test_ablations_remove_one_acquired_component_at_a_time():
    selected = ExplorationMechanism(**select_successor()["selected_mechanism"])
    ablations = mechanism_ablations(selected)
    assert ablations
    for ablated in ablations:
        changed = sum(
            (
                ablated.strategy != selected.strategy,
                ablated.novelty_weight != selected.novelty_weight,
                ablated.depth_weight != selected.depth_weight,
            )
        )
        assert changed == 1
        assert ablated != selected
    assert all(development_utility(selected) > development_utility(ablated) for ablated in ablations)


def test_pre_holdout_gate_is_causal_and_does_not_consume_holdout():
    result = pre_holdout_gate()
    assert result["budget_check"] == "passed"
    assert result["causal_development_advantage"] is True
    assert result["pre_holdout_gate_passed"] is True
    assert result["gate_scope"] == "PUBLIC_DEVELOPMENT_MECHANISM_ONLY"
    assert result["authorizes_fresh_holdout"] is False
    assert result["holdout_consumed"] is False


def test_public_rounds_expose_only_frozen_observable_features():
    expected = {"candidate_id", "source_sha256", "quality_milli", "lineage_depth", "novelty"}
    assert PUBLIC_DEV_ROUNDS
    assert all(set(candidate) == expected for round_ in PUBLIC_DEV_ROUNDS for candidate in round_)
