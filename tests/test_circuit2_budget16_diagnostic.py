"""Contrôles hors réseau du diagnostic budget 16 du CIRCUIT2."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import circuit2_budget16_diagnostic as c16
except ImportError:
    from scripts import circuit2_budget16_diagnostic as c16

from genesis import circuit_engine as engine


def _install(monkeypatch, outputs):
    queue = list(outputs)
    count = len(queue)
    monkeypatch.setattr(engine, "improved_by", lambda *args, **kwargs: ("courant", *queue.pop(0)))
    monkeypatch.setattr(engine, "measure", lambda tasks: (7, 123))
    monkeypatch.setattr(c16.lineage, "_score", lambda solutions: solutions)

    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        for _ in range(count):
            engine.improved_by(1, 2, 3, "taches")

    monkeypatch.setattr(c16.liveness, "run", fake_run)
    return captured


def _full():
    return {"admitted": 2, "candidates": 3, "trials": [1, 2, 3]}


def _cand(score, exhausted=False):
    return (score, {"exhausted": exhausted})


def _run(capsys):
    assert c16.main([]) == 0
    return capsys.readouterr().out


def test_improved_by_is_restored_even_when_the_run_fails(monkeypatch):
    marker = lambda *args, **kwargs: None
    monkeypatch.setattr(engine, "improved_by", marker)

    def boom(**kwargs):
        raise RuntimeError("échec simulé")

    monkeypatch.setattr(c16.liveness, "run", boom)
    with pytest.raises(RuntimeError):
        c16.run_replay()
    assert engine.improved_by is marker


def test_improved_by_is_restored_after_a_normal_run(monkeypatch):
    _install(monkeypatch, [([4, -9], _full())])
    fake = engine.improved_by
    c16.run_replay()
    assert engine.improved_by is fake


def test_missing_counters_are_reported_as_unavailable(monkeypatch, capsys):
    _install(monkeypatch, [([4, -9], {"candidates": 3})])
    monkeypatch.setattr(engine, "measure", lambda tasks: (_ for _ in ()).throw(RuntimeError("absent")))
    data = json.loads(_run(capsys))
    assert data["etape_a"] == {"admitted": "indisponible", "candidates": 3, "trials": "indisponible"}
    assert data["baseline_resolues"] == "indisponible"
    assert data["ameliorations_strictes"] == 0


def test_strict_improvements_exclude_ties_and_exhausted_candidates(monkeypatch, capsys):
    outputs = [
        ([4, -9], _full()),
        _cand([4, -9]),
        _cand([5, -3]),
        _cand([6, 0], exhausted=True),
        _cand([3, -1]),
    ]
    _install(monkeypatch, outputs)
    data = json.loads(_run(capsys))
    assert data["ameliorations_strictes"] == 1
    assert data["score_parent"] == [4, -9]
    assert data["baseline_resolues"] == 7
    assert data["etape_a"] == {"admitted": 2, "candidates": 3, "trials": 3}
    assert [entry["exhausted"] for entry in data["shortlist"]] == [False, False, True, False]
    assert data["parametres"] == {"budget": 16, "generations": 1, "graine": 0, "limite": 80000}


def test_strict_improvements_helper_handles_unreadable_values():
    assert c16.strict_improvements("indisponible", []) == "indisponible"
    entry = {"exhausted": "indisponible", "score": [1, 0]}
    assert c16.strict_improvements([0, 0], [entry]) == "indisponible"


def test_no_file_is_created_and_options_are_refused(monkeypatch, tmp_path, capsys):
    _install(monkeypatch, [([4, -9], _full()), _cand([5, -3])])
    monkeypatch.chdir(tmp_path)
    _run(capsys)
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(SystemExit):
        c16.main(["--out", "x.json"])
    assert list(tmp_path.iterdir()) == []


def test_stdout_is_sorted_json_only(monkeypatch, capsys):
    _install(monkeypatch, [([4, -9], _full()), _cand([5, -3])])
    assert c16.main([]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == json.dumps(json.loads(captured.out), indent=2, sort_keys=True) + "\n"


def test_replay_passes_exact_kwargs(monkeypatch):
    captured = _install(monkeypatch, [([4, -9], _full())])
    c16.run_replay()
    assert captured == {"budgets": ((16, 80000),), "seeds": (0,), "generations": 1}


def test_baseline_with_real_measure():
    # Vrai engine.measure, sans monkeypatch : jeu de tâches vide, le plus simple sans dépendre d'autres noms.
    tasks = []
    solved = engine.measure(tasks)[0]
    calls = [{"args": (1, 2, 3, tasks), "result": None}]
    result = c16._baseline(calls)
    assert isinstance(result, int) and not isinstance(result, bool)
    assert result == solved
    assert result != "indisponible"


def test_real_script_emits_sorted_json_on_stdout():
    root = Path(__file__).resolve().parent.parent
    script = root / "scripts" / "circuit2_budget16_diagnostic.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    detail = f"returncode={proc.returncode!r}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    assert proc.returncode == 0, detail
    assert proc.stdout.strip() != "", detail
    data = json.loads(proc.stdout)
    assert proc.stdout == json.dumps(data, indent=2, sort_keys=True) + "\n", detail
    assert data["parametres"] == {"budget": 16, "generations": 1, "graine": 0, "limite": 80000}, detail
    baseline = data["baseline_resolues"]
    assert isinstance(baseline, int) and not isinstance(baseline, bool), detail
