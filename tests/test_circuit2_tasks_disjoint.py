"""Offline checks that CIRCUIT2 tables are globally disjoint from CIRCUIT1 and from each other."""
from __future__ import annotations

import pytest

from genesis import circuit_tasks as tasks

SEEDS = (0, 1, 2, 3, 7)
ALL = (*tasks.LEARN, *tasks.HELD_OUT, *tasks.CONTROL)


def _keys(items):
    return {(t.inputs, t.target) for t in items}


@pytest.mark.parametrize("seed", SEEDS)
def test_learn_and_held_out_share_no_table(seed):
    learn = _keys(tasks.circuit2_suite(tasks.LEARN, seed))
    held = _keys(tasks.circuit2_suite(tasks.HELD_OUT, seed))
    assert not learn & held


@pytest.mark.parametrize("seed", SEEDS)
def test_circuit2_shares_no_table_with_circuit1(seed):
    assert not _keys(tasks.circuit2_suite(ALL, seed)) & _keys(tasks.suite(ALL, seed))


@pytest.mark.parametrize("seed", SEEDS)
def test_no_table_appears_twice(seed):
    items = tasks.circuit2_suite(ALL, seed)
    assert len(_keys(items)) == len(items)


@pytest.mark.parametrize("seed", SEEDS)
def test_xnor_collision_is_covered(seed):
    assert any(t.name == "equal1" and t.inputs == 2 and t.target == 9 for t in tasks.suite(ALL, seed))
    items = tasks.circuit2_suite(ALL, seed)
    assert not [t for t in items if t.inputs == 2 and t.target == 9]
    by_name = {t.name: t for t in items}
    a, b = by_name.get("c2_parity2"), by_name.get("c2_sub1bit0")
    assert a is None or b is None or a.target != b.target


@pytest.mark.parametrize("seed", SEEDS)
def test_assignment_is_deterministic(seed):
    first = tasks.circuit2_suite(ALL, seed)
    tasks._circuit2_assignment.cache_clear()
    second = tasks.circuit2_suite(ALL, seed)
    assert first == second


def test_returned_lists_are_copies():
    first = tasks.circuit2_tasks("and")
    first.clear()
    assert tasks.circuit2_tasks("and")


def test_unknown_family_is_refused():
    with pytest.raises(ValueError):
        tasks.circuit2_tasks("nope")


@pytest.mark.parametrize("seed", SEEDS)
def test_suites_are_non_empty_and_learn_families_keep_a_task(seed):
    assert tasks.circuit2_suite(ALL, seed) and tasks.circuit2_suite(tasks.LEARN, seed)
    for family in tasks.LEARN:
        assert tasks.circuit2_tasks(family, seed), family
