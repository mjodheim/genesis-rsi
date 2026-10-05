"""Prospective native append-extension curriculum; no behavior-based sampling."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native

DEV_SEEDS = (17, 43)
FRESH_SEEDS = (81173, 172913, 359837)
EPOCHS = 12
TASKS_PER_EPOCH = 32


def stream(seed, domain, *, epochs=EPOCHS, tasks_per_epoch=TASKS_PER_EPOCH):
    if type(epochs) is not int or epochs < 1 or type(tasks_per_epoch) is not int or tasks_per_epoch < 4 or tasks_per_epoch % 4:
        raise ValueError("Invalid prospective epoch schedule")
    rng = random.Random(digest(["v35-targets", seed, domain]))
    branches = [[] for _ in range(4)]
    tasks = []
    for epoch in range(epochs):
        for branch, ops in enumerate(branches):
            ops.append(branch + 1 if epoch == 0 else rng.randrange(1, 5))
        order = list(range(4)) * (tasks_per_epoch // 4)
        rng.shuffle(order)
        for index, branch in enumerate(order):
            task = {"task_id": f"v35-{seed}-{domain}-e{epoch}-t{index}", "epoch": epoch,
                    "domain": domain, "slots": epoch + 1, "target": list(branches[branch]),
                    "inputs": native.contexts(seed, domain, epoch, index)}
            validate_task(task)
            tasks.append(task)
    return tasks


def validate_task(task):
    if type(task) is not dict or set(task) != {"task_id", "epoch", "domain", "slots", "target", "inputs"}:
        raise ValueError("Invalid externally owned task")
    if (type(task["task_id"]) is not str or not task["task_id"] or task["domain"] not in native.DOMAINS
            or type(task["epoch"]) is not int or task["epoch"] < 0
            or type(task["slots"]) is not int or task["slots"] != task["epoch"] + 1
            or type(task["target"]) is not list or len(task["target"]) != task["slots"]
            or any(type(op) is not int or not 1 <= op <= 4 for op in task["target"])
            or type(task["inputs"]) is not list or len(task["inputs"]) != 4):
        raise ValueError("Invalid task dimensions")
    for case in task["inputs"]:
        if set(case) != {"data", "answers"} or len(case["answers"]) != 5 or len({digest(v) for v in case["answers"]}) != 5:
            raise ValueError("Reference witness omitted or aliased")
    return True


def validate_stream(tasks):
    if not tasks or len({row["task_id"] for row in tasks}) != len(tasks):
        raise ValueError("Empty or duplicate stream")
    for task in tasks:
        validate_task(task)
    if len({t["domain"] for t in tasks}) != 1 or [t["epoch"] for t in tasks] != sorted(t["epoch"] for t in tasks):
        raise ValueError("Reordered or mixed native epochs")
    return digest(tasks)
