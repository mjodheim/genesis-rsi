"""Outcome-independent epoch generator; materialize and commit before behavior."""
import random

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v34 import programs

DEV_SEEDS = (503, 887)
FRESH_SEEDS = (786433, 1048583, 1310719)
INITIAL_EPOCHS = 8
TASKS_PER_DOMAIN = 6


def target(seed, domain, epoch, branch):
    if type(epoch) is not int or not 0 <= epoch < programs.MAX_STEPS:
        raise ValueError("Epoch exceeds preregistered representation capacity")
    rng = random.Random(f"mira-v34/{seed}/{domain}/{branch}")
    return programs.validate({"domain": domain, "steps": [branch, *(rng.randrange(4) for _ in range(epoch))]})


def stream(seed, epoch):
    rng = random.Random(f"mira-v34-inputs/{seed}/{epoch}")
    tasks = []
    for domain in programs.DOMAINS[:min(epoch + 1, len(programs.DOMAINS))]:
        inputs = list(programs.WITNESSES[domain])
        if domain == "arithmetic":
            inputs += [rng.randrange(-20, 21) for _ in range(6)]
        elif domain == "text":
            inputs += ["".join(rng.choice("abcxyz") for _ in range(rng.randrange(1, 12))) for _ in range(6)]
        elif domain == "sequence":
            inputs += [[rng.randrange(-9, 10) for _ in range(rng.randrange(1, 8))] for _ in range(6)]
        else:
            inputs += [{key: rng.randrange(-9, 10) for key in ("a", "b", "noise", "d")} for _ in range(6)]
        for index, (old_epoch, branch) in enumerate([*( (epoch, branch) for branch in range(4)),
                                                  (max(0, epoch - 1), 0), (max(0, epoch - 1), 2)]):
            tasks.append({"task_id": f"v34-s{seed}-e{epoch}-{domain}-{index}", "window": epoch,
                          "domain": domain, "inputs": inputs, "target": target(seed, domain, old_epoch, branch)})
    validate_stream(tasks)
    return tasks


def validate_task(task):
    if (type(task) is not dict or set(task) != {"task_id", "window", "domain", "inputs", "target"}
            or type(task["task_id"]) is not str or not task["task_id"]
            or type(task["window"]) is not int or task["window"] < 0
            or task["domain"] not in programs.DOMAINS or type(task["inputs"]) is not list
            or not 1 <= len(task["inputs"]) <= 32
            or any(not programs.valid_value(task["domain"], value) for value in task["inputs"])):
        raise ValueError("Invalid externally governed task schema")
    if programs.validate(task["target"])["domain"] != task["domain"]:
        raise ValueError("Target and task domains differ")
    return True


def validate_stream(tasks):
    if not tasks or len({row["task_id"] for row in tasks}) != len(tasks):
        raise ValueError("Empty or duplicate epoch")
    for task in tasks:
        validate_task(task)
    if len({row["window"] for row in tasks}) != 1:
        raise ValueError("Epoch mixing is forbidden")
    return digest(tasks)


def population_sha256():
    return digest({str(seed): [stream(seed, epoch) for epoch in range(INITIAL_EPOCHS)] for seed in FRESH_SEEDS})
