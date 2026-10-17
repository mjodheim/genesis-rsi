"""Read-only CIRCUIT2 development audit: cross-seed repeats and NPN equivalence.

A distinct truth table is not a distinct NPN class, and different RNG seeds
do not create independent experimental units merely by changing encodings.
This file intentionally neither freezes/reveals an evaluation bank nor
assigns a success verdict to any scientific milestone.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from itertools import combinations, permutations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import circuit_tasks as tasks


@lru_cache(maxsize=4096)
def npn_class(inputs: int, target: int) -> tuple[int, int]:
    """Exhaustive NPN canonicalization, intentionally bounded to at most 3 inputs."""
    if not 1 <= inputs <= 3 or not 0 <= target < (1 << (1 << inputs)):
        raise ValueError("unsupported NPN class query")
    return (inputs, min(tasks._transform(inputs, target, order, negate, mask)
                        for order in permutations(range(inputs))
                        for negate in (False, True)
                        for mask in range(1 << inputs)))


def digest(sequence: list) -> str:
    rows = [[t.name, t.family, t.inputs, t.target] for t in sequence]
    return hashlib.sha256(json.dumps(rows).encode("utf-8")).hexdigest()


def _group(families: tuple[str, ...], seeds: tuple[int, ...]) -> tuple[list[list], dict]:
    sequences = [
        [task for task in tasks.circuit2_suite(families, seed) if task.inputs <= 3]
        for seed in seeds
    ]
    exact = [{(t.inputs, t.target) for t in seq} for seq in sequences]
    npn = [{npn_class(t.inputs, t.target) for t in seq} for seq in sequences]
    counts = Counter(item for group in exact for item in group)
    overlap = [len(a & b) for a, b in combinations(exact, 2)]
    return sequences, {
        "tasks_per_seed": [len(group) for group in exact],
        "total_task_slots": sum(map(len, exact)),
        "distinct_exact_tables": len(counts),
        "distinct_npn_classes": len(set().union(*npn)),
        "most_reused_exact_table_seed_count": max(counts.values(), default=0),
        "repeat_slots": sum(map(len, exact)) - len(counts),
        "pairwise_exact_overlap_sum": sum(overlap),
        "pairwise_exact_overlap_pairs": len(overlap),
        "pairwise_exact_overlap_max": max(overlap, default=0),
        "suite_digests": [digest(seq) for seq in sequences],
        "distinct_full_suite_digests": len(set(digest(seq) for seq in sequences)),
    }


def audit(seeds: tuple[int, ...] = tuple(range(20))) -> dict:
    if len(seeds) < 2 or len(seeds) != len(set(seeds)):
        raise ValueError("at least two different seeds required")
    train, train_stats = _group(tasks.LEARN, seeds)
    evaluation, evaluation_stats = _group(tasks.HELD_OUT, seeds)
    train_classes = {npn_class(t.inputs, t.target) for row in train for t in row}
    eval_classes = {npn_class(t.inputs, t.target) for row in evaluation for t in row}
    exact_collision = [
        seed for seed, learn, heldout in zip(seeds, train, evaluation)
        if {(t.inputs, t.target) for t in learn}
        & {(t.inputs, t.target) for t in heldout}
    ]
    shared = sorted(train_classes & eval_classes)
    return {
        "schema": "genesis-circuit2-seed-diversity-development-v1",
        "status": "DESCRIPTIVE_DEVELOPMENT_AUDIT_NOT_BLIND_OR_PROSPECTIVE",
        "seeds": list(seeds),
        "max_inputs": 3,
        "train": train_stats,
        "evaluation": evaluation_stats,
        "within_seed_exact_collisions": exact_collision,
        "shared_train_eval_npn_classes": [list(key) for key in shared],
        "shared_npn_count": len(shared),
        "npn_train_classes": len(train_classes),
        "npn_eval_classes": len(eval_classes),
        "npn_independent_holdout": len(shared) == 0,
        "seed_independence_established": False,
        "scientific_boundary": (
            "Seeds share truth-table and NPN-equivalence support. Distinct RNG outputs "
            "do not establish independent hypothesis trials or out-of-class transfer."
        ),
    }


def require_npn_isolation(report: dict) -> None:
    """Prospective guard; cannot repair historical or already-frozen outcomes."""
    if report["within_seed_exact_collisions"]:
        raise ValueError("LEARN and HELD_OUT overlap by exact table")
    if report["shared_npn_count"]:
        raise ValueError("LEARN and HELD_OUT reuse NPN-equivalent problem classes")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--require-npn-isolation", action="store_true",
                        help="strict prospective check (failure expected for current design)")
    args = parser.parse_args()
    report = audit()
    print(json.dumps(report, indent=2))
    if args.require_npn_isolation:
        try:
            require_npn_isolation(report)
        except ValueError as exc:
            print(f"FAIL prospective NPN isolation: {exc}", file=__import__("sys").stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
