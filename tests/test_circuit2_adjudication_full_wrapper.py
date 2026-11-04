"""Tests hors réseau du lanceur de l'adjudication CIRCUIT2 complète.

adjudicate.main est remplacé par un espion : aucune campagne n'est exécutée.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import adjudicate_circuit_lineage as adj  # noqa: E402
import run_circuit2_adjudication_full as wrapper  # noqa: E402


def _plan():
    return adj.load_plan(adj.DEFAULT_PLAN)


@pytest.fixture
def spy(monkeypatch):
    """Espion sur main ; tout calcul réel est interdit."""
    calls = []

    def fake_main(argv=None):
        calls.append(list(argv))
        return 0

    def forbidden(*args, **kwargs):
        raise AssertionError("aucune exécution réelle attendue")

    monkeypatch.setattr(adj, "main", fake_main)
    monkeypatch.setattr(adj, "final_library", forbidden)
    monkeypatch.setattr(adj, "measure_held_out", forbidden)
    return calls


def _values(argv, option):
    start = argv.index(option) + 1
    values = []
    for token in argv[start:]:
        if token.startswith("--"):
            break
        values.append(token)
    return values


def test_default_arguments_come_from_plan(spy):
    plan = _plan()
    assert wrapper.main([]) == 0
    assert len(spy) == 1
    argv = spy[0]
    assert [t for t in argv if t.startswith("--")] == ["--seeds", "--generations", "--out"]
    assert len(plan["seeds"]) == 20
    assert _values(argv, "--seeds") == [str(s) for s in plan["seeds"]]
    assert _values(argv, "--generations") == [str(plan["budgets"]["generations"])]
    expected = (Path(adj.ROOT) / "results" / "circuit2_adjudication_full.json").resolve()
    assert [Path(v).resolve() for v in _values(argv, "--out")] == [expected]


def test_out_under_results_accepted(spy):
    assert wrapper.main(["--out", "results/autre_sortie.json"]) == 0
    expected = (Path(adj.ROOT) / "results" / "autre_sortie.json").resolve()
    assert [Path(v).resolve() for v in _values(spy[0], "--out")] == [expected]


@pytest.mark.parametrize("kind", ["absolu_externe", "remonte", "traversee", "dossier"])
def test_out_outside_results_refused(spy, capsys, tmp_path, kind):
    out = {
        "absolu_externe": str(tmp_path / "x.json"),
        "remonte": "../x.json",
        "traversee": "results/../x.json",
        "dossier": "results",
    }[kind]
    assert wrapper.main(["--out", out]) == 2
    assert spy == []
    assert capsys.readouterr().err.startswith("erreur : ")


def test_altered_plan_refused_before_main(spy, monkeypatch, capsys, tmp_path):
    plan = json.loads(Path(adj.DEFAULT_PLAN).read_text(encoding="utf-8"))
    plan["budgets"]["task_budget"] += 1
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    monkeypatch.setattr(adj, "DEFAULT_PLAN", path)
    assert wrapper.main([]) == 2
    assert spy == []
    assert capsys.readouterr().err.startswith("erreur : ")


def test_other_options_rejected(spy):
    with pytest.raises(SystemExit):
        wrapper.main(["--seeds", "1"])
    assert spy == []
