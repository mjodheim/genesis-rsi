"""Contrôle hors réseau des résultats committés ; aucun rejeu expérimental."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = {
    "inherited_lineage",
    "frozen_engine",
    "fixed_procedure",
    "random_procedure",
}

def _document(name):
    """Lire un artefact canonique, sans importer ni lancer le moteur."""
    path = ROOT / "results" / name
    return json.loads(path.read_text(encoding="utf-8"))

def _count(value):
    if isinstance(value, list):
        return len(value)
    assert type(value) is int, f"Comptage invalide : {value!r}"
    return value

def test_committed_full_counts_and_closure():
    full = _document("circuit2_campaign_full.json")
    adjudication = _document("circuit2_adjudication_full.json")
    budget = _document("circuit2_budget16_stdout.json")
    assert set(full["arms"]) == ARMS

    expected_pairs = {(arm, seed) for arm in ARMS for seed in range(20)}
    observed_pairs = []
    transitions = 0
    changes = {"library_digest": 0, "procedure_digest": 0}
    for arm, entries in full["arms"].items():
        assert len(entries) == 20
        for entry in entries:
            assert type(entry["seed"]) is int
            observed_pairs.append((arm, entry["seed"]))
            generations = entry["generations"]
            assert len(generations) == 6
            assert all(type(gen["index"]) is int for gen in generations)
            assert sorted(gen["index"] for gen in generations) == list(range(6))
            generations = sorted(generations, key=lambda gen: gen["index"])
            for gen in generations:
                score = gen["score"]
                assert isinstance(score, list) and len(score) == 2
                assert type(score[1]) in (int, float)
                # score[1] n'est pas le rendement tenu à l'écart :
                # il vaut -137 dans l'extrait de campagne fourni.
            if arm == "inherited_lineage":
                for before, after in zip(generations, generations[1:]):
                    transitions += 1
                    for key in changes:
                        old = before["transmission"][key]
                        new = after["transmission"][key]
                        assert isinstance(old, str) and old
                        assert isinstance(new, str) and new
                        changes[key] += old != new
    assert len(observed_pairs) == 80
    assert len(set(observed_pairs)) == 80
    assert set(observed_pairs) == expected_pairs
    assert transitions == 100
    assert changes == {"library_digest": 0, "procedure_digest": 0}

    rows = adjudication["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 80
    adjudicated_pairs = []
    for row in rows:
        assert type(row["seed"]) is int
        adjudicated_pairs.append((row["arm"], row["seed"]))
        assert _count(row["generations"]) == 6
        assert type(row["held_out_yield"]) in (int, float)
        assert row["held_out_yield"] == 0
    assert len(set(adjudicated_pairs)) == 80
    assert set(adjudicated_pairs) == expected_pairs == set(observed_pairs)

    assert type(budget["parametres"]["budget"]) is int
    assert budget["parametres"]["budget"] == 16
    assert _count(budget["etape_a"]["candidates"]) == 2
    assert _count(budget["etape_a"]["admitted"]) == 0

    note = (ROOT / "docs/CIRCUIT2_CLOTURE_2026-11-13.md").read_text(encoding="utf-8")
    for statement in (
        "20 graines × 4 bras × 6 générations",
        "80 couples bras/graine exacts, avec rendement tenu à l'écart nul",
        "100 transitions héritées",
        "0 changement de library_digest",
        "0 changement de procedure_digest",
        "budget 16 : 2 candidats et 0 admis",
        "e2546a18",
        "capacité de programmation de Mira",
        "results/circuit2_campaign_full.json",
        "results/circuit2_adjudication_full.json",
        "results/circuit2_budget16_stdout.json",
        "l'amélioration de l'améliorateur n'est pas montrée",
    ):
        assert statement in note



