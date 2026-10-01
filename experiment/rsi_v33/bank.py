"""Predeclared larger finite assay. It cannot establish open-ended L9."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import bank as previous, programs

FRESH_SEEDS = (203999, 287107, 361373)
WINDOWS = 8
TASKS_PER_WINDOW = 12


def stream(seed):
    rng, tasks = random.Random(seed), []
    for window in range(WINDOWS):
        width = window + 3
        a, b = rng.sample(range(width), 2)
        rotation = rng.randrange(1, width)
        targets = [(0, 1 << a), (0, 1 << b), (0, (1 << a) | (1 << b)),
                   (rotation, 0), (rotation, 1 << a), (rotation, 1 << b)] * 2
        for index, (turn, mask) in enumerate(targets):
            inputs = sorted({0, (1 << width) - 1, *(1 << bit for bit in range(width)),
                             *(rng.randrange(1 << width) for _ in range(8))})
            tasks.append({"task_id": f"v33-s{seed}-w{window}-t{index}", "window": window,
                          "family": "affine" if turn and mask else "rotation" if turn else "xor",
                          "width": width, "inputs": inputs,
                          "target": programs.validate({"width": width, "rotation": turn, "mask": mask})})
    previous.validate_stream(tasks)
    return tasks


def population_sha256():
    return digest([stream(seed) for seed in FRESH_SEEDS])
