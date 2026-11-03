"""Contrôle en lecture seule de results/circuit2_campaign_full.json.

Hors réseau, sans modèle, aucune écriture, aucun accès à HELD_OUT.
L'absence du fichier fait échouer les tests.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "results" / "circuit2_campaign_full.json"

EXPECTED_ARMS = {"inherited_lineage", "frozen_engine", "fixed_procedure", "random_procedure"}
EXPECTED_SEEDS = list(range(20))
EXPECTED_GENERATIONS = 6
EXPECTED_PLAN_DIGEST = "d6ddfbe570364b0c8df9c46ae979547a61bda327a77ba3a1363a8e3493ac1ad4"
EXPECTED_MACHINERY_COMMITS = {"245661e0c8d0f2668f74a3f637f22141cae46fd1"}


@pytest.fixture(scope="module")
def data():
    assert FULL.exists(), "results/circuit2_campaign_full.json absent : le test doit échouer"
    with FULL.open(encoding="utf-8") as handle:
        return json.load(handle)


def _values_for_key(node, name):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == name:
                yield value
            yield from _values_for_key(value, name)
    elif isinstance(node, list):
        for item in node:
            yield from _values_for_key(item, name)


def _entries(data):
    for arm, entries in data["arms"].items():
        for entry in entries:
            yield arm, entry


def test_expected_arms(data):
    assert set(data["arms"]) == EXPECTED_ARMS
    assert len(data["arms"]) == 4


def test_seeds_per_arm(data):
    for arm, entries in data["arms"].items():
        seeds = [entry["seed"] for entry in entries]
        assert sorted(seeds) == EXPECTED_SEEDS, arm


def test_generation_structure(data):
    for arm, entry in _entries(data):
        label = (arm, entry["seed"])
        assert entry["generations_run"] == EXPECTED_GENERATIONS, label
        generations = entry["generations"]
        assert len(generations) == EXPECTED_GENERATIONS, label
        assert [g["index"] for g in generations] == list(range(EXPECTED_GENERATIONS)), label


def test_parent_chain(data):
    for arm, entry in _entries(data):
        generations = entry["generations"]
        label = (arm, entry["seed"])
        assert generations[0]["parent"] is None, label
        for previous, current in zip(generations, generations[1:]):
            assert current["parent"] == previous["transmission"]["digest"], label


def test_plan_digest(data):
    assert data["plan_digest"] == EXPECTED_PLAN_DIGEST


def test_machinery_commit(data):
    assert set(_values_for_key(data, "machinery_commit")) == EXPECTED_MACHINERY_COMMITS


def test_budget_accounting(data):
    for arm, entry in _entries(data):
        for generation in entry["generations"]:
            label = (arm, entry["seed"], generation["index"])
            spend = generation["spend"]
            total = spend["evaluations"] + spend["procedure"] + spend["synthesis"]
            assert generation["spent"] == total, label
            assert generation["spent"] <= generation["limit"], label


def test_total_generations(data):
    total = sum(len(entry["generations"]) for _, entry in _entries(data))
    assert total == 480, total  # 4 bras x 20 graines x 6 générations


def test_score_shape(data):
    for arm, entry in _entries(data):
        for generation in entry["generations"]:
            label = (arm, entry["seed"], generation["index"])
            score = generation["score"]
            assert isinstance(score, list) and len(score) == 2, label
            assert all(isinstance(v, int) and not isinstance(v, bool) for v in score), label


import copy


def _check_structure(d):
    """Contrôle pur de structure ; lève AssertionError en cas d'écart."""
    assert set(d["arms"]) == EXPECTED_ARMS, "bras inattendus"
    for arm, entries in d["arms"].items():
        seeds = sorted(entry["seed"] for entry in entries)
        assert seeds == EXPECTED_SEEDS, ("graines", arm)
        for entry in entries:
            label = (arm, entry["seed"])
            assert entry["generations_run"] == EXPECTED_GENERATIONS, label
            generations = entry["generations"]
            assert len(generations) == EXPECTED_GENERATIONS, label
            for generation in generations:
                assert "score" in generation, label
                assert "transmission" in generation, label


def test_check_structure_accepts_committed_data(data):
    _check_structure(data)


def test_check_structure_rejects_missing_arm(data):
    broken = copy.deepcopy(data)
    del broken["arms"]["frozen_engine"]
    with pytest.raises(AssertionError):
        _check_structure(broken)


def test_check_structure_rejects_missing_seed(data):
    broken = copy.deepcopy(data)
    broken["arms"]["inherited_lineage"].pop()
    with pytest.raises(AssertionError):
        _check_structure(broken)


def test_check_structure_rejects_truncated_generations(data):
    broken = copy.deepcopy(data)
    entry = broken["arms"]["fixed_procedure"][0]
    entry["generations"] = entry["generations"][:-1]
    with pytest.raises(AssertionError):
        _check_structure(broken)


def test_check_structure_rejects_missing_transmission(data):
    broken = copy.deepcopy(data)
    del broken["arms"]["random_procedure"][0]["generations"][0]["transmission"]
    with pytest.raises(AssertionError):
        _check_structure(broken)


def test_generation_keys(data):
    for arm, entry in _entries(data):
        for generation in entry["generations"]:
            label = (arm, entry["seed"], generation["index"])
            assert "score" in generation, label
            assert "transmission" in generation, label
