"""Tests de scripts/circuit2_mutation_reachability.py (hors réseau, rapides)."""

import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "circuit2_mutation_reachability.py"

_spec = importlib.util.spec_from_file_location("circuit2_mutation_reachability", SCRIPT)
mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = mod
_spec.loader.exec_module(mod)

cp = mod.cp
SMALL_CALLS = 400


def dump(report):
    return json.dumps(report, sort_keys=True, ensure_ascii=False, default=str)


@pytest.fixture(scope="module")
def analysis():
    patch = pytest.MonkeyPatch()
    patch.setattr(mod, "MAX_CALLS", SMALL_CALLS)
    try:
        return mod.analyse()
    finally:
        patch.undo()


def test_cibles_chargees_depuis_le_json(analysis):
    _, state = analysis
    assert state["targets"]
    for target in state["targets"]:
        assert set(target["parametres"]) == set(mod.TARGET_PARAMS)
        assert not cp.run(state["seed"], target["vec"])[1]


def test_cible_deja_admise_leve_une_erreur(monkeypatch):
    monkeypatch.setattr(mod, "admits", lambda proc, vec: True)
    with pytest.raises(mod.ReachabilityError):
        mod.analyse()


def test_procedures_valides_et_distinctes(analysis):
    _, state = analysis
    entries = state["entries"]
    assert entries, "aucune procédure produite : test sans objet"
    digests = [e["digest"] for e in entries]
    assert len(set(digests)) == len(digests)
    assert state["seed_digest"] not in digests
    for e in entries:
        assert mod.is_valid(e["proc"])
        assert mod._digest_and_record(e["proc"])[0] == e["digest"]


def test_chemins_et_rejeu(analysis):
    _, state = analysis
    for e in state["entries"]:
        assert 1 <= len(e["path"]) <= 2
        assert len(e["path"]) == e["depth"]
        json.dumps(e["path"])
        rebuilt = mod.replay(state["seed"], e["path"])
        assert mod._digest_and_record(rebuilt)[0] == e["digest"]
        assert cp.to_record(rebuilt) == e["record"]


@pytest.mark.parametrize("cap", [1, 3, 7])
def test_plafond_appels(monkeypatch, cap):
    monkeypatch.setattr(mod, "MAX_CALLS", cap)
    counter = {"n": 0}
    original = cp.mutate

    def counting(proc, rng):
        counter["n"] += 1
        return original(proc, rng)

    monkeypatch.setattr(cp, "mutate", counting)
    report, state = mod.analyse()
    assert counter["n"] == state["calls"] == report["appels_total"]
    assert counter["n"] <= cap
    assert sum(lv["appels_utilises"] for lv in report["niveaux"]) == counter["n"]
    assert any(lv["mode"] == "échantillon" for lv in report["niveaux"])
    assert mod.NOTE_SAMPLE in dump(report)


def test_plafond_temps_nul(monkeypatch):
    monkeypatch.setattr(mod, "MAX_SECONDS", 0.0)
    report, state = mod.analyse()
    assert state["calls"] == 0
    assert state["entries"] == []
    assert all(lv["mode"] == "échantillon" for lv in report["niveaux"])
    assert report["niveaux"][0]["bornes_atteintes"]["temps"] is True
    text = dump(report)
    assert mod.NOTE_SAMPLE in text
    assert mod.NOTE_NO_WITNESS_SAMPLE in text
    assert report["conclusion"] == mod.NOTE_NO_WITNESS_SAMPLE


def test_plafond_temoins_par_categorie():
    cat = mod._category(list(range(50)))
    assert cat["total"] == 50
    assert cat["affiches"] == 20
    assert len(cat["liste"]) == 20


