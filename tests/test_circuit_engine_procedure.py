import random

import pytest

from genesis import circuit_engine as engine
from genesis import circuit_procedure as cp
from genesis import circuit_tasks as tasks
from genesis.circuit_engine import Engine, Meter

BUDGET = 500
BIG = 10**7
LEARN = [task for task in tasks.suite(("and", "or", "parity")) if task.inputs <= 3]


def _procedure(admit, outs=(11, 11), steps=((0, 0), (0, 10))):
    """With the default steps signal 11 is constant 1: admit=11 admits every candidate."""
    procedure = cp.Procedure(len(cp.TRAITS), steps, outs, admit)
    cp.validate(procedure)
    return procedure


def _start():
    first = Engine()
    return first, engine.attempt(first, LEARN, BUDGET)


def _step(procedure, limit=BIG):
    first, solutions = _start()
    meter = Meter(limit)
    result = engine.improved_by(first, LEARN, BUDGET, solutions, procedure, meter, generation=1)
    return first, solutions, meter, result


def _tried(info):
    return [(trial["arity"], trial["nands"], trial["table"]) for trial in info["trials"]]


def _digest(result):
    successor, after, info = result
    return successor.record(), [(s.solved, s.evaluations, s.tree) for s in after], info


def test_meter_never_goes_past_its_limit_and_refuses_without_consuming():
    meter = Meter(5)
    assert meter.charge(3) and not meter.charge(3)
    assert (meter.spent, meter.remaining) == (3, 2)
    assert meter.charge(2) and meter.remaining == 0 and meter.charge(0) and not meter.charge(1)
    assert meter.spent == 5
    for bad in (-1, True, 1.5):
        with pytest.raises(ValueError):
            meter.charge(bad)
    with pytest.raises(ValueError):
        Meter(-1)


@pytest.mark.parametrize("limit", [0, 1, 5, 9, 12, 40, 150, 600, 5000, BIG])
def test_the_total_never_exceeds_the_limit_and_the_three_posts_add_up(limit):
    first, solutions, meter, (successor, after, info) = _step(cp.seed_procedure(), limit)
    assert meter.spent <= limit and meter.remaining == limit - meter.spent
    assert sum(info["spent"].values()) == meter.spent
    if successor is first:
        assert after == solutions and info["added"] is None
    else:
        new, old = engine.measure(after), engine.measure(solutions)
        assert (new[0], -new[1]) > (old[0], -old[1]) and info["added"]


def test_a_meter_too_tight_for_the_procedure_exhausts_and_leaves_the_engine_alone():
    reference, found = _start()
    assert engine.proposals(reference, found)
    for limit in (0, 5):
        first, solutions, meter, (successor, after, info) = _step(cp.seed_procedure(), limit)
        assert successor is first and after == solutions
        assert info["exhausted"] is True and info["trials"] == []
        assert meter.spent <= limit and sum(info["spent"].values()) == meter.spent


def test_a_generous_meter_is_not_exhausted_and_the_procedure_is_charged_per_candidate():
    seed = cp.seed_procedure()
    _, _, meter, (_, _, info) = _step(seed)
    assert info["exhausted"] is False and len(info["trials"]) <= engine.SEED_PROCEDURE["tried"]
    assert info["spent"]["procedure"] == len(seed.steps) * info["candidates"]
    assert sum(info["spent"].values()) == meter.spent


def test_one_changed_output_changes_what_is_tried():
    everything, narrow = _procedure(admit=11), _procedure(admit=6)
    one, two = _step(everything)[3][2], _step(narrow)[3][2]
    assert one["trials"] and _tried(one) != _tried(two)
    assert one["admitted"] > two["admitted"]


def test_one_changed_step_changes_what_is_tried():
    everything, inverted = _procedure(admit=11), _procedure(admit=11, steps=((0, 0), (0, 0)))
    one, two = _step(everything)[3][2], _step(inverted)[3][2]
    assert _tried(one) != _tried(two)


def test_a_procedure_that_admits_nothing_leaves_the_engine_unchanged():
    nothing = _procedure(admit=12, steps=((0, 0), (0, 10), (11, 11)))
    first, solutions, meter, (successor, after, info) = _step(nothing)
    assert successor is first and after == solutions
    assert info["trials"] == [] and info["added"] is None and info["admitted"] == 0 and info["exhausted"] is False
    assert info["spent"]["synthesis"] == info["spent"]["evaluations"] == 0 and meter.spent == 3 * info["candidates"]


def test_same_procedure_same_engine_same_result():
    for procedure in (cp.seed_procedure(), _procedure(admit=11), cp.random_procedure(random.Random(4), 12)):
        assert _digest(_step(procedure)[3]) == _digest(_step(procedure)[3])


def test_mutate_always_gives_a_valid_deterministic_procedure_without_touching_the_original():
    bases = [cp.seed_procedure(), cp.random_procedure(random.Random(1), 0), cp.random_procedure(random.Random(2), cp.MAX_STEPS)]
    for base in bases:
        snapshot = cp.to_record(base)
        rng, current, chain = random.Random(7), base, []
        for _ in range(200):
            current = cp.mutate(current, rng)
            cp.validate(current)
            chain.append(current)
        rng, current = random.Random(7), base
        for expected in chain:
            current = cp.mutate(current, rng)
            assert current == expected
        assert cp.to_record(base) == snapshot
        for seed in range(200):
            one = cp.mutate(base, random.Random(seed))
            cp.validate(one)
            assert one == cp.mutate(base, random.Random(seed))


def test_the_seed_procedure_plugs_in_and_the_existing_step_is_untouched():
    assert engine.SEED_PROCEDURE["tried"] == 6
    first, solutions, _, (successor, after, info) = _step(cp.seed_procedure())
    assert isinstance(successor, Engine) and len(info["trials"]) <= 6
    assert all(set(trial) >= {"name", "support", "composed", "priority", "solved", "evaluations"} for trial in info["trials"])
    assert engine.improved(first, LEARN, BUDGET, solutions, generation=1)[0] is not None
