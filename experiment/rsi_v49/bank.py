"""Outcome-independent, prospectively seeded serial-composition curriculum."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v49 import native

DEV_SEEDS = (1601, 2609)
FRESH_SEEDS = (11000027, 19000013)
PILOT_EPOCHS = 4
EPOCHS = 7
TASKS_PER_EPOCH = 8


def validate_task(task):
    if (task["domain"] not in native.DOMAINS or type(task["epoch"]) is not int or task["epoch"] < 0
            or task["slots"] != 1 << task["epoch"] or len(task["target"]) != task["slots"]
            or len(task["inputs"]) != 4 or len(task["answers"]) != 4):
        raise ValueError("Invalid coupled pipeline task")
    native.genome(task["domain"], task["target"])
    if [native.reference(task["target"], text)["value"] for text in task["inputs"]] != task["answers"]:
        raise ValueError("Substituted independent reference")
    return True


def stream(seed, domain, *, epochs=EPOCHS, tasks_per_epoch=TASKS_PER_EPOCH):
    if type(epochs) is not int or epochs < 1 or type(tasks_per_epoch) is not int or tasks_per_epoch < 4 or tasks_per_epoch % 4:
        raise ValueError("Invalid prospective schedule")
    rng = random.Random(digest(["v49-targets", seed, domain]))
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
            texts = native.contexts(seed, domain, epoch, index)
            target = targets[branch]
            tasks.append({"task_id": f"v49-{seed}-{domain}-e{epoch}-t{index}", "epoch": epoch,
                "domain": domain, "slots": len(target), "target": target,
                "inputs": texts, "answers": [native.reference(target, text)["value"] for text in texts]})
    return tasks
