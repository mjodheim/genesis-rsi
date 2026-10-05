[Reading 48 lines from start (total: 48 lines, 0 remaining)]

"""Prospective V52 sustained abstraction-memory population.

Committed before any V52 prospective behavioral execution. This remains a finite,
project-authored population and therefore cannot by itself establish general L9.
"""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import bank as v31, programs

FRESH_SEEDS = (520051, 520052, 520053)
WINDOWS = 12
TASKS_PER_WINDOW = 12


def stream(seed):
    if seed not in FRESH_SEEDS:
        raise ValueError("Uncommitted V52 prospective seed")
    rng = random.Random(seed)
    tasks = []
    for window in range(WINDOWS):
        width = window + 3
        a, b = rng.sample(range(width), 2)
        rotation = rng.randrange(1, width)
        targets = [
            (0, 1 << a), (0, 1 << b), (0, (1 << a) | (1 << b)),
            (rotation, 0), (rotation, 1 << a), (rotation, 1 << b),
        ] * 2
        for index, (turn, mask) in enumerate(targets):
            inputs = sorted({
                0, (1 << width) - 1,
                *(1 << bit for bit in range(width)),
                *(rng.randrange(1 << width) for _ in range(8)),
            })
            tasks.append({
                "task_id": f"v52-s{seed}-w{window}-t{index}",
                "window": window,
                "family": "affine" if turn and mask else "rotation" if turn else "xor",
                "width": width,
                "inputs": inputs,
                "target": programs.validate({"width": width, "rotation": turn, "mask": mask}),
            })
    v31.validate_stream(tasks)
    return tasks


def population_sha256():
    return digest([stream(seed) for seed in FRESH_SEEDS])

[executed on device: Mjodheim-Ubuntu-cx33 (915d6eb6-54f1-400c-8c12-a1e043b0a356)]