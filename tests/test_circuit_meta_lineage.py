import copy
import json
import random

import pytest

from genesis import circuit_engine as engine
from genesis import circuit_meta_lineage as lineage
from genesis import circuit_procedure as cp
from genesis import circuit_tasks as tasks
from genesis.circuit_engine import Meter

BUDGET = 500
BIG = 10**6
LEARN = [task for task in tasks.suite(("and", "or", "parity")) if task.inputs <= 3]


def _procedure(admit, outs=(11, 11), steps=((0, 0), (0, 10))):
    """With the default steps signal 11 is constant 1: admit=11 admits every candidate."""
    procedure = cp.Procedure(len(cp.TRAITS), steps, outs, admit)
    cp.validate(procedure)
    return procedure


def _nothing():
    return _procedure(admit=12, steps=((0, 0), (0, 10), (11, 11)))


def _run(generations=3, limit=BIG, seed=1):
    return lineage.run_lineage(generations, LEARN, BUDGET, limit, seed)


def _rng(seed, index=0):
    return random.Random(f"meta|{seed}|{index}")


def test_two_identical_runs_give_the_same_fingerprints():
    one, two = _run(4), _run(4)
    assert [state["digest"] for state in one] == [state["digest"] for state in two]
    assert one == two and len(one) == 5
    assert json.loads(json.dumps(one)) == one
    assert lineage.verify_lineage(json.loads(json.dumps(one))) is True


def test_the_initial_state_passes_verify_state():
    state = lineage.initial_state()
    assert lineage.verify_state(state) is None
    assert lineage.verify_state(json.loads(json.dumps(state))) is None
    assert lineage.verify_lineage([state]) is True


def test_initial_state_with_a_list_library_is_accepted_before_and_after_a_json_round_trip():
    state = lineage.initial_state()
    assert isinstance(state["library"], list)
    assert lineage.verify_state(state) is None
    assert lineage.verify_state(json.loads(json.dumps(state))) is None


def _spend_more(chain):
    chain[2]["spent"]["synthesis"] += 1


def _bend_parent(chain):
    chain[3]["parent"] = "0" * 64


def _bend_procedure(chain):
    chain[2]["procedure"]["admit_output"] = 0


def _bend_library(chain):
    chain[1]["library"] = {"altered": True}


def _reseal_forgery(chain):
    body = dict(chain[1])
    body["spent"] = {**body["spent"], "synthesis": body["spent"]["synthesis"] + 1}
    chain[1] = lineage.seal(body)


def _swap(chain):
    chain[1], chain[2] = chain[2], chain[1]


def _skip(chain):
    del chain[2]


def test_every_generation_points_to_its_parent_and_a_tampered_chain_is_refused():
    states = _run(4)
    assert states[0]["parent"] is None
    for before, after in zip(states, states[1:]):
        assert after["parent"] == before["digest"] and after["index"] == before["index"] + 1
    assert lineage.verify_lineage(states) is True
    assert lineage.verify_lineage([]) is True
    for alter in (_spend_more, _bend_parent, _bend_procedure, _bend_library, _reseal_forgery, _swap, _skip):
        chain = copy.deepcopy([dict(state) for state in states])
        alter(chain)
        with pytest.raises(lineage.LineageError):
            lineage.verify_lineage(chain)


@pytest.mark.parametrize("limit", [0, 1, 7, 60, 400, 3000, 20000, BIG])
def test_the_ceiling_is_exact_and_the_posts_add_up(limit):
    start = lineage.initial_state()
    meter = Meter(limit)
    state = lineage.step(start, LEARN, BUDGET, meter, _rng(1))
    assert meter.spent <= limit
    assert sum(state["spent"].values()) == meter.spent
    assert state["parent"] == start["digest"] and lineage.verify_lineage([start, state]) is True
    if limit == 0:
        assert state["exhausted"] is True and meter.spent == 0
        assert state["library"] == start["library"] and state["procedure"] == start["procedure"]
    if limit == BIG:
        assert state["exhausted"] is False
    for generated in _run(3, limit)[1:]:
        assert sum(generated["spent"].values()) <= limit


@pytest.fixture()
def solve_spy(monkeypatch):
    real = engine.solve
    log = {"calls": 0, "evaluations": 0}

    def spy(*args, **kwargs):
        result = real(*args, **kwargs)
        log["calls"] += 1
        log["evaluations"] += result.evaluations
        return result

    monkeypatch.setattr(engine, "solve", spy)
    return log


def test_a_zero_budget_never_reaches_solve(solve_spy):
    start = lineage.initial_state()
    meter = Meter(0)
    state = lineage.step(start, LEARN, BUDGET, meter, _rng(1))
    assert solve_spy["calls"] == 0 and solve_spy["evaluations"] == 0
    assert meter.spent == 0
    assert state["exhausted"] is True
    assert state["adopted"] is False
    assert state["score"] is None and state["parent_score"] is None
    assert state["library"] == start["library"] and state["procedure"] == start["procedure"]
    assert sum(state["spent"].values()) == 0
    assert lineage.verify_lineage([start, state]) is True


