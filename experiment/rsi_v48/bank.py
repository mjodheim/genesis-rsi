"""Prospective successor population; independent salt, unchanged task grammar."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import bank as base

DEV_SEEDS = (503, 887, 86028121, 86028157, 86028193)
FRESH_SEEDS = (104395301, 104395337, 104395373)
INITIAL_EPOCHS = 8
TASKS_PER_DOMAIN = base.TASKS_PER_DOMAIN
target = base.target
stream = base.stream
validate_task = base.validate_task
validate_stream = base.validate_stream


def population_sha256():
    return digest({str(seed): [stream(seed, epoch) for epoch in range(INITIAL_EPOCHS)] for seed in FRESH_SEEDS})
