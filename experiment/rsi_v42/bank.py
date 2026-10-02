"""V42 development reuses the consumed V35 public curriculum exactly."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import bank as base
DEV_SEEDS=base.DEV_SEEDS
FRESH_SEEDS=(86028121,86028157,86028193)
INITIAL_EPOCHS=base.INITIAL_EPOCHS
TASKS_PER_DOMAIN=base.TASKS_PER_DOMAIN
target=base.target
stream=base.stream
validate_task=base.validate_task
validate_stream=base.validate_stream
def population_sha256():
    return digest({str(seed): [stream(seed,e) for e in range(INITIAL_EPOCHS)] for seed in FRESH_SEEDS})
