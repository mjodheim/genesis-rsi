"""Diagnostic budget 16 du CIRCUIT2 : rejeu unique hors réseau, JSON trié sur stdout."""
from __future__ import annotations

import argparse
import json
import sys

try:
    import diagnose_circuit2_lineage_admission as diag
except ImportError:
    from scripts import diagnose_circuit2_lineage_admission as diag

from genesis import circuit_engine as engine

liveness = diag.liveness
lineage = diag.lineage

UNAVAILABLE = "indisponible"
BUDGET = 16
SEED = 0
GENERATIONS = 1
LIMIT = 80000


def _jsonable(value):
    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return UNAVAILABLE
    return value


def _info(call):
    if call is None:
        return None
    result = call["result"]
    if isinstance(result, (tuple, list)) and len(result) >= 3 and isinstance(result[2], dict):
        return result[2]
    return None


def _field(call, key):
    info = _info(call)
    if info is None or key not in info:
        return UNAVAILABLE
    return _jsonable(info[key])


def _trials(call):
    info = _info(call)
    try:
        return len(info["trials"])
    except (TypeError, KeyError):
        return UNAVAILABLE


def _score(call):
    if call is None:
        return UNAVAILABLE
    try:
        return _jsonable(list(lineage._score(call["result"][1])))
    except Exception:
        return UNAVAILABLE


def _exhausted(call):
    info = _info(call)
    value = None if info is None else info.get("exhausted")
    return value if isinstance(value, bool) else UNAVAILABLE


def _baseline(calls):
    try:
        measured = engine.measure(calls[0]["args"][3])
        if isinstance(measured, dict):
            measured = measured["solved"]
        else:
            measured = getattr(measured, "solved", measured)
    except Exception:
        return UNAVAILABLE
    if isinstance(measured, int) and not isinstance(measured, bool):
        return measured
    return UNAVAILABLE


def strict_improvements(parent, shortlist):
    if parent == UNAVAILABLE:
        return UNAVAILABLE
    count = 0
    for entry in shortlist:
        if entry["exhausted"] is True:
            continue
        if entry["exhausted"] == UNAVAILABLE or entry["score"] == UNAVAILABLE:
            return UNAVAILABLE
        try:
            better = entry["score"] > parent
        except TypeError:
            return UNAVAILABLE
        count += 1 if better else 0
    return count


def run_replay():
    calls = []
    original = engine.improved_by

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append({"args": args, "result": result})
        return result

    engine.improved_by = wrapper
    try:
        liveness.run(budgets=((BUDGET, LIMIT),), seeds=(SEED,), generations=GENERATIONS)
    finally:
        engine.improved_by = original
    return calls


def build(calls):
    first = calls[0] if calls else None
    parent = _score(first)
    shortlist = [{"exhausted": _exhausted(call), "score": _score(call)} for call in calls[1:]]
    return {
        "ameliorations_strictes": strict_improvements(parent, shortlist),
        "baseline_resolues": _baseline(calls),
        "etape_a": {
            "admitted": _field(first, "admitted"),
            "candidates": _field(first, "candidates"),
            "trials": _trials(first),
        },
        "parametres": {"budget": BUDGET, "generations": GENERATIONS, "graine": SEED, "limite": LIMIT},
        "score_parent": parent,
        "shortlist": shortlist,
    }


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    sys.stdout.write(json.dumps(build(run_replay()), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
