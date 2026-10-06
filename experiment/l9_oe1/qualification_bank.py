"""Prospective L9-OE1 multi-domain qualification population."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native

QUALIFICATION_SEED = 86753091
EPOCHS = 12
TASKS_PER_EPOCH = 16
BLOCK = 3
TRANSFER_TARGETS = 8


def stream(domain):
    if domain not in native.DOMAINS:
        raise ValueError("Unknown native domain")
    rng = random.Random(
        digest(["l9-oe1-qualification", QUALIFICATION_SEED, domain])
    )
    motifs = [
        [first, rng.randrange(1, 5), rng.randrange(1, 5)]
        for first in range(1, 5)
    ]
    tasks = []

    for epoch in range(EPOCHS):
        if epoch < BLOCK:
            targets = [motif[: epoch + 1] for motif in motifs]
        else:
            blocks = epoch - BLOCK + 2
            targets = []
            while len(targets) < TRANSFER_TARGETS:
                target = sum(
                    (motifs[rng.randrange(4)] for _ in range(blocks)),
                    [],
                )
                if target not in targets:
                    targets.append(target)

        repeats = TASKS_PER_EPOCH // len(targets)
        order = list(range(len(targets))) * repeats
        rng.shuffle(order)

        for index, branch in enumerate(order):
            target = targets[branch]
            task = {
                "task_id": f"l9oe1-{QUALIFICATION_SEED}-{domain}-e{epoch}-t{index}",
                "epoch": epoch,
                "domain": domain,
                "slots": len(target),
                "target": list(target),
                "inputs": native.contexts(
                    QUALIFICATION_SEED,
                    domain,
                    epoch,
                    index,
                ),
            }
            validate_task(task)
            tasks.append(task)

    validate_stream(tasks)
    return tasks


def validate_task(task):
    if (
        type(task) is not dict
        or set(task)
        != {"task_id", "epoch", "domain", "slots", "target", "inputs"}
    ):
        raise ValueError("Invalid externally owned task")

    if (
        type(task["task_id"]) is not str
        or not task["task_id"]
        or task["domain"] not in native.DOMAINS
        or type(task["epoch"]) is not int
        or not 0 <= task["epoch"] < EPOCHS
        or type(task["slots"]) is not int
        or task["slots"] < 1
        or type(task["target"]) is not list
        or len(task["target"]) != task["slots"]
        or any(type(op) is not int or not 1 <= op <= 4 for op in task["target"])
        or type(task["inputs"]) is not list
        or len(task["inputs"]) != 4
    ):
        raise ValueError("Invalid qualification task dimensions")
    return True


def validate_stream(tasks):
    if len(tasks) != EPOCHS * TASKS_PER_EPOCH:
        raise ValueError("Qualification stream length changed")
    if len({task["task_id"] for task in tasks}) != len(tasks):
        raise ValueError("Duplicate qualification task")
    for task in tasks:
        validate_task(task)
    if [task["epoch"] for task in tasks] != sorted(
        task["epoch"] for task in tasks
    ):
        raise ValueError("Qualification tasks reordered")
    return digest(tasks)


def population_sha256():
    return digest({
        domain: stream(domain)
        for domain in native.DOMAINS
    })
