"""V41 development reuses the consumed V35 public curriculum exactly."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import bank as base
DEV_SEEDS=base.DEV_SEEDS
FRESH_SEEDS=(67867967,67867979,67868003)
INITIAL_EPOCHS=base.INITIAL_EPOCHS
TASKS_PER_DOMAIN=base.TASKS_PER_DOMAIN
target=base.target
stream=base.stream
validate_task=base.validate_task
validate_stream=base.validate_stream
def population_sha256():
    return digest({str(seed): [stream(seed, epoch) for epoch in range(INITIAL_EPOCHS)] for seed in FRESH_SEEDS})
