"""Contrôles hors réseau des traits des candidats du budget 16 (CIRCUIT2)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

try:
    import circuit2_budget16_traits as traits_mod
except ImportError:
    from scripts import circuit2_budget16_traits as traits_mod

ROOT = Path(__file__).resolve().parent.parent


def _simuler(monkeypatch):
    vus = {}

    comp_a = SimpleNamespace(key="a", arity=2, steps=[0, 1, 2])
    comp_b = SimpleNamespace(key="b", arity=3, steps=[0, 1, 2, 3])

    def proposals(a, b):
        vus["proposals"] = (a, b)
        return [(comp_a, 1), (comp_b, 2)]

    def composed_flags(a, b):
        vus["composed_flags"] = (a, b)
        return {"a": False, "b": True}

    monkeypatch.setattr(
        traits_mod.diag,
        "run_replay",
        lambda: [{"args": (5, 6, 7, "taches"), "result": None}],
    )
    monkeypatch.setattr(traits_mod.engine, "proposals", proposals)
    monkeypatch.setattr(traits_mod.engine, "composed_flags", composed_flags)
    monkeypatch.setattr(traits_mod.circuit_procedure, "seed_procedure", lambda: "depart")
    monkeypatch.setattr(
        traits_mod.circuit_procedure,
        "traits_of",
        lambda support, arity, nands, composed: (support, arity, nands, composed),
    )
    monkeypatch.setattr(
        traits_mod.circuit_procedure,
        "run",
        lambda proc, traits: (traits[0], traits[0] >= 2 and proc == "depart", 0),
    )
    return vus


def test_output_reflects_traits_and_admission(monkeypatch, capsys):
    vus = _simuler(monkeypatch)
    assert traits_mod.main([]) == 0
    sortie = capsys.readouterr().out
    data = json.loads(sortie)
    assert sortie == json.dumps(data, indent=2, sort_keys=True) + "\n"
    assert vus["proposals"] == (5, "taches")
    assert vus["composed_flags"] == (5, "taches")
    assert data["nombre_candidats"] == 2
    assert data["candidats"] == [
        {
            "admis": False,
            "priorite": 1,
            "traits": {"support": 1, "arity": 2, "nands": 3, "composed": False},
        },
        {
            "admis": True,
            "priorite": 2,
            "traits": {"support": 2, "arity": 3, "nands": 4, "composed": True},
        },
    ]


def test_no_file_is_created(monkeypatch, tmp_path, capsys):
    _simuler(monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert traits_mod.main([]) == 0
    capsys.readouterr()
    assert list(tmp_path.iterdir()) == []


def test_missing_flag_key_raises(monkeypatch):
    _simuler(monkeypatch)
    monkeypatch.setattr(traits_mod.engine, "composed_flags", lambda a, b: {"a": False})
    with pytest.raises(KeyError):
        traits_mod.collect()


def test_real_script_matches_published_counts():
    script = ROOT / "scripts" / "circuit2_budget16_traits.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    detail = f"returncode={proc.returncode!r}\nstdout={proc.stdout!r}\nstderr={proc.stderr!r}"
    assert proc.returncode == 0, detail
    data = json.loads(proc.stdout)
    publie = json.loads((ROOT / "results" / "circuit2_budget16_stdout.json").read_text(encoding="utf-8"))
    bloc = publie.get("etape_a", publie)
    assert data["nombre_candidats"] == 2, detail
    assert bloc["candidates"] == data["nombre_candidats"], detail
    assert bloc["admitted"] == 0, detail
    assert sum(1 for c in data["candidats"] if c["admis"]) == bloc["admitted"], detail
    appels = traits_mod._appels(traits_mod.diag.run_replay())
    moteur, solutions = appels[0]["args"][0], appels[0]["args"][3]
    paires = list(traits_mod.engine.proposals(moteur, solutions))
    drapeaux = traits_mod.engine.composed_flags(moteur, solutions)
    assert isinstance(drapeaux, dict), detail
    assert {c.key for c, _ in paires} <= set(drapeaux), detail
    assert len(paires) == data["nombre_candidats"], detail
    assert bloc["candidates"] == len(paires), detail
    assert len(data["candidats"]) == len(paires), detail
    for ligne, (c, _support) in zip(data["candidats"], paires):
        traits = ligne["traits"]
        assert isinstance(traits["composed"], bool), detail
        assert type(traits["nands"]) is int and traits["nands"] > 0, detail
        assert type(traits["arity"]) is int and traits["arity"] > 0, detail
        assert traits["composed"] == drapeaux[c.key], detail
        assert traits["nands"] == len(c.steps), detail
        assert traits["arity"] == c.arity, detail
