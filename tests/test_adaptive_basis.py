"""Development-only property tests for bounded reversible grammar exploration."""
from __future__ import annotations

import pytest
from experiment.representation_discovery import adaptive_basis as a
from experiment.representation_discovery import prototype as p


def test_reversible_shear_and_axis_on_every_three_input_table():
    for table in range(256):
        for op in (a.Op("axis", 0), a.Op("axis", 2), a.Op("shear", 3, 5),
                   a.Op("shear", 6, 0)):
            assert a.apply_op(a.apply_op(table, 3, op), 3, op) == table


def test_program_inverse_composition_is_exact():
    program = (a.Op("axis", 0), a.Op("shear", 2, 1),
               a.Op("axis", 1), a.Op("shear", 0, 7))
    for table in range(256):
        encoded = a.apply_program(table, 3, program)
        assert a.invert_program(encoded, 3, program) == table
        assert a.invert_program(p.decode(p.encode(encoded, 3), 3), 3, program) == table


@pytest.mark.parametrize("op", [
    a.Op("other", 0), a.Op("axis", 8), a.Op("axis", 1, 1),
    a.Op("shear", 2, 2), a.Op("shear", 8, 1), a.Op("shear", 0, -1)])
def test_invalid_primitive_rejected(op):
    with pytest.raises(ValueError):
        a.apply_op(0, 3, op)


def test_training_only_search_wins_or_ties_identity():
    for n in (3, 4, 5, 6):
        train = p.tasks_for(p.FAMILIES_TRAIN, n)
        best, record = a.discover(train, n, candidate_limit=28)
        assert best.score <= a.training_score(train, n, ())
        assert len(record["candidates"]) <= 28
        assert record["prescreen_probes"] >= 0
        assert best.program in record["candidates"]


def test_random_uses_equal_or_less_evaluated_budget():
    train = p.tasks_for(p.FAMILIES_TRAIN, 4)
    _, guided = a.discover(train, 4, candidate_limit=33)
    _, random = a.discover(train, 4, strategy="random", candidate_limit=33)
    assert len(guided["candidates"]) == len(random["candidates"]) == 33
    assert guided["prescreen_probes"] > random["prescreen_probes"]


def test_repeated_development_trial_is_deterministic():
    assert a.trial(seeds=(0,)) == a.trial(seeds=(0,))
