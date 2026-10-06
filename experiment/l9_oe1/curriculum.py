"""Competence-frontier curriculum generation for OE1."""
from __future__ import annotations

from collections import defaultdict
import random

from experiment.rsi_v31 import bank as v31, programs


def competence(rows):
    grouped = defaultdict(lambda: [0, 0])
    for row in rows:
        key = (row["family"], int(row["width"]))
        grouped[key][1] += 1
        grouped[key][0] += int(bool(row["solved"]))
    return {
        key: solved / total
        for key, (solved, total) in grouped.items()
        if total
    }


def frontier(rows, *, low=0.20, high=0.80):
    rates = competence(rows)
    selected = [
        (family, width, rate)
        for (family, width), rate in rates.items()
        if low <= rate <= high
    ]
    if selected:
        return sorted(selected, key=lambda row: (abs(0.5 - row[2]), row[1], row[0]))

    # If no task sits in the Goldilocks zone, advance just beyond the strongest
    # mastered width rather than sampling an arbitrary harder problem.
    mastered = [
        (family, width, rate)
        for (family, width), rate in rates.items()
        if rate > high
    ]
    if mastered:
        family, width, rate = max(mastered, key=lambda row: (row[1], row[2]))
        return [(family, width + 1, rate)]
    return [("affine", 3, 0.0)]


def _target_for(rng, family, width):
    if family == "xor":
        bits = rng.sample(range(width), k=min(2, width))
        return 0, sum(1 << bit for bit in bits)
    if family == "rotation":
        return rng.randrange(1, width), 0
    bits = rng.sample(range(width), k=min(2, width))
    return rng.randrange(1, width), sum(1 << bit for bit in bits)


def propose(rows, *, seed, count=12, low=0.20, high=0.80, max_width=32):
    """Generate tasks at the current competence frontier.

    The generator receives aggregate historical outcomes only; current target outputs
    never influence selection.
    """
    rng = random.Random(seed)
    zones = frontier(rows, low=low, high=high)
    tasks = []
    for index in range(count):
        family, width, _ = zones[index % len(zones)]
        width = max(3, min(max_width, width))
        rotation, mask = _target_for(rng, family, width)
        inputs = sorted({
            0,
            (1 << width) - 1,
            *(1 << bit for bit in range(width)),
            *(rng.randrange(1 << width) for _ in range(8)),
        })
        tasks.append({
            "task_id": f"oe1-{seed}-{index}",
            "window": index // max(1, len(zones)),
            "family": family,
            "width": width,
            "inputs": inputs,
            "target": programs.validate({
                "width": width,
                "rotation": rotation,
                "mask": mask,
            }),
        })
    v31.validate_stream(tasks)
    return tasks
