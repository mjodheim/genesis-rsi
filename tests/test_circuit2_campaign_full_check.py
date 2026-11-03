"""Contrôle en lecture seule de results/circuit2_campaign_full.json.

Hors réseau, sans modèle, aucune écriture, aucun accès à HELD_OUT.
Le test est ignoré (skip) si le fichier est absent.
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
FORBIDDEN = ("gain", "success", "yield", "succes", "succès")

pytestmark = pytest.mark.skipif(not FULL.exists(), reason="campagne complète absente")


@pytest.fixture(scope="module")
def data():
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


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 20


def test_descriptive_counts(data):
    # Calcul descriptif, sans jugement. Les valeurs exactes seront figées
    # après observation ; seuls les types entiers et les bornes 0 à 20
    # sont vérifiés. Des scores ou digests constants resteraient un
    # résultat négatif visible, pas un résultat favorable.
    summary = {}
    for arm, entries in data["arms"].items():
        score_differs = 0
        distinct = []
        for entry in entries:
            generations = entry["generations"]
            if generations[0]["score"] != generations[-1]["score"]:
                score_differs += 1
            distinct.append(len({g["digest"] for g in generations}))
        summary[arm] = {
            "seeds_score_differs": score_differs,
            "distinct_digests_per_seed": distinct,
        }
    for arm, values in summary.items():
        for key in values:
            assert not any(word in key.lower() for word in FORBIDDEN), key
        assert _is_count(values["seeds_score_differs"]), arm
        assert all(_is_count(n) for n in values["distinct_digests_per_seed"]), arm
