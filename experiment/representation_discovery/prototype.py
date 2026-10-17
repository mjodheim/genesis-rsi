"""Development study: evolve an invertible representation of Boolean truth tables.

Allowed representation is a subset of reversible GF(2) butterfly passes.
This is NOT unrestricted grammar invention, blind evaluation, or RSI.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import random

from genesis import circuit_tasks as tasks

FAMILIES_TRAIN = tuple(tasks.LEARN)
FAMILIES_EVAL = tuple(tasks.HELD_OUT)
MAX_INPUTS = 6
BEAM = 4


def representation(table: int, inputs: int, mask: int) -> int:
    """Apply commuting, individually-involutive XOR butterfly passes."""
    if not (1 <= inputs <= MAX_INPUTS) or mask < 0 or mask >= (1 << inputs):
        raise ValueError("invalid representation parameters")
    count = 1 << inputs
    if table < 0 or table >= (1 << count):
        raise ValueError("invalid truth-table value")
    coeff = [(table >> row) & 1 for row in range(count)]
    for axis in range(inputs):
        if (mask >> axis) & 1:
            for row in range(count):
                if row & (1 << axis):
                    coeff[row] ^= coeff[row ^ (1 << axis)]
    return sum(value << index for index, value in enumerate(coeff))


def encode(table: int, inputs: int) -> str:
    """Real finite bitstring codec, with packed (0) or sparse-index (1) payload."""
    if not 1 <= inputs <= MAX_INPUTS or not 0 <= table < (1 << (1 << inputs)):
        raise ValueError("invalid codec parameters")
    length = 1 << inputs
    indexes = [i for i in range(length) if (table >> i) & 1]
    dense = "0" + format(table, f"0{length}b")
    sparse = ("1" + format(len(indexes), f"0{inputs + 1}b")
              + "".join(format(index, f"0{inputs}b") for index in indexes))
    return min((dense, sparse), key=len)


def decode(payload: str, inputs: int) -> int:
    """Decode complete bitstring; reject truncated, duplicate or trailing data."""
    if not 1 <= inputs <= MAX_INPUTS or not isinstance(payload, str):
        raise ValueError("invalid codec parameters")
    if not payload or any(c not in "01" for c in payload):
        raise ValueError("non-binary payload")
    if payload[0] == "0":
        if len(payload) != 1 + (1 << inputs):
            raise ValueError("incorrect dense payload size")
        return int(payload[1:], 2)
    count_end = 1 + inputs + 1
    if len(payload) < count_end:
        raise ValueError("truncated sparse header")
    count = int(payload[1:count_end], 2)
    if count > (1 << inputs) or len(payload) != count_end + inputs * count:
        raise ValueError("incorrect sparse payload size")
    output, previous = 0, -1
    for i in range(count):
        start = count_end + i * inputs
        pos = int(payload[start:start + inputs], 2)
        if pos <= previous:
            raise ValueError("noncanonical duplicate or unordered sparse index")
        output |= 1 << pos
        previous = pos
    return output


def encoding_bits(table: int, inputs: int) -> int:
    """Measured actual bit length of the reversible codec."""
    return len(encode(table, inputs))


def tasks_for(families: tuple[str, ...], inputs: int) -> tuple:
    return tuple(t for family in families for t in tasks.tasks(family) if t.inputs == inputs)


def score(training: tuple, inputs: int, mask: int) -> int:
    """Training-only objective; one-time descriptor counts against change."""
    overhead = inputs if mask != 0 else 0
    return overhead + sum(encoding_bits(representation(t.target, inputs, mask), inputs) for t in training)


@dataclass(frozen=True)
class Candidate:
    mask: int
    parent: int | None
    generation: int
    training_bits: int


def evolve(training: tuple, inputs: int, *, budget: int | None = None) -> tuple[Candidate, dict[int, Candidate]]:
    """Beam mutations of the representation program, accounting for distinct trials."""
    if budget is None:
        budget = 1 << inputs
    if budget < 1:
        raise ValueError("budget must be positive")
    seed = Candidate(mask=0, parent=None, generation=0, training_bits=score(training, inputs, 0))
    pool: dict[int, Candidate] = {0: seed}
    beam = [seed]
    for gen in range(1, inputs + 2):
        if len(pool) >= budget:
            break
        offspring: list[Candidate] = []
        for parent in beam:
            for axis in range(inputs):
                mask = parent.mask ^ (1 << axis)
                if mask in pool or len(pool) >= budget:
                    continue
                child = Candidate(mask, parent.mask, gen, score(training, inputs, mask))
                pool[mask] = child
                offspring.append(child)
        if not offspring:
            break
        beam = sorted(
            [*beam, *offspring],
            key=lambda c: (c.training_bits, c.mask.bit_count(), c.mask),
        )[:BEAM]
    winning = min(pool.values(), key=lambda c: (c.training_bits, c.mask.bit_count(), c.mask))
    return winning, pool


def digest_tasks(seq: tuple) -> str:
    obj = [[t.name, t.family, t.inputs, t.target] for t in seq]
    return sha256(json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()).hexdigest()


def trial() -> dict:
    """Deterministic DEVELOPMENT-only trial, no hidden holdout or self-promotion."""
    rows = []
    for n in range(2, MAX_INPUTS + 1):
        train = tasks_for(FAMILIES_TRAIN, n)
        evaluation = tasks_for(FAMILIES_EVAL, n)
        selected, candidates = evolve(train, n)
        path = [selected.mask]
        parent = selected.parent
        while parent is not None:
            path.append(parent)
            parent = candidates[parent].parent
        path.reverse()
        for t in [*train, *evaluation]:
            transformed = representation(t.target, n, selected.mask)
            payload = encode(transformed, n)
            if representation(decode(payload, n), n, selected.mask) != t.target:
                raise AssertionError("non-reproducible representation/codec")
        rng = random.Random(f"repr-controls|{n}")
        random_masks = rng.sample(range(1 << n), len(candidates))
        random_win = min(random_masks, key=lambda m: (score(train, n, m), m.bit_count(), m))
        def bits(dataset, mask):
            return sum(encoding_bits(representation(t.target, n, mask), n) for t in dataset)
        rows.append({
            "inputs": n,
            "train_count": len(train),
            "evaluation_count": len(evaluation),
            "candidate_evaluations": len(candidates),
            "winner_mask": selected.mask,
            "winner_lineage_masks": path,
            "training_identity_bits": bits(train, 0),
            "training_evolved_bits_including_descriptor": selected.training_bits,
            "training_random_bits_including_descriptor": score(train, n, random_win),
            "evaluation_identity_bits": bits(evaluation, 0),
            "evaluation_evolved_bits": bits(evaluation, selected.mask),
            "evaluation_full_mobius_bits": bits(evaluation, (1 << n) - 1),
            "evaluation_random_bits": bits(evaluation, random_win),
            "work_units": sum(len(train) * m.bit_count() * (1 << (n - 1)) for m in candidates),
        })
    return {
        "status": "DEVELOPMENT_ONLY_NOT_BLIND",
        "schema": "genesis-representation-prototype-v1",
        "training_families": FAMILIES_TRAIN,
        "evaluation_families": FAMILIES_EVAL,
        "train_digest": digest_tasks(tuple(t for n in range(2, MAX_INPUTS+1) for t in tasks_for(FAMILIES_TRAIN, n))),
        "evaluation_digest": digest_tasks(tuple(t for n in range(2, MAX_INPUTS+1) for t in tasks_for(FAMILIES_EVAL, n))),
        "metric": "toy encoding bits and counted transform work; not CPU runtime or energy",
        "rows": rows,
    }


if __name__ == "__main__":
    print(json.dumps(trial(), indent=2))
