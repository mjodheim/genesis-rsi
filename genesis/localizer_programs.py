"""Small programs over the answers of archived localizers, found by search rather than written.

RECOMBINE1 merged two localizers with one rule fixed by hand. Here the rule itself is searched.
A *program* is a tree of nine operations on ranked lists of ``[path, line]``; its leaves are
members of the archive. Programs are data: they are bounded in size, read no file and run no
code of a model, so judging one costs arithmetic on answers computed once.

Each generation the system first measures what recombination can still reach (the cases some
member localizes and the champion misses), then searches programs by mutation and crossover on
search cases, and submits the best one to the selection cases under the rule of the lineage. A
promoted program joins the archive under its name and is a leaf for the generations after it.
"""
from __future__ import annotations

import random
from typing import Callable, Mapping, Sequence

from genesis.localizer_lineage import MAX_LOCATIONS, WINDOW, compare, covers, evaluate, promotes
from genesis.trust_root import digest_of

PROGRAM_SCHEMA = "genesis-localizer-program-v1"
MAX_NODES = 15
MAX_ITEMS = 2 * MAX_LOCATIONS
UNARY = {"head": (1, 2, 3, 4, 5), "tail": (1, 2, 3, 4, 5), "apart": (10, 20, 40), "shift": (-30, -15, 15, 30)}
BINARY = ("join", "weave", "agree", "files")
OPERATIONS = tuple(UNARY) + BINARY

Program = tuple
Locations = list


# -- the language -------------------------------------------------------------------------------


def member(name: str) -> Program:
    return ("member", name)


def size(program: Program) -> int:
    if program[0] == "member":
        return 1
    return 1 + sum(size(part) for part in program[1:] if isinstance(part, tuple))


def leaves(program: Program) -> list[str]:
    if program[0] == "member":
        return [program[1]]
    return [name for part in program[1:] if isinstance(part, tuple) for name in leaves(part)]


def operations(program: Program) -> list[str]:
    if program[0] == "member":
        return []
    return [program[0]] + [name for part in program[1:] if isinstance(part, tuple) for name in operations(part)]


def checked(program: object, known: Sequence[str], allowed: Sequence[str] = OPERATIONS) -> Program:
    """The program as nested tuples, or ValueError when it leaves the language."""

    def walk(node: object) -> Program:
        if not isinstance(node, (list, tuple)) or not node or not isinstance(node[0], str):
            raise ValueError("a program is a list that starts with an operation")
        name = node[0]
        if name == "member":
            if len(node) != 2 or node[1] not in known:
                raise ValueError("unknown member")
            return ("member", node[1])
        if name not in allowed:
            raise ValueError(f"operation {name!r} is not in the language")
        if name in UNARY:
            if len(node) != 3 or node[1] not in UNARY[name]:
                raise ValueError(f"{name} takes one of {UNARY[name]} and one program")
            return (name, node[1], walk(node[2]))
        if len(node) != 3:
            raise ValueError(f"{name} takes two programs")
        return (name, walk(node[1]), walk(node[2]))

    result = walk(program)
    if size(result) > MAX_NODES:
        raise ValueError("program too large")
    return result


def named(program: Program) -> str:
    return "p-" + digest_of({"schema": PROGRAM_SCHEMA, "program": program})[:12]


def _near(item: Sequence, others: Sequence[Sequence], distance: int) -> bool:
    return any(path == item[0] and abs(line - item[1]) <= distance for path, line in others)


def run(program: Program, answers: Callable[[str], Sequence[Sequence]]) -> Locations:
    """Evaluate a program on one case. ``answers`` gives a member's locations for that case."""
    name = program[0]
    if name == "member":
        return [list(item) for item in answers(program[1])][:MAX_ITEMS]
    if name in UNARY:
        amount, items = program[1], run(program[2], answers)
        if name == "head":
            return items[:amount]
        if name == "tail":
            return items[amount:]
        if name == "shift":
            return [[path, max(1, line + amount)] for path, line in items]
        kept: Locations = []
        for item in items:
            if not _near(item, kept, amount):
                kept.append(item)
        return kept
    first, second = run(program[1], answers), run(program[2], answers)
    if name == "join":
        merged = first + [item for item in second if item not in first]
    elif name == "weave":
        merged = []
        for index in range(max(len(first), len(second))):
            for source in (first, second):
                if index < len(source) and source[index] not in merged:
                    merged.append(source[index])
    elif name == "agree":
        merged = [item for item in first if _near(item, second, WINDOW)]
    else:
        files = {path for path, _ in second}
        merged = [item for item in first if item[0] in files]
    return merged[:MAX_ITEMS]