@pytest.mark.parametrize("limit", [0, 1, 7, 60, 400, BIG])
def test_the_evaluations_post_is_what_solve_really_returned(solve_spy, limit):
    start = lineage.initial_state()
    meter = Meter(limit)
    state = lineage.step(start, LEARN, BUDGET, meter, _rng(1))
    assert solve_spy["evaluations"] == state["spent"]["evaluations"]
    assert meter.spent <= limit
    assert sum(state["spent"].values()) == meter.spent
    assert lineage.verify_lineage([start, state]) is True


def test_the_inherited_procedure_changes_what_is_evaluated():
    base = lineage.initial_state()
    everything = lineage.replace_procedure(base, _procedure(admit=11))
    nothing = lineage.replace_procedure(base, _nothing())
    assert everything["library"] == nothing["library"]
    witnesses = []
    for seed in range(6):
        one = lineage.step(everything, LEARN, BUDGET, Meter(BIG), _rng(seed))
        two = lineage.step(nothing, LEARN, BUDGET, Meter(BIG), _rng(seed))
        if one["evaluated"] and one["evaluated"] != two["evaluated"]:
            witnesses.append(seed)
    assert witnesses


def test_held_out_and_control_tasks_are_refused():
    held = [task for family in tasks.HELD_OUT for task in tasks.tasks(family)[:1]]
    control = [engine.Task("control", family, 2, 0b0110) for family in getattr(tasks, "CONTROL", ())]
    unknown = [engine.Task("unknown", "no-such-family", 2, 0b0110)]
    assert held
    for bad in [[task] for task in (*held, *control)] + [unknown]:
        with pytest.raises(lineage.LineageError):
            lineage.run_lineage(1, bad, BUDGET, BIG, 1)
        with pytest.raises(lineage.LineageError):
            lineage.run_lineage(1, LEARN + bad, BUDGET, BIG, 1)


def test_selection_uses_learning_tasks_only_and_never_asks_for_held_out(monkeypatch):
    real = engine.improved_by
    seen = []

    def spy(first, given, *args, **kwargs):
        seen.append(list(given))
        return real(first, given, *args, **kwargs)

    monkeypatch.setattr(engine, "improved_by", spy)
    states = _run(3)
    assert len(states) == 4 and seen
    refused = set(tasks.HELD_OUT) | set(getattr(tasks, "CONTROL", ()))
    for received in seen:
        assert [task.name for task in received] == [task.name for task in LEARN]
        assert all(task.family in tasks.LEARN for task in received)
        assert not {task.family for task in received} & refused


def test_a_parent_is_kept_when_no_candidate_is_strictly_better():
    single = [engine.Task("x", "and", 2, 0b1010)]
    base = lineage.replace_procedure(lineage.initial_state(), _procedure(admit=11))
    tried = []
    for seed in range(4):
        out = lineage.step(base, single, 100, Meter(BIG), _rng(seed))
        assert out["adopted"] is False and out["procedure"] == base["procedure"]
        assert out["library"] == base["library"] and out["score"] == out["parent_score"]
        tried.append(out["evaluated"])
    assert any(tried)


def test_a_candidate_is_adopted_only_when_strictly_better():
    states = _run(4)
    for before, after in zip(states, states[1:]):
        if after["adopted"]:
            assert tuple(after["score"]) > tuple(after["parent_score"])
            assert after["procedure"] != before["procedure"]
        else:
            assert after["score"] == after["parent_score"]
            assert after["procedure"] == before["procedure"]


def test_adoption_of_a_strictly_better_candidate_with_a_controlled_fixture(monkeypatch):
    base = lineage.replace_procedure(lineage.initial_state(), _procedure(admit=11))
    expected = {"parent": base["procedure"]["procedure_digest"]}
    calls = []

    def fake_improved_by(current, given, budget, baseline, procedure, meter, generation=None):
        digest = cp.to_record(procedure)["procedure_digest"]
        calls.append(digest)
        score = (0, -5) if digest == expected["parent"] else (1, -5)
        return current, score, {"spent": {}, "exhausted": False}

    monkeypatch.setattr(engine, "improved_by", fake_improved_by)
    monkeypatch.setattr(lineage, "_score", lambda x: x)
    retained = []
    for seed in range(8):
        expected["parent"] = base["procedure"]["procedure_digest"]
        out = lineage.step(base, LEARN, BUDGET, Meter(BIG), _rng(seed))
        assert out["evaluated"]
        retained.append(seed)
        assert out["adopted"] is True
        assert out["exhausted"] is False
        assert out["parent_score"] == [0, -5] and out["score"] == [1, -5]
        adopted = out["procedure"]["procedure_digest"]
        assert adopted == out["evaluated"][0]
        assert adopted != base["procedure"]["procedure_digest"]
        assert out["procedure"] != base["procedure"]
        assert out["library"] == base["library"]
        assert out["parent"] == base["digest"]
        expected["parent"] = adopted
        calls.clear()
        nxt = lineage.step(out, LEARN, BUDGET, Meter(BIG), _rng(seed, 1))
        assert calls[0] == adopted
        assert nxt["parent"] == out["digest"]
        assert lineage.verify_lineage([base, out, nxt]) is True
    assert retained


