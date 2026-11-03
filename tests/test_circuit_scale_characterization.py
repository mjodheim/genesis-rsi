"""Tests de caractérisation (et non de succès) de l'échelle du circuit.

Aucune valeur de propositions n'est codée en dur : le nombre observé est
seulement mesuré, affiché et placé dans les messages d'assertion.
Hors réseau, aucune ressource gelée n'est modifiée.
"""
import random

from genesis import circuit_engine as engine
from genesis import circuit_meta_lineage as lineage
from genesis import circuit_tasks as tasks
from genesis.circuit_engine import Meter

LEARN = [t for t in tasks.suite(("and", "or", "parity")) if t.inputs <= 3]


def _n_proposals(tb):
    return len(engine.proposals(engine.Engine(), engine.attempt(engine.Engine(), LEARN, tb)))


def test_step_lineage_comptabilite_et_zero_candidat():
    start = lineage.initial_state()
    meter = Meter(1096)
    state = lineage.step(start, LEARN, 16, meter, random.Random("meta|0|0"))
    n = _n_proposals(16)
    msg = f"propositions observées (tb=16) : {n} ; meter.spent={meter.spent}"
    print(msg)
    assert meter.spent <= 1096, msg
    assert sum(state["spent"].values()) == meter.spent, msg
    assert lineage.verify_lineage([start, state]) is True, msg
    if n == 0:
        assert state["adopted"] is False, msg
        assert state["evaluated"] == [], msg
        assert state["library"] == start["library"], msg