def answers_of(program: Program, known: Mapping[str, Mapping[str, list]], cases: Sequence[str]) -> dict[str, list]:
    return {case: run(program, lambda name, case=case: known[name].get(case, ()))[:MAX_LOCATIONS] for case in cases}


# -- what recombination can still reach ---------------------------------------------------------


def diagnosis(champion: str, known: Mapping[str, Mapping[str, list]], truth: Mapping, cases: Sequence[str]) -> dict:
    """Split the champion's misses by whether the archive already holds what is missing.

    ``one_member`` misses are localized by some member alone; ``pooled`` ones have every edit
    site covered by a location of some member, but by no single member; the others need
    evidence no member produces, whatever the combination.
    """
    missed = one_member = pooled = 0
    for case in cases:
        sites = truth[case]
        if all(covers(site, known[champion].get(case, ())) for site in sites):
            continue
        missed += 1
        if any(all(covers(site, answers.get(case, ())) for site in sites) for answers in known.values()):
            one_member += 1
        elif all(any(covers(site, answers.get(case, ())) for answers in known.values()) for site in sites):
            pooled += 1
    return {"cases": len(cases), "missed": missed, "one_member": one_member, "pooled": pooled,
            "out_of_reach": missed - one_member - pooled}


# -- search -------------------------------------------------------------------------------------


class Scorer:
    """Counts the cases a program localizes, with site coverage inlined: this is the hot loop."""

    def __init__(self, known: Mapping[str, Mapping[str, list]], truth: Mapping, cases: Sequence[str]):
        self.cases = list(cases)
        self.sites = [[(site["path"], site["first"], site["last"]) for site in truth[case]] for case in self.cases]
        self.known = {name: [answers.get(case, ()) for case in self.cases] for name, answers in known.items()}
        self.seen: dict[Program, tuple] = {}

    def outcome(self, program: Program) -> tuple:
        """(localized cases, cases with a site covered, the localized cases as a tuple of flags)."""
        if program in self.seen:
            return self.seen[program]
        flags, partial = [], 0
        for index, sites in enumerate(self.sites):
            locations = run(program, lambda name: self.known[name][index])[:MAX_LOCATIONS]
            hits = [any(path == file and line - WINDOW <= first and last <= line + WINDOW for file, line in locations)
                    for path, first, last in sites]
            flags.append(all(hits))
            partial += any(hits)
        self.seen[program] = (sum(flags), partial, tuple(flags))
        return self.seen[program]


def _random_program(rng: random.Random, names: Sequence[str], champion: str, depth: int,
                    allowed: Sequence[str]) -> Program:
    if depth == 0 or rng.random() < 0.3:
        return member(champion if rng.random() < 0.4 else rng.choice(names))
    name = rng.choice(allowed)
    if name in UNARY:
        return (name, rng.choice(UNARY[name]), _random_program(rng, names, champion, depth - 1, allowed))
    return (name, _random_program(rng, names, champion, depth - 1, allowed),
            _random_program(rng, names, champion, depth - 1, allowed))


def _paths(program: Program, prefix: tuple = ()) -> list[tuple]:
    found = [prefix]
    for index, part in enumerate(program):
        if index and isinstance(part, tuple):
            found.extend(_paths(part, prefix + (index,)))
    return found


def _at(program: Program, path: tuple) -> Program:
    for index in path:
        program = program[index]
    return program


def _replaced(program: Program, path: tuple, value: Program) -> Program:
    if not path:
        return value
    return program[:path[0]] + (_replaced(program[path[0]], path[1:], value),) + program[path[0] + 1:]


