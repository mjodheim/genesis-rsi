import copy
import itertools
import json
import random
from dataclasses import replace

import pytest

from genesis import circuit_procedure as cp

CASES = [tuple(bits) for bits in itertools.product((0, 1), repeat=len(cp.TRAITS))]


def test_validation_accepts_seed_and_random_procedures():
    cp.validate(cp.seed_procedure())
    for seed in range(20):
        cp.validate(cp.random_procedure(random.Random(seed), 1 + (seed * 3) % 64))


def test_validation_rejects_malformed_procedures():
    p = cp.seed_procedure()
    n, rest = p.n_inputs, p.steps[1:]
    bad = [
        replace(p, steps=((0, n),) + rest),
        replace(p, steps=((0, n + 1),) + rest),
        replace(p, steps=((0, 10**6),) + rest),
        replace(p, steps=((0, -1),) + rest),
        replace(p, steps=((0, True),) + rest),
        replace(p, steps=((0, 0),) * (cp.MAX_STEPS + 1)),
        replace(p, n_inputs=n - 1),
        replace(p, admit_output=n + len(p.steps)),
        replace(p, admit_output=True),
        replace(p, priority_outputs=(0,)),
        replace(p, priority_outputs=(0, n + len(p.steps))),
    ]
    for item in bad:
        with pytest.raises(cp.ProcedureError):
            cp.validate(item)


def _alter_step(r):
    r["steps"][0] = [(r["steps"][0][0] + 1) % r["n_inputs"], r["steps"][0][1]]


def _alter_admit(r):
    r["admit_output"] = 0


def _alter_priority(r):
    r["priority_outputs"] = [0, 0]


def _alter_digest(r):
    r["procedure_digest"] = "tampered"


def _alter_schema(r):
    r["schema"] = "autre"


def _add_key(r):
    r["extra"] = 1


def test_roundtrip_keeps_digest_and_tampering_is_refused():
    p = cp.seed_procedure()
    rec = cp.to_record(p)
    again = json.loads(json.dumps(rec))
    assert again == rec and rec["schema"] == "genesis-circuit-procedure-v1"
    assert rec["traits"] == list(cp.TRAIT_NAMES)
    q = cp.from_record(again)
    assert q == p and cp.to_record(q) == rec
    assert json.dumps(cp.to_record(q), sort_keys=True) == json.dumps(rec, sort_keys=True)
    for alter in (_alter_step, _alter_admit, _alter_priority, _alter_digest, _alter_schema, _add_key):
        broken = copy.deepcopy(rec)
        alter(broken)
        with pytest.raises(cp.ProcedureError):
            cp.from_record(broken)
    with pytest.raises(cp.ProcedureError):
        cp.from_record([])


def test_run_is_deterministic_and_counts_its_gates():
    procedures = [cp.seed_procedure()] + [cp.random_procedure(random.Random(s), s) for s in range(10)]
    for q in procedures:
        for case in CASES[::37]:
            first = cp.run(q, case)
            assert first == cp.run(q, case) and first[2] == len(q.steps)
            assert isinstance(first[0], int) and isinstance(first[1], bool)


def test_a_single_changed_step_changes_the_replay():
    p = cp.seed_procedure()
    twin = cp.from_record(cp.to_record(p))
    assert cp.replay_digest(p, CASES) == cp.replay_digest(twin, CASES)
    g = p.steps[-1][0]
    changed = replace(p, steps=p.steps[:-1] + ((g, 0),))
    cp.validate(changed)
    assert cp.replay_digest(changed, CASES) != cp.replay_digest(p, CASES)
    assert any(cp.run(changed, c) != cp.run(p, c) for c in CASES)


def test_seed_priority_grows_with_support():
    p = cp.seed_procedure()
    priorities = [cp.run(p, cp.traits_of(s, 2, 1, False))[0] for s in range(9)]
    assert priorities == sorted(priorities) and priorities[-1] > priorities[0]
    assert cp.run(p, cp.traits_of(1, 2, 1, False))[1] is False
    assert cp.run(p, cp.traits_of(2, 3, 1, False))[1] is True
    assert cp.run(p, cp.traits_of(2, 4, 1, False))[1] is False


def test_rank_is_stable_and_deterministic():
    p = cp.seed_procedure()
    candidates = [
        ("b", 6, 2, 3, False),
        ("a", 4, 3, 2, True),
        ("c", 3, 2, 1, False),
        ("d", 2, 2, 1, False),
        ("e", 1, 2, 1, False),
        ("f", 5, 4, 2, False),
    ]
    expected = [("a", 3), ("b", 3), ("c", 2), ("d", 1)]
    assert cp.rank(p, candidates) == expected
    shuffled = list(candidates)
    random.Random(1).shuffle(shuffled)
    assert cp.rank(p, shuffled) == expected == cp.rank(p, candidates)


def test_traits_of_takes_only_integers_and_booleans():
    assert cp.traits_of(2, 3, 4, True) == (1, 0, 0, 0, 1, 0, 1, 1, 0, 1)
    assert cp.traits_of(0, 0, 0, False) == (0,) * len(cp.TRAITS)
    assert len(cp.TRAIT_NAMES) == len(cp.TRAITS) == 10
    for args in ((1.5, 3, 4, True), (2, "3", 4, True), (2, 3, None, True), (2, 3, 4, 1.0), (2, 3, 4, "x")):
        with pytest.raises(TypeError):
            cp.traits_of(*args)
    assert cp.traits_of(True, False, True, True) == cp.traits_of(1, 0, 1, 1)
