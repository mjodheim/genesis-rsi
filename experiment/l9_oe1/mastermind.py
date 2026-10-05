"""Target-blind information-gain solver for V36 native tasks.

The solver never reads task["target"]. It uses only:
- public task dimensions/domain,
- previously solved bodies,
- fully charged native evaluations returning matched_slots.

Epochs 0-2 acquire the four motif prefixes over the public native alphabet.
Later epochs treat learned 3-slot motifs as symbols and solve the composition as
a Mastermind-style hypothesis elimination problem.
"""
from __future__ import annotations

import itertools
import math
import random

import numpy as np

from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank

MAX_CALLS = 14
VERIFY_RESERVE = 1
PROBE_SAMPLE = 40
ALPHABET = (1, 2, 3, 4)


class State:
    def __init__(self, retention="archive"):
        if retention not in ("archive", "greedy", "cold"):
            raise ValueError("Unknown OE1 retention arm")
        self.retention = retention
        self.motifs = []
        self.solutions_by_slots = {}

    def remember(self, slots, ops):
        key = tuple(ops)
        if slots == bank.BLOCK and all(ops) and key not in self.motifs:
            self.motifs.append(key)

        if self.retention == "cold":
            return

        self.solutions_by_slots.setdefault(slots, [])
        if self.retention == "greedy":
            self.solutions_by_slots[slots] = [key]
        elif key not in self.solutions_by_slots[slots]:
            self.solutions_by_slots[slots].append(key)

    def preferred(self, slots):
        return tuple(self.solutions_by_slots.get(slots, ()))

    def exact_branches(self):
        return sum(len(values) for values in self.solutions_by_slots.values())

    def snapshot(self):
        return {
            "retention": self.retention,
            "motifs": [list(value) for value in self.motifs],
            "solutions_by_slots": {
                str(slots): [list(value) for value in values]
                for slots, values in sorted(self.solutions_by_slots.items())
            },
        }

    @classmethod
    def restore(cls, value):
        state = cls(value["retention"])
        state.motifs = [tuple(row) for row in value["motifs"]]
        state.solutions_by_slots = {
            int(slots): [tuple(row) for row in values]
            for slots, values in value["solutions_by_slots"].items()
        }
        return state


def _hypotheses(symbol_count, units):
    return np.array(
        list(itertools.product(range(symbol_count), repeat=units)),
        dtype=np.int8,
    )


def _similarity(symbols):
    if isinstance(symbols[0], int):
        return np.eye(len(symbols), dtype=np.int16)
    matrix = np.zeros((len(symbols), len(symbols)), dtype=np.int16)
    for i, left in enumerate(symbols):
        for j, right in enumerate(symbols):
            matrix[i, j] = sum(a == b for a, b in zip(left, right))
    return matrix


def _ops(probe, symbols):
    if isinstance(symbols[0], int):
        return [symbols[index] for index in probe]
    result = []
    for index in probe:
        result.extend(symbols[index])
    return result


def _probe_for_ops(ops, symbols):
    if isinstance(symbols[0], int):
        lookup = {value: index for index, value in enumerate(symbols)}
        if any(value not in lookup for value in ops):
            return None
        return tuple(lookup[value] for value in ops)

    width = len(symbols[0])
    lookup = {tuple(value): index for index, value in enumerate(symbols)}
    chunks = [tuple(ops[i:i + width]) for i in range(0, len(ops), width)]
    if any(chunk not in lookup for chunk in chunks):
        return None
    return tuple(lookup[chunk] for chunk in chunks)


def _responses(hypotheses, probe, similarity):
    values = np.zeros(len(hypotheses), dtype=np.int16)
    for position in range(hypotheses.shape[1]):
        values += similarity[hypotheses[:, position], probe[position]]
    return values


def _entropy(counts):
    total = counts.sum()
    if not total:
        return -1.0
    probabilities = counts[counts > 0] / total
    return float(-(probabilities * np.log2(probabilities)).sum())


