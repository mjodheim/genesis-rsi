"""Contrôles hors réseau du diagnostic d'admission de la lignée CIRCUIT2."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

try:
    import diagnose_circuit2_lineage_admission as diag
except ImportError:
    from scripts import diagnose_circuit2_lineage_admission as diag

from genesis import circuit_engine as engine

LIVENESS_JSON = Path(__file__).resolve().parent.parent / "results" / "circuit2_lineage_liveness.json"
SCORE_KEYS = (
    "adopted",
    "adoption_stricte_explique_absence",
    "candidats",
    "candidats_strictement_meilleurs",
    "parent",
    "scores_tous_egaux",
)


def _sha():
    return hashlib.sha256(LIVENESS_JSON.read_bytes()).hexdigest() if LIVENESS_JSON.exists() else None


@pytest.fixture(scope="module")
def replayed():
    original, before = engine.improved_by, _sha()
    result = diag.replay()
    return {"after": _sha(), "before": before, "original": original, "restored": engine.improved_by, "result": result}


def test_admission_is_deterministic_and_bounded():
    one, two = diag.admission(), diag.admission()
    assert json.dumps(one, sort_keys=True) == json.dumps(two, sort_keys=True)
    assert 0 <= one["atteignables_admis"] <= one["admis"] <= 1024
    assert one["atteignables_admis"] <= one["atteignables_distincts"]
    assert one["vecteurs_total"] == 1024
    assert "borne_enumeration" in one


def test_replay_restores_the_wrapper_and_leaves_the_liveness_json_untouched(replayed):
    assert replayed["restored"] is replayed["original"]
    assert replayed["before"] == replayed["after"]


def test_fidelity_is_a_boolean_and_scores_are_only_published_when_true(replayed):
    result = replayed["result"]
    assert "fidelity_ok" in result and isinstance(result["fidelity_ok"], bool)
    for key in SCORE_KEYS:
        assert (key in result) is result["fidelity_ok"]


def test_the_wrapper_is_restored_after_a_failing_replay(monkeypatch):
    original = engine.improved_by

    def boom(*args, **kwargs):
        raise RuntimeError("échec simulé")

    monkeypatch.setattr(diag.liveness, "run", boom)
    with pytest.raises(RuntimeError):
        diag.replay()
    assert engine.improved_by is original


def _forbid(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("aucun calcul avant le refus")

    monkeypatch.setattr(diag, "admission", forbidden)
    monkeypatch.setattr(diag, "replay", forbidden)


def test_main_refuses_the_liveness_file_and_outside_paths(tmp_path, monkeypatch):
    _forbid(monkeypatch)
    before = _sha()
    assert diag.main(["--out", str(LIVENESS_JSON)]) == 1
    assert _sha() == before
    monkeypatch.setattr(diag, "RESULTS_DIR", tmp_path / "results")
    assert diag.main(["--out", str(tmp_path / "elsewhere.json")]) == 1
    assert diag.main(["--out", str(tmp_path / "results" / diag.PROTECTED)]) == 1
    assert not (tmp_path / "elsewhere.json").exists()


def test_stdout_is_sorted_json_and_out_is_written_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(diag, "admission", lambda: {"zeta": 1, "alpha": 0})
    monkeypatch.setattr(diag, "replay", lambda: {"fidelity_ok": False})
    monkeypatch.setattr(diag, "RESULTS_DIR", tmp_path / "results")
    assert diag.main([]) == 0
    printed = capsys.readouterr().out
    assert printed == json.dumps(json.loads(printed), indent=2, sort_keys=True) + "\n"
    target = tmp_path / "results" / "distinct.json"
    assert diag.main(["--out", str(target)]) == 0
    assert target.read_text(encoding="utf-8") == printed
    assert diag.main(["--out", str(target)]) == 1
    assert target.read_text(encoding="utf-8") == printed
