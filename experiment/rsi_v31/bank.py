"""Predeclared project-authored streams, with every task retained."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import programs

DEV_SEEDS = (101, 211)
FRESH_SEEDS = (9143, 27189, 40733)
WINDOWS = 4
TASKS_PER_WINDOW = 12


def stream(seed):
    rng = random.Random(seed)
    result = []
    for window in range(WINDOWS):
        width = window + 3
        a, b = rng.sample(range(width), 2)
        rotation = rng.randrange(1, width)
        # Alternation revisits earlier branches. No outcome-based filtering.
        targets = [(0, 1 << a), (0, 1 << b), (0, (1 << a) | (1 << b)),
                   (rotation, 0), (rotation, 1 << a), (rotation, 1 << b)] * 2
        for index, (turn, mask) in enumerate(targets):
            family = "affine" if turn and mask else "rotation" if turn else "xor"
            inputs = sorted({0, (1 << width) - 1, *(1 << bit for bit in range(width)),
                             *(rng.randrange(1 << width) for _ in range(8))})
            result.append({"task_id": f"s{seed}-w{window}-t{index}", "window": window,
                           "family": family, "width": width, "inputs": inputs,
                           "target": programs.validate({"width": width, "rotation": turn, "mask": mask})})
    return result


def validate_task(task):
    if type(task) is not dict or set(task) != {"task_id", "window", "family", "width", "inputs", "target"}:
        raise ValueError("Invalid externally owned task record")
    programs.validate(task["target"])
    if (type(task["task_id"]) is not str or not task["task_id"] or len(task["task_id"]) > 128
            or type(task["window"]) is not int or task["window"] < 0
            or task["family"] not in ("xor", "rotation", "affine")
            or type(task["width"]) is not int
            or task["width"] != task["target"]["width"]
            or type(task["inputs"]) is not list or not 1 <= len(task["inputs"]) <= 128
            or len(set(task["inputs"])) != len(task["inputs"])
            or any(type(x) is not int or not 0 <= x < 1 << task["width"] for x in task["inputs"])):
        raise ValueError("Invalid external task dimensions or probes")
    return True


def validate_stream(tasks):
    if not tasks or len({row["task_id"] for row in tasks}) != len(tasks):
        raise ValueError("Empty or duplicate stream")
    for row in tasks:
        validate_task(row)
    if [row["window"] for row in tasks] != sorted(row["window"] for row in tasks):
        raise ValueError("Task windows were reordered")
    return digest(tasks)
