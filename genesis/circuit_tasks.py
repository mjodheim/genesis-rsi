"""Truth tables to synthesise, by family. Families are split once and for all between those an
engine may learn from and those kept to judge it; nothing here is drawn from solutions."""
from __future__ import annotations

from functools import lru_cache
import random

from genesis.circuit_engine import Task

LEARN = ("and", "or", "parity", "equal", "mux", "adder", "majority")
HELD_OUT = ("less", "subtract", "popcount", "exactly", "multiply")
CONTROL = ("random",)      # no structure to reuse: a library should bring little here


def _table(inputs: int, function) -> int:
    return sum(int(bool(function([(row >> index) & 1 for index in range(inputs)]))) << row for row in range(1 << inputs))


def _number(bits) -> int:
    return sum(bit << index for index, bit in enumerate(bits))


def tasks(family: str, seed: int = 0) -> list[Task]:
    made: list[tuple[str, int, object]] = []
    if family == "and":
        made = [(f"and{n}", n, all) for n in range(2, 7)] + [(f"nor{n}", n, lambda x: not any(x)) for n in range(2, 7)]
    elif family == "or":
        made = [(f"or{n}", n, any) for n in range(2, 7)]
    elif family == "parity":
        made = [(f"parity{n}", n, lambda x: sum(x) % 2) for n in range(2, 7)]
    elif family == "majority":
        made = [(f"atleast{k}of{n}", n, lambda x, k=k: sum(x) >= k) for n in range(3, 6) for k in range(2, n)]
    elif family == "exactly":
        made = [(f"exactly{k}of{n}", n, lambda x, k=k: sum(x) == k) for n in range(3, 6) for k in range(1, n)]
    elif family == "popcount":
        made = [(f"count{n}bit{j}", n, lambda x, j=j: (sum(x) >> j) & 1) for n in range(3, 7) for j in range(1, n.bit_length())]
    elif family == "mux":
        made = [("mux2", 3, lambda x: x[1 + x[0]]), ("mux3", 5, lambda x: x[2 + min(x[0] + 2 * x[1], 2)]),
                ("mux4", 6, lambda x: x[2 + x[0] + 2 * x[1]])]
    elif family in ("adder", "subtract", "less", "equal", "multiply"):
        for width in (1, 2, 3):
            n = 2 * width
            a, b = (lambda x, w=width: _number(x[:w])), (lambda x, w=width: _number(x[w:2 * w]))
            if family == "adder":
                made += [(f"add{width}bit{j}", n, lambda x, j=j, a=a, b=b: ((a(x) + b(x)) >> j) & 1) for j in range(width + 1)]
                made += [(f"addc{width}bit{j}", n + 1, lambda x, j=j, a=a, b=b, n=n: ((a(x) + b(x) + x[n]) >> j) & 1)
                         for j in range(width + 1)]
            elif family == "subtract":
                made += [(f"sub{width}bit{j}", n, lambda x, j=j, a=a, b=b, w=width: (((a(x) - b(x)) % (2 << w)) >> j) & 1)
                         for j in range(width + 1)]
            elif family == "less":
                made += [(f"less{width}", n, lambda x, a=a, b=b: a(x) < b(x)), (f"lesseq{width}", n, lambda x, a=a, b=b: a(x) <= b(x))]
            elif family == "equal":
                made += [(f"equal{width}", n, lambda x, a=a, b=b: a(x) == b(x))]
            elif width > 1:
                made += [(f"mul{width}bit{j}", n, lambda x, j=j, a=a, b=b: ((a(x) * b(x)) >> j) & 1) for j in range(2 * width)]
    elif family == "random":
        rng = random.Random(f"random|{seed}")
        return [Task(f"random{n}n{index}", family, n, rng.getrandbits(1 << n)) for n in (3, 4) for index in range(8)]
    else:
        raise ValueError(family)
    return [Task(name, family, inputs, _table(inputs, function)) for name, inputs, function in made]


def suite(families, seed: int = 0) -> list[Task]:
    return [task for family in families for task in tasks(family, seed)]


CIRCUIT2_ATTEMPTS = 64
CIRCUIT2_MAX_INPUTS = 6


def _transform(inputs: int, target: int, order, negate: bool, negate_inputs: int = 0) -> int:
    table = 0
    for row in range(1 << inputs):
        source = sum((((row >> order[index]) & 1) ^ ((negate_inputs >> index) & 1)) << index for index in range(inputs))
        table |= (((target >> source) & 1) ^ int(negate)) << row
    return table


CIRCUIT2_ORDER = (*LEARN, *HELD_OUT, *CONTROL)


@lru_cache(maxsize=None)
def _circuit2_assignment(seed: int) -> dict[str, tuple[Task, ...]]:
    known = {(t.inputs, t.target) for family in CIRCUIT2_ORDER for t in tasks(family, seed)
             if t.inputs <= CIRCUIT2_MAX_INPUTS}
    chosen: set[tuple[int, int]] = set()
    assigned: dict[str, tuple[Task, ...]] = {}
    for family in CIRCUIT2_ORDER:
        made: list[Task] = []
        for task in tasks(family, seed):
            if task.inputs > CIRCUIT2_MAX_INPUTS:
                continue
            rng = random.Random(f"circuit2|{family}|{task.name}")
            for _ in range(CIRCUIT2_ATTEMPTS):
                order = list(range(task.inputs))
                # RNG draws per attempt, in this fixed order: (a) rng.shuffle(order);
                # (b) rng.random() < 0.5 for the output negation;
                # (c) rng.getrandbits(task.inputs) for the input-negation mask.
                rng.shuffle(order)
                negate = rng.random() < 0.5
                mask = rng.getrandbits(task.inputs)
                table = _transform(task.inputs, task.target, order, negate, mask)
                key = (task.inputs, table)
                if key in known or key in chosen:
                    continue
                chosen.add(key)
                made.append(Task(f"c2_{task.name}", family, task.inputs, table))
                break
        assigned[family] = tuple(made)
    return assigned


def circuit2_tasks(family: str, seed: int = 0) -> list[Task]:
    """CIRCUIT2 instances derived from CIRCUIT1 tasks by three transformations: a permutation of
    the inputs, a negation of a random subset of the inputs, and a negation of the output.

    Limit: these transformations stay in the same NPN class as the source CIRCUIT1 task. Only the
    disjointness of (arity, table) is guaranteed, not an NPN separation between learning and
    evaluation. c2_parity2 and c2_sub1bit0 remain excluded, XOR and XNOR both being in CIRCUIT1.

    Attribution is global: a table is kept only if its canonical (arity, table) is absent from
    every CIRCUIT1 task (LEARN, HELD_OUT, CONTROL) and from every table already chosen. Families are
    visited in the fixed order LEARN, HELD_OUT, CONTROL, tasks in tasks() order, so priority goes to
    LEARN and HELD_OUT loses on collision. A task with no new table within 64 attempts is dropped."""
    if family not in CIRCUIT2_ORDER:
        raise ValueError(family)
    return list(_circuit2_assignment(seed)[family])


def circuit2_suite(families, seed: int = 0) -> list[Task]:
    return [task for family in families for task in circuit2_tasks(family, seed)]
