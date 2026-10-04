"""Prospective non-prefix native recombination; no behavior-based selection."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native

DEV_SEEDS = (71, 113)
FRESH_SEEDS = (940127, 1490233, 2718281)
BLOCK = 3
EPOCHS = 10
TASKS_PER_EPOCH = 16


def stream(seed, domain, *, epochs=EPOCHS, tasks_per_epoch=TASKS_PER_EPOCH):
    if (type(epochs) is not int or epochs < 1 or type(tasks_per_epoch) is not int
            or tasks_per_epoch < 4 or tasks_per_epoch % 4):
        raise ValueError("Invalid prospective epoch schedule")
    rng = random.Random(digest(["v36-targets", seed, domain]))
    motifs = [[first, rng.randrange(1, 5), rng.randrange(1, 5)] for first in range(1, 5)]
    tasks = []
    for epoch in range(epochs):
        if epoch < BLOCK:
            targets = [motif[:epoch + 1] for motif in motifs]
        else:
            blocks = epoch - BLOCK + 2
            targets = []
            while len(targets) < 4:
                target = sum((motifs[rng.randrange(4)] for _ in range(blocks)), [])
                if target not in targets:
                    targets.append(target)
        order = list(range(4)) * (tasks_per_epoch // 4)
        rng.shuffle(order)
        for index, branch in enumerate(order):
            target = targets[branch]
            task = {"task_id": f"v36-{seed}-{domain}-e{epoch}-t{index}", "epoch": epoch,
                    "domain": domain, "slots": len(target), "target": list(target),
                    "inputs": native.contexts(seed, domain, epoch, index)}
            validate_task(task)
            tasks.append(task)
    return tasks


def validate_task(task):
    if type(task) is not dict or set(task) != {"task_id", "epoch", "domain", "slots", "target", "inputs"}:
        raise ValueError("Invalid externally owned task")
    if (type(task["task_id"]) is not str or not task["task_id"] or task["domain"] not in native.DOMAINS
            or type(task["epoch"]) is not int or task["epoch"] < 0
            or type(task["slots"]) is not int or task["slots"] < 1
            or type(task["target"]) is not list or len(task["target"]) != task["slots"]
            or any(type(op) is not int or not 1 <= op <= 4 for op in task["target"])
            or type(task["inputs"]) is not list or len(task["inputs"]) != 4):
        raise ValueError("Invalid native task dimensions")
    for case in task["inputs"]:
        if set(case) != {"data", "answers"} or len(case["answers"]) != 5 or len({digest(v) for v in case["answers"]}) != 5:
            raise ValueError("Reference witness omitted or aliased")
    return True


def validate_stream(tasks):
    if not tasks or len({t["task_id"] for t in tasks}) != len(tasks):
        raise ValueError("Empty or duplicate stream")
    for task in tasks:
        validate_task(task)
    if len({t["domain"] for t in tasks}) != 1 or [t["epoch"] for t in tasks] != sorted(t["epoch"] for t in tasks):
        raise ValueError("Reordered or mixed native epochs")
    return digest(tasks)
