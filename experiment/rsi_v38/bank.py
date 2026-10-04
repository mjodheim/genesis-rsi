"""Prospective recursively composed native targets; no behavior-based sampling."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36.bank import validate_task as base_validate, validate_stream as base_stream

DEV_SEEDS = (503, 809)
FRESH_SEEDS = (4000037, 7000003)
EPOCHS = 9
TASKS_PER_EPOCH = 8


def validate_task(task):
    base_validate(task)
    if task["slots"] != 1 << task["epoch"]:
        raise ValueError("Invalid recursive interface length")
    return True


def validate_stream(tasks):
    for task in tasks:
        validate_task(task)
    return base_stream(tasks)


def stream(seed, domain, *, epochs=EPOCHS, tasks_per_epoch=TASKS_PER_EPOCH):
    if (type(epochs) is not int or epochs < 1 or type(tasks_per_epoch) is not int
            or tasks_per_epoch < 4 or tasks_per_epoch % 4):
        raise ValueError("Invalid prospective recursive schedule")
    rng = random.Random(digest(["v38-targets", seed, domain]))
    targets, tasks = [[operator] for operator in range(1, 5)], []
    for epoch in range(epochs):
        if epoch:
            previous, targets = targets, []
            while len(targets) < 4:
                target = previous[rng.randrange(4)] + previous[rng.randrange(4)]
                if target not in targets:
                    targets.append(target)
        order = list(range(4)) * (tasks_per_epoch // 4)
        rng.shuffle(order)
        for index, branch in enumerate(order):
            target = targets[branch]
            task = {"task_id": f"v38-{seed}-{domain}-e{epoch}-t{index}", "epoch": epoch,
                "domain": domain, "slots": len(target), "target": list(target),
                "inputs": native.contexts(seed, domain, epoch, index)}
            validate_task(task)
            tasks.append(task)
    return tasks
