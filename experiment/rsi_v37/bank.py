"""Unused populations through the preserved V36 rewrite generator."""
from experiment.rsi_v36 import bank as predecessor

DEV_SEEDS = (211, 337)
FRESH_SEEDS = (101909, 202921)
BLOCK = predecessor.BLOCK
EPOCHS = 6
TASKS_PER_EPOCH = 8
validate_task = predecessor.validate_task
validate_stream = predecessor.validate_stream


def stream(seed, domain, *, epochs=EPOCHS, tasks_per_epoch=TASKS_PER_EPOCH):
    return [{**task, "task_id": task["task_id"].replace("v36-", "v37-", 1)}
            for task in predecessor.stream(seed, domain, epochs=epochs, tasks_per_epoch=tasks_per_epoch)]