def test_reevaluation_directe_des_temoins(analysis):
    report, state = analysis
    seed = state["seed"]
    vecs = {t["nom"]: t["vec"] for t in mod.load_targets()}
    reference = state["reference"]
    assert all(cp.run(seed, vec)[1] for vec in reference)
    for name, cat in report["temoins"].items():
        assert cat["affiches"] == len(cat["liste"]) <= 20
        assert cat["total"] >= cat["affiches"]
        for w in cat["liste"]:
            proc = mod.replay(seed, w["chemin"])
            assert w["profondeur"] == len(w["chemin"])
            assert cp.run(proc, vecs[name])[1]
    for name, cat in report["temoins_conservateurs"].items():
        for w in cat["liste"]:
            proc = mod.replay(seed, w["chemin"])
            assert cp.run(proc, vecs[name])[1]
            assert all(cp.run(proc, vec)[1] for vec in reference)


def test_bande_explore_tous_les_choix():
    ctl = mod.Budget(10_000, time.monotonic() + 60)
    leaves = []

    def fn(rng):
        return (rng.randrange(3), rng.choice(["a", "b"]))

    complete = mod.explore_exhaustive(
        fn, ctl, None, None, lambda ch, res: leaves.append((tuple(ch), res))
    )
    assert complete
    assert ctl.calls == 6
    assert len({path for path, _ in leaves}) == 6
    assert {res for _, res in leaves} == {(i, c) for i in range(3) for c in "ab"}


def test_bande_branches_dependantes():
    ctl = mod.Budget(10_000, time.monotonic() + 60)
    results = []

    def fn(rng):
        i = rng.randrange(3)
        return (i, rng.choice(list(range(i + 1))))

    complete = mod.explore_exhaustive(
        fn, ctl, None, None, lambda ch, res: results.append(res)
    )
    assert complete
    assert ctl.calls == 6
    assert sorted(results) == [(0, 0), (1, 0), (1, 1), (2, 0), (2, 1), (2, 2)]


def test_bande_plafond_interrompt():
    ctl = mod.Budget(4, time.monotonic() + 60)
    leaves = []
    complete = mod.explore_exhaustive(
        lambda rng: rng.randrange(10), ctl, None, None, lambda ch, res: leaves.append(res)
    )
    assert not complete
    assert ctl.calls == 4
    assert ctl.hit_calls
    assert len(leaves) == 4


def test_bande_rejoue_prefixe_et_randrange_borne():
    rng = mod.BandRNG([2, 1])
    assert rng.randrange(2, 5) == 4
    assert rng.choice(["x", "y"]) == "y"
    assert rng.trace == [(2, 3), (1, 2)]


def test_out_refuse_ecrasement_et_hors_results(monkeypatch, tmp_path):
    results = tmp_path / "results"
    results.mkdir()
    monkeypatch.setattr(mod, "RESULTS_DIR", results)
    monkeypatch.setattr(mod, "MAX_CALLS", 3)
    existing = results / "deja.json"
    existing.write_text("ancien", encoding="utf-8")
    assert mod.main(["--out", str(existing)]) == 1
    assert existing.read_text(encoding="utf-8") == "ancien"
    outside = tmp_path / "hors.json"
    assert mod.main(["--out", str(outside)]) == 1
    assert not outside.exists()
    traversal = results / ".." / "hors2.json"
    assert mod.main(["--out", str(traversal)]) == 1
    assert not (tmp_path / "hors2.json").exists()
    new = results / "nouveau.json"
    assert mod.main(["--out", str(new)]) == 0
    assert json.loads(new.read_text(encoding="utf-8"))["schema"] == mod.SCHEMA
    assert mod.main(["--out", str(new)]) == 1


def test_stdout_json_valide(monkeypatch, capsys):
    monkeypatch.setattr(mod, "MAX_CALLS", 3)
    assert mod.main([]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == mod.SCHEMA


def test_determinisme_plafonds_reduits(monkeypatch):
    monkeypatch.setattr(mod, "MAX_CALLS", 150)
    assert dump(mod.build_report()) == dump(mod.build_report())


def test_determinisme_temps_nul(monkeypatch):
    monkeypatch.setattr(mod, "MAX_SECONDS", 0.0)
    assert dump(mod.build_report()) == dump(mod.build_report())
