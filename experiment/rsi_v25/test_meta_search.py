"""Structural tests for the prospective V25 public meta-search."""
from __future__ import annotations

from meta_search import (
    PUBLIC_DEV_ROUNDS,
    development_utility,
    mechanism_ablation,
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


def test_ablation_removes_only_acquired_mechanism_back_to_frozen_root():
    selected = ExplorationMechanism(**select_successor()["selected_mechanism"])
    assert mechanism_ablation(selected) == ROOT
    assert development_utility(mechanism_ablation(selected)) == development_utility(ROOT)


def test_pre_holdout_gate_is_causal_and_does_not_consume_holdout():
    result = pre_holdout_gate()
    assert result["budget_check"] == "passed"
    assert result["causal_development_advantage"] is True
    assert result["pre_holdout_gate_passed"] is True
    assert result["holdout_consumed"] is False


def test_public_rounds_expose_only_frozen_observable_features():
    expected = {"candidate_id", "source_sha256", "quality_milli", "lineage_depth", "novelty"}
    assert PUBLIC_DEV_ROUNDS
    assert all(set(candidate) == expected for round_ in PUBLIC_DEV_ROUNDS for candidate in round_)
