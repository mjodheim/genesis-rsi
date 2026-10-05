"""Target-blind diagnostic constructor learned from the V36 failure mode.

The policy sees only acquired successful motifs and scalar matched-slot feedback.
It never inspects task targets, expected outputs, task IDs or fresh seed identities.
"""
from __future__ import annotations

import itertools
import random

import numpy as np

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank, engine as v36

MAX_EVALUATIONS = 14
MOTIFS = 4
BLOCK = bank.BLOCK


def _evaluate(task, ops, calls, kind, *, isolated):
    genome = native.genome(task["domain"], ops)
    receipt = native.evaluate(task, genome, isolated=isolated)
    calls.append({
        "kind": kind,
        "genome": genome,
        "evaluation": receipt,
    })
    return receipt["matched_slots"]


def _solved_entry(task, position, ops, calls, construction):
    genome = native.genome(task["domain"], ops)
    descriptor = native.descriptor(genome)
    return {
        "task_sha256": digest(task),
        "global_position": position,
        "epoch": task["epoch"],
        "domain": task["domain"],
        "slots": task["slots"],
        "calls": calls,
        "programs": [{
            "genome": genome,
            "source_sha256": descriptor["source_sha256"],
            "semantic_sha256": descriptor["semantic_sha256"],
            "parent_source_sha256": None,
            "search_parent_source_sha256": None,
            "evaluation": calls[-1]["evaluation"],
            "previously_observed": False,
            "construction": construction,
            "donor_source_sha256": None,
        }],
        "charged_evaluations": len(calls),
        "solved": calls[-1]["evaluation"]["matched_slots"] == task["slots"],
    }


def acquired_motifs(history, domain):
    found = {}
    for entry in history.values():
        genome = entry["genome"]
        if (
            entry["successes"]
            and genome["domain"] == domain
            and len(genome["ops"]) == BLOCK
            and all(genome["ops"])
        ):
            key = tuple(genome["ops"])
            found.setdefault(key, list(key))
    return tuple(found[key] for key in sorted(found))


def acquire(task, position, *, isolated=False):
    """Acquire a one-to-three-slot native body by scalar coordinate diagnosis."""
    slots = task["slots"]
    if not 1 <= slots <= BLOCK:
        raise ValueError("Acquisition is restricted to the first three slots")

    current = [0] * slots
    calls = []
    score = _evaluate(task, current, calls, "root", isolated=isolated)

    for slot in range(slots):
        selected = False
        for operator in (1, 2, 3):
            probe = list(current)
            probe[slot] = operator
            observed = _evaluate(
                task, probe, calls, "acquisition-probe", isolated=isolated
            )
            if observed == score + 1:
                current = probe
                score = observed
                selected = True
                break
        if not selected:
            # The externally frozen native alphabet is {1,2,3,4}. If three
            # alternatives fail to improve this untouched slot, the fourth is
            # determined without a paid query.
            current[slot] = 4
            score += 1

    _evaluate(task, current, calls, "verify", isolated=isolated)
    if len(calls) > MAX_EVALUATIONS:
        raise ValueError("Acquisition escaped the fourteen-call cap")
    return _solved_entry(
        task,
        position,
        current,
        calls,
        {"kind": "scalar-coordinate-acquisition"},
    )


def _match_matrix(motifs):
    return np.array([
        [sum(a == b for a, b in zip(query, target)) for target in motifs]
        for query in motifs
    ], dtype=np.int8)


def _hypotheses(blocks):
    rows = 4 ** blocks
    values = np.empty((rows, blocks), dtype=np.int8)
    for index, hypothesis in enumerate(
        itertools.product(range(MOTIFS), repeat=blocks)
    ):
        values[index] = hypothesis
    return values


def _response_vector(hypotheses, query, matrix):
    values = np.zeros(len(hypotheses), dtype=np.int16)
    for block_index, motif_index in enumerate(query):
        values += matrix[motif_index, hypotheses[:, block_index]]
    return values


def _candidate_queries(hypotheses, blocks, step):
    queries = []
    if len(hypotheses):
        picks = np.linspace(
            0, len(hypotheses) - 1, min(24, len(hypotheses)), dtype=int
        )
        queries.extend(
            tuple(int(value) for value in hypotheses[index])
            for index in picks
        )
    queries.extend(tuple([motif] * blocks) for motif in range(MOTIFS))

    # Fixed deterministic pseudo-random exploration. No task identity, seed,
    # target or expected output participates in this proposal stream.
    rng = random.Random(digest([
        "l9-oe1-diagnostic-query-v1",
        blocks,
        step,
        len(hypotheses),
    ]))
    for _ in range(72):
        queries.append(tuple(rng.randrange(MOTIFS) for _ in range(blocks)))

    seen = set()
    unique = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def _choose_query(hypotheses, matrix, blocks, step):
    best = None
    for query in _candidate_queries(hypotheses, blocks, step):
        responses = _response_vector(hypotheses, query, matrix)
        counts = np.bincount(responses)
        max_bucket = int(counts.max())
        squared_mass = int(
            np.dot(counts.astype(np.int64), counts.astype(np.int64))
        )
        key = (max_bucket, squared_mass, query)
        if best is None or key < best[0]:
            best = (key, query)
    return best[1]


def _ops(query, motifs):
    values = []
    for motif_index in query:
        values.extend(motifs[motif_index])
    return values


