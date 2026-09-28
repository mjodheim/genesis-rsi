"""Structural regressions for the prospective V24 L5 apparatus.

These tests deliberately do not evaluate the complete public candidate universe
and do not execute the four scientific meta-search arms. Full-universe bridge
validation belongs to the one-time prospective freeze step.
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V23 = ROOT / "experiment" / "rsi_v23"
V24 = ROOT / "experiment" / "rsi_v24"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


family = _load("test_v24_family", V23 / "l5_policy_family.py")
bridge = _load("test_v24_bridge", V24 / "semantic_quality_bridge.py")
search = _load("test_v24_search", V24 / "l5_meta_search.py")


def test_v24_root_remains_exact_frozen_g2():
    source = family.root_source()
    assert hashlib.sha256(source.encode()).hexdigest() == family.ROOT_SHA256


def test_v24_root_public_utility_is_bound_to_preserved_v23_observation():
    assert bridge.ROOT_DEVELOPMENT_UTILITY == (7, 12, 10970, -30, -30)
    assert bridge.root_utility() == bridge.ROOT_DEVELOPMENT_UTILITY


def test_v24_semantic_bridge_matches_exact_g2_threshold_regions():
    root = bridge.ROOT_DEVELOPMENT_UTILITY
    worse_a = (6, 12, 10000, -20, -20)
    worse_b = (7, 11, 12000, -10, -10)
    better_a = (8, 12, 11000, -40, -40)
    better_b = (9, 12, 12000, -50, -50)

    mapping = bridge.semantic_quality_map(
        (worse_a, worse_b, root, better_a, better_b)
    )

    assert 0 <= mapping[worse_a] <= bridge.PROMISING_MAX
    assert 0 <= mapping[worse_b] <= bridge.PROMISING_MAX
    assert mapping[root] == bridge.NEUTRAL_QUALITY
    assert bridge.STRONG_THRESHOLD <= mapping[better_a] <= bridge.MAX_QUALITY
    assert bridge.STRONG_THRESHOLD <= mapping[better_b] <= bridge.MAX_QUALITY


def test_v24_semantic_bridge_preserves_strict_order_inside_each_side_of_root():
    root = bridge.ROOT_DEVELOPMENT_UTILITY
    utilities = (
        (5, 12, 9000, -20, -20),
        (6, 12, 10000, -20, -20),
        root,
        (8, 12, 11000, -40, -40),
        (9, 12, 12000, -50, -50),
    )
    mapping = bridge.semantic_quality_map(utilities, root)

    worse = sorted(value for value in mapping if value < root)
    better = sorted(value for value in mapping if value > root)

    assert all(mapping[a] < mapping[b] for a, b in zip(worse, worse[1:]))
    assert all(mapping[a] < mapping[b] for a, b in zip(better, better[1:]))


def test_v24_semantic_bridge_requires_the_root_utility():
    with pytest.raises(ValueError, match="root utility must be present"):
        bridge.semantic_quality_map(((1, 2, 3),), bridge.ROOT_DEVELOPMENT_UTILITY)


def test_v24_exact_g2_strong_stop_boundary_is_not_rewritten():
    g2 = family.root_source()
    assert "if best >= 780:" in g2
    assert bridge.STRONG_THRESHOLD == 780
    assert bridge.PROMISING_MAX == 710
    assert bridge.NEUTRAL_QUALITY == 750


def test_v24_ablation_is_exact_g2_except_for_the_l4_validated_early_stop():
    g2 = family.root_source()
    ablated = search.g2_ablation_source()
    block = """    if best >= 780:
        return []

"""
    assert ablated == g2.replace(block, "")


def test_v24_equal_external_meta_budgets_remain_v23_sized():
    assert search.META_REQUEST_BUDGET == 9
    assert search.META_ROUND_BUDGET == 8
    assert search.META_MAX_PARALLELISM == 2
    assert search.META_MUTATION_DEPTH == 2


def test_v24_scientific_arms_are_guarded_by_the_committed_freeze():
    if search.FREEZE_PATH.exists():
        freeze = search.require_freeze(verify_semantic_map=False)
        assert freeze["status"] == "FROZEN_BEFORE_ANY_V24_META_SEARCH"
    else:
        with pytest.raises(RuntimeError, match="forbidden before V24_FREEZE.json"):
            search.require_freeze(verify_semantic_map=False)