def test_replace_procedure_restores_the_ancestor_without_touching_the_library():
    states = _run(3)
    ancestral = lineage.replace_procedure(states[3], cp.seed_procedure())
    assert ancestral["library"] == states[3]["library"]
    assert ancestral["procedure"] == cp.to_record(cp.seed_procedure())
    assert ancestral["index"] == states[3]["index"] and ancestral["parent"] == states[3]["parent"]
    assert lineage.verify_lineage(states[:3] + [ancestral]) is True


def test_bad_arguments_are_refused():
    for bad in (-1, True, 1.5):
        with pytest.raises(lineage.LineageError):
            lineage.run_lineage(bad, LEARN, BUDGET, BIG, 1)
        with pytest.raises(lineage.LineageError):
            lineage.run_lineage(1, LEARN, BUDGET, bad, 1)


def test_a_state_reloaded_from_json_is_refused_explicitly_by_step():
    states = _run(2)
    assert states[1].engine is not None
    reloaded = json.loads(json.dumps(states[1]))
    assert lineage.verify_state(reloaded) is None
    with pytest.raises(lineage.LineageError, match="no live library"):
        lineage.step(reloaded, LEARN, BUDGET, Meter(BIG), _rng(1))
    live = lineage.step(states[1], LEARN, BUDGET, Meter(BIG), _rng(1))
    assert lineage.verify_lineage([*states[:2], live]) is True


def test_replace_procedure_neutralises_the_selection_fields_and_gives_a_new_digest():
    states = _run(3)
    source = states[3]
    replaced = lineage.replace_procedure(source, _procedure(admit=11))
    assert replaced["adopted"] is False and replaced["evaluated"] == []
    assert replaced["score"] is None and replaced["parent_score"] is None
    assert replaced["spent"] == source["spent"] and replaced["exhausted"] == source["exhausted"]
    assert replaced["library"] == source["library"]
    assert replaced["digest"] != source["digest"]
    assert lineage.verify_lineage(states[:3] + [replaced]) is True


BAD_FIELDS = (
    ("score", "x"),
    ("score", [1]),
    ("score", [1, True]),
    ("score", [1, 2.5]),
    ("score", [1, 2, 3]),
    ("parent_score", [0, 1, 2]),
    ("parent_score", "x"),
    ("adopted", 1),
    ("adopted", "yes"),
    ("exhausted", None),
    ("exhausted", 0),
    ("evaluated", "abc"),
    ("evaluated", [1]),
    ("library", {}),
    ("library", "x"),
    ("library", [1]),
    ("library", [{}, 3]),
)


@pytest.mark.parametrize("position", [1, -1])
def test_a_resealed_state_with_badly_typed_fields_is_refused(position):
    states = _run(3)
    for name, value in BAD_FIELDS:
        chain = [dict(state) for state in states]
        chain[position] = lineage.seal({**chain[position], name: value})
        with pytest.raises(lineage.LineageError):
            lineage.verify_lineage(chain)


def test_the_last_link_is_checked_even_when_its_digest_is_consistent():
    states = _run(3)
    last = lineage.seal({**states[-1], "score": "arbitrary"})
    assert last["digest"] != states[-1]["digest"]
    with pytest.raises(lineage.LineageError):
        lineage.verify_state(last)
    with pytest.raises(lineage.LineageError):
        lineage.verify_lineage([*states[:-1], last])


@pytest.mark.parametrize(
    ("build", "sealed"),
    [
        pytest.param(lambda states: states[3:], False, id="extracted-tail"),
        pytest.param(lambda states: [states[1], states[2]], False, id="pair-without-root"),
        pytest.param(
            lambda states: [lineage.seal({**states[0], "parent": "0" * 64})],
            True,
            id="resealed-index-0-with-parent",
        ),
        pytest.param(
            lambda states: [lineage.seal({**states[0], "index": 1})],
            True,
            id="resealed-index-1-no-parent",
        ),
    ],
)
def test_a_chain_must_start_at_a_true_root(build, sealed):
    states = _run(4)
    chain = build(states)
    if sealed:
        assert lineage.verify_state(chain[0]) is None
    with pytest.raises(lineage.LineageError, match="first generation must have index 0 and no parent"):
        lineage.verify_lineage(chain)
    assert lineage.verify_lineage(states) is True
    assert lineage.verify_lineage([states[0]]) is True
