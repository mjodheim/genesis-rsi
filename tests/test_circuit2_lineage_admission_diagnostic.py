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


def _call(digest, score, exhausted=False):
    return {"digest": digest, "exhausted": exhausted, "score": score}


def test_the_real_replay_matches_every_frozen_expectation(replayed):
    # Si ce test échoue, c'est un résultat négatif à signaler : EXPECTED n'est pas assoupli.
    frozen = {"n_evaluated": 5, "solved": 5, "evaluations": 21529, "procedure": 813, "synthesis": 12}
    assert diag.EXPECTED == frozen
    assert diag.LIBRARY_PREFIX == "2fd1cbc5"
    result = replayed["result"]
    assert result["fidelity_ok"] is True
    assert result["ecarts"] == []
    for name, value in frozen.items():
        assert result["observe"][name] == value, name
    assert result["observe"]["library_digest"].startswith("2fd1cbc5")


def test_analyse_with_all_scores_equal():
    out = diag.analyse([_call("p", [4, -9]), _call("a", [4, -9]), _call("b", [4, -9])], False)
    assert out["scores_tous_egaux"] is True
    assert out["candidats_strictement_meilleurs"] == []
    assert out["adoption_stricte_explique_absence"] is True
    assert out["parent"]["digest"] == "p"
    assert [c["digest"] for c in out["candidats"]] == ["a", "b"]


def test_analyse_with_one_strictly_better_candidate():
    calls = [_call("p", [4, -9]), _call("a", [4, -9]), _call("b", [5, -20])]
    out = diag.analyse(calls, False)
    assert out["scores_tous_egaux"] is False
    assert out["candidats_strictement_meilleurs"] == ["b"]
    assert out["adoption_stricte_explique_absence"] is False
    assert diag.analyse(calls, True)["adoption_stricte_explique_absence"] is False


def test_analyse_ignores_a_better_but_exhausted_candidate():
    out = diag.analyse([_call("p", [4, -9]), _call("a", [5, -3], exhausted=True)], False)
    assert out["candidats_strictement_meilleurs"] == []
    assert out["scores_tous_egaux"] is False
    assert out["adoption_stricte_explique_absence"] is True


def test_analyse_treats_incomparable_scores_as_not_better():
    out = diag.analyse([_call("p", [4, -9]), _call("a", [4, "x"])], False)
    assert out["candidats_strictement_meilleurs"] == []
    assert out["scores_tous_egaux"] is False
    assert out["adoption_stricte_explique_absence"] is True


def test_analyse_without_any_candidate():
    out = diag.analyse([_call("p", [4, -9])], False)
    assert out["candidats"] == []
    assert out["candidats_strictement_meilleurs"] == []
    assert out["scores_tous_egaux"] is False
    assert out["adoption_stricte_explique_absence"] is True


def _bad_samples():
    width = len(diag.cp.TRAITS)
    return ["abc", 1.5, None, True, {0, 1}, [0, 1], (0,) * (width + 1), [0] * (width - 1) + [2], [0] * (width - 1) + ["1"]]


@pytest.mark.parametrize("sample", _bad_samples())
def test_universe_refuses_unexpected_types_and_values(sample):
    with pytest.raises(diag.DiagnosticError):
        diag._universe(sample)


def test_universe_accepts_int_list_and_tuple():
    width = len(diag.cp.TRAITS)
    assert len(diag._universe(0)) == 1 << width
    as_lists = diag._universe([0] * width)
    as_tuples = diag._universe((0,) * width)
    assert len(as_lists) == len(as_tuples) == 1 << width
    assert all(isinstance(vector, list) for vector in as_lists)
    assert all(isinstance(vector, tuple) for vector in as_tuples)


def test_replay_refuses_a_result_without_exhausted_or_a_call_without_procedure(monkeypatch):
    monkeypatch.setattr(engine, "improved_by", lambda *args, **kwargs: ("courant", "solutions", {}))
    monkeypatch.setattr(diag.liveness, "run", lambda **kwargs: engine.improved_by(1, 2, 3, 4, "p", None))
    with pytest.raises(diag.DiagnosticError):
        diag.replay()
    monkeypatch.setattr(diag.liveness, "run", lambda **kwargs: engine.improved_by(1, 2, 3, 4))
    with pytest.raises(diag.DiagnosticError):
        diag.replay()


def test_admission_recounts_with_cp_max_steps(monkeypatch):
    monkeypatch.setattr(diag.cp, "MAX_STEPS", 3)
    monkeypatch.setattr(diag.cp, "run", lambda procedure, vector: (0, False, None))
    seen = []
    real = diag.lineage._traits

    def spy(size, support, composed):
        seen.append((size, support, composed))
        return real(size, support, composed)

    monkeypatch.setattr(diag.lineage, "_traits", spy)
    out = diag.admission()
    bound = out["borne_enumeration"]
    assert len(seen) == 2 * 4 * (diag.SUPPORT_RANGE + 1)
    assert bound["appels"] == len(seen)
    assert bound["taille"] == [0, 3]
    assert {size for size, _, _ in seen} == {0, 1, 2, 3}
    assert {composed for _, _, composed in seen} == {False, True}
    assert {support for _, support, _ in seen} == set(range(diag.SUPPORT_RANGE + 1))


def test_admission_refuses_a_support_range_above_the_cap(monkeypatch):
    monkeypatch.setattr(diag, "SUPPORT_RANGE", diag.lineage.SUPPORT_CAP + 1)
    with pytest.raises(diag.DiagnosticError):
        diag.admission()