def diagnose(task, position, history, *, isolated=False):
    """Identify a composition of four acquired motifs from scalar feedback."""
    motifs = acquired_motifs(history, task["domain"])
    if len(motifs) != MOTIFS:
        raise ValueError(
            f"Diagnostic construction requires four acquired motifs, got {len(motifs)}"
        )
    if task["slots"] % BLOCK:
        raise ValueError("Diagnostic construction requires whole motif blocks")

    blocks = task["slots"] // BLOCK
    hypotheses = _hypotheses(blocks)
    matrix = _match_matrix(motifs)
    calls = []
    tested = set()
    step = 0
    solution_ops = None

    while len(hypotheses) > 1 and len(calls) < MAX_EVALUATIONS - 1:
        query = _choose_query(hypotheses, matrix, blocks, step)
        if query in tested:
            break
        tested.add(query)

        ops = _ops(query, motifs)
        observed = _evaluate(
            task, ops, calls, "diagnostic-probe", isolated=isolated
        )
        if observed == task["slots"]:
            solution_ops = ops
            break

        responses = _response_vector(hypotheses, query, matrix)
        hypotheses = hypotheses[responses == observed]
        step += 1

    if solution_ops is None and len(hypotheses):
        # Once the scalar transcript isolates one remaining composition, execute
        # it normally before confirmation. No hidden answer is read here.
        query = tuple(int(value) for value in hypotheses[0])
        if query not in tested and len(calls) < MAX_EVALUATIONS - 1:
            ops = _ops(query, motifs)
            observed = _evaluate(
                task, ops, calls, "posterior-candidate", isolated=isolated
            )
            if observed == task["slots"]:
                solution_ops = ops

    if solution_ops is None:
        raise RuntimeError(
            f"Diagnostic posterior unresolved within budget: {len(hypotheses)}"
        )

    _evaluate(task, solution_ops, calls, "verify", isolated=isolated)
    if len(calls) > MAX_EVALUATIONS:
        raise ValueError("Diagnostic construction escaped the fourteen-call cap")

    return _solved_entry(
        task,
        position,
        solution_ops,
        calls,
        {
            "kind": "scalar-hypothesis-construction",
            "motifs": [list(value) for value in motifs],
            "diagnostic_steps": step,
            "remaining_hypotheses": len(hypotheses),
        },
    )


def episode(task, position, history, *, isolated=False):
    if task["slots"] <= BLOCK:
        row = acquire(task, position, isolated=isolated)
    else:
        row = diagnose(task, position, history, isolated=isolated)

    old_solved = {
        entry["semantic_sha256"]
        for entry in history.values()
        if entry["successes"]
    }
    program = row["programs"][0]
    old_entry = history.get(program["source_sha256"])
    program["previously_observed"] = old_entry is not None
    rediscovered = (
        [program["semantic_sha256"]]
        if (
            row["solved"]
            and old_entry is not None
            and old_entry["successes"]
            and old_entry["last_success_position"] < position - 1
        )
        else []
    )
    row.update({
        "search": {
            "best_quality_milli": program["evaluation"]["quality_milli"],
            "represented_requests": len(row["calls"]),
        },
        "selected_root_sha256": None,
        "screen_calls": 0,
        "learned_fragments": [
            {"ops": list(motif)} for motif in acquired_motifs(history, task["domain"])
        ],
        "policy_calls": len(row["calls"]),
        "archive_size_before": len(history),
        "new_first_solving_semantics": (
            [program["semantic_sha256"]]
            if row["solved"] and program["semantic_sha256"] not in old_solved
            else []
        ),
        "new_source_solves": (
            [program["source_sha256"]]
            if row["solved"] and program["source_sha256"] not in history
            else []
        ),
        "rediscovered": rediscovered,
    })
    return row


def verify_episode(task, position, history, row, *, isolated=False):
    if row["task_sha256"] != digest(task) or row["global_position"] != position:
        raise ValueError("Substituted task or position")
    for call in row["calls"]:
        expected = native.evaluate(task, call["genome"], isolated=isolated)
        if expected != call["evaluation"]:
            raise ValueError("Altered native evaluator receipt")
    rebuilt = episode(task, position, history, isolated=isolated)
    if digest(rebuilt) != digest(row):
        raise ValueError("Altered diagnostic policy or accounting")
    return True


def summary(rows, history_before=None):
    previous = {} if history_before is None else history_before
    full = v36.history_from(rows, previous)
    solved = [entry for entry in full.values() if entry["successes"]]
    cost = sum(row["charged_evaluations"] for row in rows)
    new = sum(len(row["new_first_solving_semantics"]) for row in rows)
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "evaluations": cost,
        "first_solving_semantics": new,
        "discovery_per_1000_evaluations": new * 1000 // cost if cost else 0,
        "archive_size": len(full),
        "solved_semantic_size": len({
            entry["semantic_sha256"] for entry in solved
        }),
        "new_source_solves": sum(len(row["new_source_solves"]) for row in rows),
        "branches": len({
            entry["genome"]["ops"][0]
            for entry in solved
            if entry["genome"]["ops"]
        }),
        "rediscoveries": sum(len(row["rediscovered"]) for row in rows),
        "max_solved_length": max(
            (len(entry["genome"]["ops"]) for entry in solved),
            default=0,
        ),
    }