def mutated(program: Program, other: Program, rng: random.Random, names: Sequence[str], champion: str,
            allowed: Sequence[str]) -> Program:
    """One edit: a new subtree, a wrap, a hoist, a parameter, or a subtree of another program."""
    path = rng.choice(_paths(program))
    node = _at(program, path)
    move = rng.randrange(5)
    if move == 0:
        value = _random_program(rng, names, champion, 2, allowed)
    elif move == 1:
        name = rng.choice(allowed)
        fresh = _random_program(rng, names, champion, 1, allowed)
        if name in UNARY:
            value = (name, rng.choice(UNARY[name]), node)
        else:
            value = (name, node, fresh) if rng.random() < 0.5 else (name, fresh, node)
    elif move == 2:
        parts = [part for part in node[1:] if isinstance(part, tuple)]
        value = rng.choice(parts) if parts else member(rng.choice(names))
    elif move == 3:
        if node[0] in UNARY:
            value = (node[0], rng.choice(UNARY[node[0]]), node[2])
        elif node[0] == "member":
            value = member(rng.choice(names))
        else:
            value = (node[0], node[2], node[1])
    else:
        value = _at(other, rng.choice(_paths(other)))
    child = _replaced(program, path, value)
    return child if size(child) <= MAX_NODES else program


def search(champion: str, scorer: Scorer, *, seed: int, rounds: int, population: int, kept: int,
           allowed: Sequence[str] = OPERATIONS) -> dict:
    """Best program found on the scorer's cases, by mutation and crossover from random programs.

    Programs that localize exactly the same cases count once among the survivors, the smallest
    first, so the population does not fill with spellings of one behaviour.
    """
    rng = random.Random(seed)
    names = sorted(scorer.known)
    pool = {member(champion)} | {member(name) for name in names}
    while len(pool) < population + len(names):
        pool.add(_random_program(rng, names, champion, 3, allowed))
    evaluated = 0
    survivors: list[Program] = []
    for _ in range(rounds):
        ranked = sorted(pool, key=lambda item: (-scorer.outcome(item)[0], -scorer.outcome(item)[1], size(item),
                                                repr(item)))
        evaluated += len(pool)
        survivors, behaviours = [], set()
        for item in ranked:
            flags = scorer.outcome(item)[2]
            if flags not in behaviours:
                behaviours.add(flags)
                survivors.append(item)
            if len(survivors) == kept:
                break
        pool = set(survivors)
        while len(pool) < kept + population:
            first, second = rng.choice(survivors), rng.choice(survivors)
            pool.add(mutated(first, second, rng, names, champion, allowed))
    best = min(pool, key=lambda item: (-scorer.outcome(item)[0], -scorer.outcome(item)[1], size(item), repr(item)))
    return {"program": best, "localized": scorer.outcome(best)[0], "any_site": scorer.outcome(best)[1],
            "programs_scored": len(scorer.seen), "candidates_ranked": evaluated + len(pool)}


# -- generations --------------------------------------------------------------------------------


def scored(locations: Mapping[str, list], truth: Mapping, cases: Sequence[str]) -> dict:
    return evaluate({case: {"locations": locations.get(case, [])} for case in cases}, truth, cases)


def evolve(champion: str, known: dict, truth: Mapping, searching: Sequence[str], selection: Sequence[str], *,
           seed: int, generations: int, rounds: int, population: int, kept: int, margin: int = 5,
           alpha: float = 0.05, allowed: Sequence[str] = OPERATIONS) -> dict:
    """Search, then promote on unseen cases, until a generation yields nothing. ``known`` gains the promoted."""
    chain, attempts, programs = [champion], [], {}
    everything = list(searching) + list(selection)
    for generation in range(1, generations + 1):
        reach = diagnosis(champion, known, truth, searching)
        scorer = Scorer(known, truth, searching)
        base = scorer.outcome(member(champion))[0]
        found = search(champion, scorer, seed=seed + generation, rounds=rounds, population=population, kept=kept,
                       allowed=allowed)
        attempt = {"generation": generation, "parent": champion, "archive_size": len(known), "reach": reach,
                   "parent_localized": base, "programs_scored": found["programs_scored"]}
        if found["localized"] <= base:
            attempts.append({**attempt, "outcome": "no program better on search cases"})
            break
        program = found["program"]
        name = named(program)
        locations = answers_of(program, known, everything)
        comparison = compare(scored(locations, truth, selection), scored(known[champion], truth, selection))
        promoted = promotes(comparison, margin, alpha)
        attempts.append({**attempt, "name": name, "program": program, "size": size(program),
                         "search_localized": found["localized"],
                         "selection": {key: comparison[key] for key in
                                       ("parent", "child", "gained", "lost", "one_sided_sign_test")},
                         "outcome": "promoted" if promoted else "rejected on unseen cases"})
        if not promoted:
            break
        programs[name] = program
        known[name] = locations
        champion = name
        chain.append(name)
    return {"chain": chain, "attempts": attempts, "programs": programs}

