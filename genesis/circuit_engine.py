"""A solver whose capability lies in its own code and data, and the step that improves it.

The solver builds a logic circuit for a target truth table. It starts with one component, NAND,
and searches bottom-up in increasing total weight of the components used: signals with the same
truth table are kept once, and every component application counts against a budget of
evaluations. No model is involved and nothing depends on the clock:
the same engine, tasks and budget give the same result.

An *engine* is what a generation hands to the next: a library of components (each a small NAND
circuit of at most three inputs, found in earlier solutions), the weight each costs in the
search and the order in which they are tried. The *improvement step* reads the circuits the engine found, proposes components that
recur across tasks, and keeps the proposal only if the engine then solves more of the tasks it
learns from, or as many with fewer evaluations. A later step can propose components made of
earlier ones: that is the only way a generation can be better placed to improve than the one
before, and it is what the lineage script measures.

Prior art: library learning from solved tasks (Ellis et al., DreamCoder, 2021), bottom-up
enumeration with observational equivalence, cut enumeration in logic synthesis.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import combinations, combinations_with_replacement, permutations, product
import random
from typing import Iterable, Sequence

MAX_ARITY = 3


def variables(n: int) -> list[int]:
    """Truth tables of the n inputs, as integers of 2**n bits."""
    return [sum(((row >> index) & 1) << row for row in range(1 << n)) for index in range(n)]


@dataclass(frozen=True)
class Component:
    """A function of ``arity`` inputs given as NAND steps over its inputs and earlier steps; the last is its output."""

    name: str
    arity: int
    steps: tuple[tuple[int, int], ...]
    weight: int = 1      # what one use costs in the search: signals are built in increasing total weight

    def apply(self, arguments: Sequence[int], mask: int) -> int:
        values = list(arguments)
        for left, right in self.steps:
            values.append(~(values[left] & values[right]) & mask)
        return values[-1]

    @property
    def table(self) -> int:
        return self.apply(variables(self.arity), (1 << (1 << self.arity)) - 1)

    @property
    def key(self) -> tuple[int, int]:
        """The same for two components that differ by the order of their inputs."""
        base = variables(self.arity)
        mask = (1 << (1 << self.arity)) - 1
        return self.arity, min(self.apply([base[i] for i in order], mask) for order in permutations(range(self.arity)))

    @property
    def symmetric(self) -> bool:
        base = variables(self.arity)
        mask = (1 << (1 << self.arity)) - 1
        return len({self.apply([base[i] for i in order], mask) for order in permutations(range(self.arity))}) == 1


NAND = Component("nand", 2, ((0, 1),))


@dataclass
class Engine:
    """What one generation hands to the next. Components are tried in this order."""

    components: list[Component] = field(default_factory=lambda: [NAND])

    def record(self) -> list[dict]:
        return [{"name": item.name, "arity": item.arity, "weight": item.weight, "nands": len(item.steps), "table": item.table,
                 "steps": [list(step) for step in item.steps]} for item in self.components]


@dataclass(frozen=True)
class Task:
    name: str
    family: str
    inputs: int
    target: int


@dataclass
class Solution:
    solved: bool
    evaluations: int
    cost: int | None = None
    tree: tuple | None = None       # (component name, child trees) with ("in", index) at the leaves


def solve(engine: Engine, task: Task, budget: int) -> Solution:
    """Search for a circuit computing ``task.target`` within ``budget`` component applications."""
    mask = (1 << (1 << task.inputs)) - 1
    inputs = variables(task.inputs)
    origin: dict[int, tuple] = {table: ("in", index) for index, table in enumerate(inputs)}
    levels: list[list[int]] = [list(origin)]
    used = 0

    def tree(table: int) -> tuple:
        made = origin[table]
        return made if made[0] == "in" else (made[0], tuple(tree(child) for child in made[1]))

    if task.target in origin:
        return Solution(True, 0, 0, tree(task.target))
    while True:
        cost, fresh = len(levels), []
        for component in engine.components:
            symmetric = component.symmetric
            for split in _splits(cost - component.weight, component.arity, symmetric) if cost >= component.weight else ():
                pools = [levels[part] for part in split]
                if symmetric and len(set(split)) == 1:
                    tuples: Iterable = combinations_with_replacement(pools[0], component.arity)
                elif symmetric:
                    tuples = _sorted_product(pools, split)
                else:
                    tuples = product(*pools)
                for arguments in tuples:
                    if used >= budget:
                        return Solution(False, used)
                    used += 1
                    table = component.apply(arguments, mask)
                    if table in origin:
                        continue
                    origin[table] = (component.name, arguments)
                    fresh.append(table)
                    if table == task.target:
                        return Solution(True, used, cost, tree(table))
        levels.append(fresh)
        if cost > 64 or (cost > 8 and not any(levels[-8:])):
            return Solution(False, used)


def _splits(total: int, parts: int, symmetric: bool) -> list[tuple[int, ...]]:
    """Ways to give ``total`` components to ``parts`` arguments; non-decreasing ones only when order is irrelevant."""
    found = [split for split in product(range(total + 1), repeat=parts) if sum(split) == total]
    return [split for split in found if not symmetric or list(split) == sorted(split)]


def _sorted_product(pools: Sequence[list[int]], split: Sequence[int]) -> Iterable[tuple[int, ...]]:
    """Product of the pools without the reorderings inside a run of equal levels."""
    groups, start = [], 0
    for index in range(1, len(split) + 1):
        if index == len(split) or split[index] != split[start]:
            groups.append(combinations_with_replacement(pools[start], index - start))
            start = index
    for chosen in product(*groups):
        yield tuple(item for group in chosen for item in group)


# --------------------------------------------------------------------------- the improvement step

def _expanded(tree: tuple, library: dict[str, Component], leaves: list, steps: list) -> int:
    """Append to ``steps`` the NANDs computing ``tree`` over ``leaves``; returns the index of its value."""
    if tree in leaves:
        return leaves.index(tree)
    component = library[tree[0]]
    arguments = [_expanded(child, library, leaves, steps) for child in tree[1]]
    local = list(arguments)
    for left, right in component.steps:
        steps.append((local[left], local[right]))
        local.append(len(leaves) + len(steps) - 1)
    return local[-1]


def _cuts(tree: tuple, layers: int, arity: int, limit: int = 200) -> list[tuple]:
    """Leaf sets of the sub-circuits rooted at ``tree`` that are at most ``layers`` components deep and
    read at most ``arity`` distinct signals."""
    choices = []
    for child in tree[1]:
        options = [(child,)]
        if child[0] != "in" and layers > 1:
            options += _cuts(child, layers - 1, arity, limit)
        choices.append(options)
    found = []
    for chosen in product(*choices):
        leaves: list = []
        for group in chosen:
            for leaf in group:
                if leaf not in leaves:
                    leaves.append(leaf)
        if len(leaves) <= arity and tuple(leaves) not in found:
            found.append(tuple(leaves))
            if len(found) >= limit:
                break
    return found


def _patterns(tree: tuple, layers: int = 2, arity: int = MAX_ARITY) -> Iterable[tuple[tuple, list]]:
    """Sub-circuits around each node, with the signals they read. One component reading distinct signals
    is not a pattern: it is the component."""
    if tree[0] == "in":
        return
    for leaves in _cuts(tree, layers, arity):
        if not (len(leaves) == len(tree[1]) and all(leaf in tree[1] for leaf in leaves)):
            yield tree, list(leaves)
    for child in tree[1]:
        yield from _patterns(child, layers, arity)


def proposals(engine: Engine, solutions: Sequence[Solution], layers: int = 2, arity: int = MAX_ARITY) -> list[tuple[Component, int]]:
    """New components found in the solutions, with the number of tasks each occurs in, most shared first."""
    library = {item.name: item for item in engine.components}
    known = {item.key for item in engine.components}
    support: Counter = Counter()
    smallest: dict[tuple, Component] = {}
    for solution in solutions:
        seen = set()
        for tree, leaves in _patterns(solution.tree, layers, arity) if solution.solved and solution.tree else ():
            steps: list = []
            _expanded(_cut(tree, leaves), library, leaves, steps)
            component = Component("", len(leaves), tuple(steps))
            table, full = component.table, (1 << (1 << component.arity)) - 1
            if table in (0, full) or any(_ignores(component, index) for index in range(component.arity)):
                continue
            key = component.key
            if key in known:
                continue
            seen.add(key)
            if key not in smallest or len(steps) < len(smallest[key].steps):
                smallest[key] = component
        support.update(seen)
    ranked = sorted(support, key=lambda key: (-support[key], len(smallest[key].steps), key))
    return [(smallest[key], support[key]) for key in ranked]


def _cut(tree: tuple, leaves: list) -> tuple:
    """``tree`` kept down to ``leaves`` (which are subtrees of it)."""
    if tree in leaves or tree[0] == "in":
        return tree
    return (tree[0], tuple(_cut(child, leaves) for child in tree[1]))


def _ignores(component: Component, index: int) -> bool:
    base = variables(component.arity)
    mask = (1 << (1 << component.arity)) - 1
    flipped = [(~value & mask) if position == index else value for position, value in enumerate(base)]
    return component.apply(base, mask) == component.apply(flipped, mask)


def attempt(engine: Engine, tasks: Sequence[Task], budget: int) -> list[Solution]:
    return [solve(engine, task, budget) for task in tasks]


def measure(solutions: Sequence[Solution]) -> tuple[int, int]:
    """Tasks solved, and evaluations spent; engines are compared on the first, then on the second (fewer is better)."""
    return sum(solution.solved for solution in solutions), sum(solution.evaluations for solution in solutions)


def uses(solutions: Sequence[Solution]) -> Counter:
    """How often each component occurs in the circuits found."""
    use: Counter = Counter()

    def count(tree: tuple) -> None:
        if tree[0] != "in":
            use[tree[0]] += 1
            for child in tree[1]:
                count(child)
    for solution in solutions:
        if solution.solved and solution.tree:
            count(solution.tree)
    return use


SEED_PROCEDURE = {"tried": 6, "min_support": 2, "ranking": "support", "heaviest": 4, "drop_unused": True, "arity": 3}


def refitted(engine: Engine, solutions: Sequence[Solution], procedure: dict) -> Engine:
    """The engine with weights and order set from use: the most used component weighs 1, one used half
    as often weighs 2, and so on up to ``heaviest``; with ``drop_unused`` a learnt component no circuit
    uses is dropped."""
    use = uses(solutions)
    most = max(use.values(), default=1)
    kept = []
    for item in engine.components:
        if use[item.name] or item.name == NAND.name or not procedure["drop_unused"]:
            weight = (min(procedure["heaviest"], (most // use[item.name]).bit_length()) if use[item.name]
                      else 1 if item.name == NAND.name else procedure["heaviest"])
            kept.append(Component(item.name, item.arity, item.steps, weight))
    return Engine(sorted(kept, key=lambda item: (item.weight, -use[item.name])))


def improved(engine: Engine, tasks: Sequence[Task], budget: int, solutions: Sequence[Solution], *, generation: int,
             procedure: dict = SEED_PROCEDURE, rng: random.Random | None = None,
             ranker: Sequence[float] | None = None) -> tuple[Engine, list[Solution], dict]:
    """One improvement step under ``procedure``. The ``tried`` best-ranked new components are each added
    alone, the engine is refitted to what it then finds, and the best is kept if the engine solves more
    of ``tasks``, or as many with fewer evaluations. Returns the engine to hand on (the same object when
    nothing passes), its solutions and what was tried. Ranking is by the number of tasks a component
    occurs in ("support"), by that number times the NANDs it stands for ("saving"), or drawn with
    ``rng`` ("random"), or by ``ranker``, the weights of a linear score over ``features`` fitted on the
    trials of earlier lineages ("learned")."""
    found = [(component, support) for component, support in
             proposals(engine, solutions, procedure.get("layers", 2), max(MAX_ARITY, procedure["arity"]))
             if support >= procedure["min_support"] and component.arity <= procedure["arity"]]
    if procedure["ranking"] == "learned":
        scores = {id(pair[0]): sum(w * x for w, x in zip(ranker, features(pair[0].arity, pair[0].table, len(pair[0].steps), pair[1],
                                                                              generation, len(engine.components))))
                  for pair in found}
        found.sort(key=lambda pair: -scores[id(pair[0])])
    elif procedure["ranking"] == "saving":
        found.sort(key=lambda pair: -pair[1] * len(pair[0].steps))
    elif procedure["ranking"] == "random":
        (rng or random.Random(generation)).shuffle(found)
    before, trials, best = measure(solutions), [], None
    for index, (component, support) in enumerate(found[:procedure["tried"]]):
        added = Component(f"g{generation}c{index}", component.arity, component.steps)
        wider = Engine(engine.components + [added])
        candidate = refitted(wider, attempt(wider, tasks, budget), procedure)
        after_solutions = attempt(candidate, tasks, budget)
        after = measure(after_solutions)
        trials.append({"name": added.name, "arity": added.arity, "nands": len(added.steps), "table": added.table,
                       "support": support, "solved": after[0], "evaluations": after[1], "library": len(engine.components)})
        if (after[0], -after[1]) > (before[0], -before[1]) and (best is None or (after[0], -after[1]) > best[0]):
            best = ((after[0], -after[1]), candidate, after_solutions, added.name)
    info = {"candidates": len(found), "trials": trials, "added": best[3] if best else None}
    return (best[1], best[2], info) if best else (engine, list(solutions), info)


def features(arity: int, table: int, nands: int, support: int, generation: int, library: int) -> list[float]:
    """What a ranker may know of a proposed component before it is tried."""
    rows = 1 << arity
    bits = [(table >> row) & 1 for row in range(rows)]
    ones = sum(bits) / rows
    parity = [bin(row).count("1") & 1 for row in range(rows)]
    xor_like = bits == parity or bits == [1 - bit for bit in parity]
    rising = all(bits[row] <= bits[row | (1 << index)] for row in range(rows) for index in range(arity))
    falling = all(bits[row] >= bits[row | (1 << index)] for row in range(rows) for index in range(arity))
    symmetric = all(bits[row] == bits[other] for row in range(rows) for other in range(rows)
                    if bin(row).count("1") == bin(other).count("1"))
    return [1.0, float(arity == 1), float(arity == 2), float(arity == 3), float(arity >= 4), float(nands),
            float(min(support, 10)), abs(ones - 0.5), float(xor_like), float(rising or falling), float(symmetric),
            float(generation), float(library)]


def together(engine: Engine, tasks: Sequence[Task], budget: int, solutions: Sequence[Solution], count: int,
             procedure: dict = SEED_PROCEDURE) -> tuple[Engine, list[Solution]]:
    """Control without accumulation: the ``count`` best-ranked components of one reading of the
    solutions, added at once and refitted, whatever the result."""
    found = [(component, support) for component, support in proposals(engine, solutions)
             if support >= procedure["min_support"] and component.arity <= procedure["arity"]]
    wider = Engine(engine.components + [Component(f"once{index}", component.arity, component.steps)
                                        for index, (component, _) in enumerate(found[:count])])
    candidate = refitted(wider, attempt(wider, tasks, budget), procedure)
    return candidate, attempt(candidate, tasks, budget)
