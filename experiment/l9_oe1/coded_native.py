"""Target-blind coded native constructor for OE1."""
from __future__ import annotations

import itertools
import random
import numpy as np

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native

BLOCK = 3
MAX_CALLS = 14
MAX_CODE_PROBES = 12


def _evaluate(task, ops, calls, *, isolated, kind):
    genome = native.genome(task["domain"], ops)
    evaluation = native.evaluate(task, genome, isolated=isolated)
    calls.append({"kind": kind, "genome": genome, "evaluation": evaluation})
    return evaluation


def acquire(task, *, isolated=False):
    current = [0] * task["slots"]
    calls = []
    score = _evaluate(task, current, calls, isolated=isolated, kind="root")["matched_slots"]

    for slot in range(task["slots"]):
        found = False
        for operator in (1, 2, 3):
            probe = list(current)
            probe[slot] = operator
            evaluation = _evaluate(
                task, probe, calls, isolated=isolated, kind="slot-probe"
            )
            if evaluation["matched_slots"] == score + 1:
                current = probe
                score += 1
                found = True
                break
        if not found:
            current[slot] = 4
            score += 1

    verification = _evaluate(
        task, current, calls, isolated=isolated, kind="verify"
    )
    if len(calls) > MAX_CALLS:
        raise ValueError("Coded acquisition escaped fourteen-call cap")
    return {
        "solved": verification["matched_slots"] == task["slots"],
        "genome": native.genome(task["domain"], current),
        "calls": calls,
    }


def _similarity(motifs):
    return np.asarray([
        [sum(a == b for a, b in zip(left, right)) for right in motifs]
        for left in motifs
    ], dtype=np.int16)


def _responses(query, hypotheses, similarity):
    query = np.asarray(query, dtype=np.int16)
    return similarity[query[None, :], hypotheses].sum(axis=1).astype(np.int64)

def design_code(motifs, blocks, *, attempts=64, max_probes=MAX_CODE_PROBES):
    if len(motifs) != 4 or blocks < 2:
        raise ValueError("Coded transfer requires four motifs and at least two blocks")

    similarity = _similarity(motifs)
    hypotheses = np.asarray(
        list(itertools.product(range(4), repeat=blocks)),
        dtype=np.int16,
    )
    base = 3 * blocks + 1
    count = len(hypotheses)

    for attempt in range(attempts):
        rng = random.Random(digest(["oe1-coded-native", motifs, blocks, attempt]))
        signature = np.zeros(count, dtype=np.int64)
        queries = []

        for _ in range(max_probes):
            query = tuple(rng.randrange(4) for _ in range(blocks))
            queries.append(query)
            signature = signature * base + _responses(query, hypotheses, similarity)

            if np.unique(signature).size == count:
                lookup = {}
                for code, hypothesis in zip(
                    signature.tolist(), hypotheses.tolist()
                ):
                    lookup[int(code)] = tuple(map(int, hypothesis))
                return {
                    "queries": tuple(queries),
                    "lookup": lookup,
                    "base": base,
                    "blocks": blocks,
                    "hypotheses": count,
                    "code_sha256": digest([motifs, blocks, queries]),
                }
    return None


def solve(task, motifs, code, *, isolated=False):
    calls = []
    _evaluate(task, [0] * task["slots"], calls, isolated=isolated, kind="root")
    signature = 0

    for query in code["queries"]:
        ops = sum((motifs[index] for index in query), [])
        observed = _evaluate(
            task, ops, calls, isolated=isolated, kind="coded-probe"
        )["matched_slots"]

        if observed == task["slots"]:
            verification = _evaluate(
                task, ops, calls, isolated=isolated, kind="verify"
            )
            return {
                "solved": verification["matched_slots"] == task["slots"],
                "genome": native.genome(task["domain"], ops),
                "calls": calls,
                "code_sha256": code["code_sha256"],
            }

        signature = signature * code["base"] + observed

    hypothesis = code["lookup"].get(int(signature))
    if hypothesis is None:
        return {
            "solved": False,
            "genome": None,
            "calls": calls,
            "code_sha256": code["code_sha256"],
        }

    final = sum((motifs[index] for index in hypothesis), [])
    verification = _evaluate(
        task, final, calls, isolated=isolated, kind="verify"
    )

    if len(calls) > MAX_CALLS:
        raise ValueError("Coded transfer escaped fourteen-call cap")

    return {
        "solved": verification["matched_slots"] == task["slots"],
        "genome": native.genome(task["domain"], final),
        "calls": calls,
        "code_sha256": code["code_sha256"],
    }


def motif_library(programs, domain):
    found = {}
    for program in programs:
        genome = program["genome"]
        if genome["domain"] != domain:
            continue
        ops = genome["ops"]
        if len(ops) == BLOCK and all(ops):
            found.setdefault(tuple(ops), list(ops))
    return [found[key] for key in sorted(found)]


def code_manifest(motifs, max_blocks):
    rows = {}
    for blocks in range(2, max_blocks + 1):
        code = design_code(motifs, blocks)
        if code is None:
            rows[str(blocks)] = None
        else:
            rows[str(blocks)] = {
                "probes": len(code["queries"]),
                "hypotheses": code["hypotheses"],
                "code_sha256": code["code_sha256"],
            }
    return rows