def _choose_probe(hypotheses, similarity, rng, tried, preferred=()):
    live = {tuple(int(x) for x in row) for row in hypotheses}

    # Previously solved bodies are valuable probes because V36 repeats four branches
    # inside each epoch. They remain valid information-gain queries when not exact.
    for probe in preferred:
        if probe in live and probe not in tried:
            return probe

    count = len(hypotheses)
    indexes = list(range(count))
    if count > PROBE_SAMPLE:
        indexes = sorted(rng.sample(indexes, PROBE_SAMPLE))

    best_probe = None
    best_key = None
    for index in indexes:
        probe = tuple(int(x) for x in hypotheses[index])
        if probe in tried:
            continue
        responses = _responses(hypotheses, probe, similarity)
        counts = np.bincount(responses)
        # Entropy first, then minimax bucket size, then deterministic lexical tie-break.
        key = (
            _entropy(counts),
            -int(counts.max()),
            tuple(-value for value in probe),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_probe = probe

    if best_probe is not None:
        return best_probe

    for row in hypotheses:
        probe = tuple(int(x) for x in row)
        if probe not in tried:
            return probe
    return tuple(int(x) for x in hypotheses[0])


def _evaluate(task, ops, calls, kind):
    genome = native.genome(task["domain"], ops)
    evaluation = native.evaluate(task, genome, isolated=False)
    calls.append({
        "kind": kind,
        "genome": genome,
        "source_sha256": native.descriptor(genome)["source_sha256"],
        "evaluation": evaluation,
    })
    return evaluation


def solve(task, state, *, seed):
    if len(state.motifs) >= 4 and task["slots"] % bank.BLOCK == 0:
        symbols = [list(motif) for motif in state.motifs[:4]]
        units = task["slots"] // bank.BLOCK
        mode = "motif-mastermind"
    else:
        # Acquisition stages remain small: epochs 0-2 expose 1,2,3-slot prefixes.
        if task["slots"] > bank.BLOCK:
            return {
                "solved": False,
                "calls": [],
                "final_ops": None,
                "mode": "motifs-not-yet-acquired",
                "remaining_hypotheses": None,
            }
        symbols = list(ALPHABET)
        units = task["slots"]
        mode = "alphabet-mastermind"

    hypotheses = _hypotheses(len(symbols), units)
    similarity = _similarity(symbols)
    rng = random.Random(seed)
    tried = set()
    calls = []
    solved_ops = None

    preferred = []
    for old_ops in state.preferred(task["slots"]):
        probe = _probe_for_ops(old_ops, symbols)
        if probe is not None:
            preferred.append(probe)

    while len(calls) < MAX_CALLS - VERIFY_RESERVE and len(hypotheses):
        probe = _choose_probe(
            hypotheses,
            similarity,
            rng,
            tried,
            preferred=preferred,
        )
        tried.add(probe)
        ops = _ops(probe, symbols)
        evaluation = _evaluate(task, ops, calls, "probe")
        observed = evaluation["matched_slots"]

        if observed == task["slots"]:
            solved_ops = ops
            break

        responses = _responses(hypotheses, probe, similarity)
        hypotheses = hypotheses[responses == observed]

        if len(hypotheses) == 1:
            final_probe = tuple(int(x) for x in hypotheses[0])
            final_ops = _ops(final_probe, symbols)
            if final_probe == probe:
                solved_ops = final_ops
                break
            if len(calls) >= MAX_CALLS - VERIFY_RESERVE:
                break
            evaluation = _evaluate(task, final_ops, calls, "deduced")
            if evaluation["matched_slots"] == task["slots"]:
                solved_ops = final_ops
            break

    verified = False
    if solved_ops is not None and len(calls) < MAX_CALLS:
        verification = _evaluate(task, solved_ops, calls, "verify")
        verified = verification["matched_slots"] == task["slots"]

    if verified:
        state.remember(task["slots"], solved_ops)
        if task["slots"] == bank.BLOCK:
            state.remember(bank.BLOCK, solved_ops)

    return {
        "solved": verified,
        "calls": calls,
        "final_ops": solved_ops if verified else None,
        "mode": mode,
        "remaining_hypotheses": int(len(hypotheses)),
    }
