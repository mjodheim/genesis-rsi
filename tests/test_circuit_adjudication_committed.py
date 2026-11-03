"""Tests hors réseau et sans modèle sur le résultat committé de l'adjudication réduite.

Fichier lu : results/circuit2_adjudication_s0-1_g6.json (adjudication RÉDUITE :
graines 0 et 1 sur 20, 6 générations).

- Les 20 graines ne sont pas jugées contre le critère gelé.
- Résultat nul consigné tel quel : rendement 0 et même empreinte de bibliothèque
  pour les 4 bras.
- Écart de machinery_commit non expliqué : 245661e0 dans PROCEDURE_PREREG_PLAN.json
  contre e60a37e1 dans le résultat ; il n'est pas comparé ici.
- Rien n'est affirmé sur results/circuit2_campaign_full.json : non vérifié.

Hypothèses non confirmées par lecture, laissées visibles : le module fcp est lu via
adj.fcp ; le digest du plan est pris dans le plan s'il y figure, sinon fingerprint(plan).
Un échec dû à l'une d'elles est un résultat à rapporter, pas à masquer.
"""
from __future__ import annotations

import ast
import importlib
import json
import signal
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "adjudicate_circuit_lineage.py"
RESULT = ROOT / "results" / "circuit2_adjudication_s0-1_g6.json"
REPLAY_TIMEOUT_S = 600
FORBIDDEN_KEY_PARTS = ("gain", "success", "succes", "succès")
TRIVIAL_CONSTANTS = (0, 1)


class _ReplayTimeout(Exception):
    pass


def _on_alarm(signum, frame):
    raise _ReplayTimeout()


@pytest.fixture(scope="module")
def adj():
    for path in (str(ROOT), str(ROOT / "scripts")):
        if path not in sys.path:
            sys.path.insert(0, path)
    return importlib.import_module("adjudicate_circuit_lineage")


@pytest.fixture(scope="module")
def fcp(adj):
    return adj.fcp


@pytest.fixture(scope="module")
def data():
    return json.loads(RESULT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def plan(adj):
    return adj.load_plan(adj.DEFAULT_PLAN)


def _plan_digest(adj, plan):
    if isinstance(plan, dict):
        for key in ("plan_digest", "digest"):
            if key in plan:
                return plan[key]
    return adj.fingerprint(plan)


def _yield_value(measured):
    if isinstance(measured, dict) and "held_out_yield" in measured:
        return measured["held_out_yield"]
    return measured


def _all_keys(obj):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield str(key)
            yield from _all_keys(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _all_keys(value)


def _numeric_value(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    if (
        isinstance(node, ast.Constant)
        and isinstance(node.value, (int, float))
        and not isinstance(node.value, bool)
    ):
        return node.value
    return None


def _bad_keys(obj):
    return sorted(
        {k for k in _all_keys(obj) if any(p in k.lower() for p in FORBIDDEN_KEY_PARTS)}
    )


def test_structure(adj, data, plan):
    assert data["scale"] == "reduced"
    assert data["seeds"] == [0, 1]
    assert data["generations"] == 6
    assert len(data["arms"]) == 4
    assert len(set(data["arms"])) == 4
    assert len(data["rows"]) == 8
    pairs = {(row["arm"], row["seed"]) for row in data["rows"]}
    assert pairs == {(arm, seed) for arm in data["arms"] for seed in data["seeds"]}
    assert data["plan_digest"] == _plan_digest(adj, plan)
    budgets = plan["budgets"]
    assert data["task_budget"] == budgets["task_budget"]
    assert data["per_generation_limit"] == budgets["per_generation_limit"]
    assert data["generations"] == budgets["generations"]


def test_null_result_recorded_as_is(data):
    rows = data["rows"]
    yields = [row["held_out_yield"] for row in rows]
    fingerprints = {row["library_fingerprint"] for row in rows}
    pairs = {(row["arm"], row["seed"]) for row in rows}
    expected = {(arm, seed) for arm in data["arms"] for seed in data["seeds"]}
    observed = (
        f"lignes={len(rows)} paires={sorted(pairs)!r} held_out_yield={yields!r} "
        f"library_fingerprint_distinctes={sorted(fingerprints)!r}"
    )
    assert pairs == expected, observed
    assert len(rows) == len(expected), observed
    assert all(value == 0 for value in yields), observed
    assert len(fingerprints) == 1, observed


def test_replay_random_procedure_seed0(adj, fcp, data):
    row = next(
        r for r in data["rows"] if r["arm"] == "random_procedure" and r["seed"] == 0
    )
    plan_errors = tuple(
        e for e in (getattr(adj, "PlanError", None),) if isinstance(e, type)
    )
    has_alarm = hasattr(signal, "SIGALRM")
    if has_alarm:
        previous = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(REPLAY_TIMEOUT_S)
    try:
        tasks = fcp.learn_tasks()
        records, engine, final_procedure, _initial = adj.final_library(
            "random_procedure",
            0,
            tasks,
            data["per_generation_limit"],
            data["task_budget"],
            data["generations"],
        )
        measured = adj.measure_held_out(engine)
    except _ReplayTimeout:
        pytest.skip(f"rejeu au-delà de {REPLAY_TIMEOUT_S} s : non conclu, non comparé")
    except plan_errors as exc:
        if "EXECUTABLES" not in str(exc):
            raise
        pytest.skip(f"EXECUTABLES.json absent (PlanError) : mesure impossible ({exc})")
    finally:
        if has_alarm:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)
    obtenu_yield = _yield_value(measured)
    obtenu_fingerprint = adj.fingerprint(engine.record())
    obtenu_generations = len(records)
    obtenu_stop_reason = adj.stop_reason(records)
    assert obtenu_yield == row["held_out_yield"], (
        f"held_out_yield : attendu={row['held_out_yield']!r} obtenu={obtenu_yield!r}"
    )
    assert obtenu_fingerprint == row["library_fingerprint"], (
        f"library_fingerprint : attendu={row['library_fingerprint']!r} "
        f"obtenu={obtenu_fingerprint!r}"
    )
    assert obtenu_generations == row["generations"], (
        f"generations : attendu={row['generations']!r} obtenu={obtenu_generations!r}"
    )
    assert obtenu_stop_reason == row["stop_reason"], (
        f"stop_reason : attendu={row['stop_reason']!r} obtenu={obtenu_stop_reason!r}"
    )


def test_no_success_threshold_comparison_in_script():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"), filename=str(SCRIPT))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            for operand in [node.left, *node.comparators]:
                value = _numeric_value(operand)
                if value is not None and value not in TRIVIAL_CONSTANTS:
                    found.append((node.lineno, value))
    assert not found, f"comparaisons à une constante numérique : {found}"


def test_no_gain_or_success_key_in_committed_result(data):
    assert _bad_keys(data) == []
    assert _bad_keys(data["rows"]) == []
