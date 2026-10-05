"""Prospective V51 development population.

These seeds and the eight-window growth schedule are committed in source before
the first V51 behavioral run. This remains project-authored development, not an
L9 qualification population.
"""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import bank as v31, programs

DEVELOPMENT_SEEDS = (510051, 510052, 510053)
WINDOWS = 8
TASKS_PER_WINDOW = 12


def stream(seed):
    if seed not in DEVELOPMENT_SEEDS:
        raise ValueError("Uncommitted V51 development seed")
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
                "task_id": f"v51-s{seed}-w{window}-t{index}",
                "window": window,
                "family": "affine" if turn and mask else "rotation" if turn else "xor",
                "width": width,
                "inputs": inputs,
                "target": programs.validate({"width": width, "rotation": turn, "mask": mask}),
            })
    v31.validate_stream(tasks)
    return tasks


def population_sha256():
    return digest([stream(seed) for seed in DEVELOPMENT_SEEDS])
