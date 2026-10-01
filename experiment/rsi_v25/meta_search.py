"""Prospective V25 meta-mechanism search over public development traces only.

This module is pre-holdout apparatus. It cannot read final holdout tasks or
outcomes and it has no adoption authority.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from controls import ExternalBudget, consume_budget
from exploration_grammar import ExplorationMechanism, ROOT, behaviorally_distinct, decision_trace, universe


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


# Public synthetic development rounds. They expose only the feature schema
# frozen by exploration_grammar; no evaluator secrets or holdout features.
PUBLIC_DEV_ROUNDS: tuple[tuple[dict[str, Any], ...], ...] = (
    (
        {"candidate_id": "root", "source_sha256": _sha("root"), "quality_milli": 700, "lineage_depth": 0, "novelty": 0},
        {"candidate_id": "novel-a", "source_sha256": _sha("novel-a"), "quality_milli": 690, "lineage_depth": 1, "novelty": 3},
        {"candidate_id": "quality-a", "source_sha256": _sha("quality-a"), "quality_milli": 780, "lineage_depth": 1, "novelty": 1},
    ),
    (
        {"candidate_id": "root-b", "source_sha256": _sha("root-b"), "quality_milli": 710, "lineage_depth": 0, "novelty": 0},
        {"candidate_id": "deep-b", "source_sha256": _sha("deep-b"), "quality_milli": 705, "lineage_depth": 2, "novelty": 1},
        {"candidate_id": "novel-b", "source_sha256": _sha("novel-b"), "quality_milli": 700, "lineage_depth": 1, "novelty": 4},
    ),
    (
        {"candidate_id": "root-c", "source_sha256": _sha("root-c"), "quality_milli": 720, "lineage_depth": 0, "novelty": 0},
        {"candidate_id": "balanced-c", "source_sha256": _sha("balanced-c"), "quality_milli": 750, "lineage_depth": 2, "novelty": 2},
        {"candidate_id": "novel-c", "source_sha256": _sha("novel-c"), "quality_milli": 715, "lineage_depth": 1, "novelty": 5},
    ),
)


def development_utility(mechanism: ExplorationMechanism) -> tuple[int, int, int]:
    trace = decision_trace(mechanism, PUBLIC_DEV_ROUNDS)
    selected = {row["selected_candidate_id"] for row in trace}
    quality = sum(
        int(candidate["quality_milli"])
        for candidates, record in zip(PUBLIC_DEV_ROUNDS, trace)
        for candidate in candidates
        if candidate["candidate_id"] == record["selected_candidate_id"]
    )
    distinct = len(selected)
    # Prefer public development quality first; diversity is only a tie-break.
    return quality, distinct, -sum(record["selected_index"] for record in trace)


def select_successor() -> dict[str, Any]:
    ExternalBudget().validate()
    candidates = tuple(universe())
    # Finite grammar enumeration is an offline public-development operation,
    # not a represented execution request. Bind its cardinality explicitly so
    # changing the search space requires a new prospective apparatus version.
    expected_cardinality = 27
    if len(candidates) != expected_cardinality:
        raise RuntimeError("V25 frozen mechanism grammar cardinality changed")
    ranked = sorted(
        ((development_utility(mechanism), mechanism.digest(), mechanism) for mechanism in candidates),
        # Equal utility does not justify acquiring behaviorally silent parameters.
        # Prefer the smallest change before the content-addressed final tie-break.
        key=lambda row: (row[0], -acquired_component_count(row[2]), row[1]),
    )
    utility, _, selected = ranked[-1]
    root_utility = development_utility(ROOT)
    distinct = behaviorally_distinct(selected, ROOT, PUBLIC_DEV_ROUNDS)
    return {
        "schema": "mira-genesis-rsi-v25-public-meta-search-v1",
        "selected_mechanism": selected.payload(),
        "selected_mechanism_sha256": selected.digest(),
        "root_mechanism_sha256": ROOT.digest(),
        "selection_rule": "development-utility_then-fewest-acquired-components_then-digest",
        "selected_development_utility": utility,
        "root_development_utility": root_utility,
        "strict_public_improvement": utility > root_utility,
        "behaviorally_distinct_from_root": distinct,
        "selected_trace": decision_trace(selected, PUBLIC_DEV_ROUNDS),
        "root_trace": decision_trace(ROOT, PUBLIC_DEV_ROUNDS),
        "holdout_consumed": False,
    }


def acquired_component_count(mechanism: ExplorationMechanism) -> int:
    return sum((mechanism.strategy != ROOT.strategy,
                mechanism.novelty_weight != ROOT.novelty_weight,
                mechanism.depth_weight != ROOT.depth_weight))


def mechanism_ablations(selected: ExplorationMechanism) -> tuple[ExplorationMechanism, ...]:
    """Return matched single-component ablations of acquired mechanism changes."""
    selected.validate()
    variants = []
    if selected.strategy != ROOT.strategy:
        variants.append(ExplorationMechanism(ROOT.strategy, selected.novelty_weight, selected.depth_weight))
    if selected.novelty_weight != ROOT.novelty_weight:
        variants.append(ExplorationMechanism(selected.strategy, ROOT.novelty_weight, selected.depth_weight))
    if selected.depth_weight != ROOT.depth_weight:
        variants.append(ExplorationMechanism(selected.strategy, selected.novelty_weight, ROOT.depth_weight))
    return tuple(dict((item.digest(), item) for item in variants).values())


def pre_holdout_gate() -> dict[str, Any]:
    result = select_successor()
    selected = ExplorationMechanism(**result["selected_mechanism"])
    ablations = mechanism_ablations(selected)
    if not ablations:
        raise RuntimeError("selected successor has no acquired component to ablate")
    successor_utility = development_utility(selected)
    ablation_utilities = tuple(development_utility(item) for item in ablations)
    causal_advantage = all(successor_utility > utility for utility in ablation_utilities)
    # Execution counters are prospectively bounded and checked here rather
    # than merely documented. This apparatus uses one decision round per
    # frozen public round and no parallel expansion.
    consume_budget(
        requests=len(PUBLIC_DEV_ROUNDS),
        rounds=len(PUBLIC_DEV_ROUNDS),
        parallelism=1,
        depth=1,
    )
    passed = bool(
        result["strict_public_improvement"]
        and result["behaviorally_distinct_from_root"]
        and causal_advantage
    )
    return {
        **result,
        "mechanism_ablation_sha256": [item.digest() for item in ablations],
        "mechanism_ablation_development_utility": list(ablation_utilities),
        "causal_development_advantage": causal_advantage,
        "budget_check": "passed",
        "pre_holdout_gate_passed": passed,
        "gate_scope": "PUBLIC_DEVELOPMENT_MECHANISM_ONLY",
        "authorizes_fresh_holdout": False,
        "holdout_consumed": False,
    }
