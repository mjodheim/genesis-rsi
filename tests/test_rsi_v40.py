"""V40 development boundaries."""
from experiment.rsi_v35 import bank as v35_bank
from experiment.rsi_v40 import bank, engine

def test_same_consumed_curriculum():
    for seed in bank.DEV_SEEDS:
        for epoch in range(4):
            assert bank.stream(seed, epoch) == v35_bank.stream(seed, epoch)

def test_stagnation_flag_is_deterministic_and_bounded():
    tasks = bank.stream(bank.DEV_SEEDS[0], 0)
    prefix=[]
    for position, task in enumerate(tasks[:4]):
        row=engine.episode(task, position, prefix, "adaptive", isolated=False)
        assert row["charged_evaluations"] <= 14
        assert row["routing"]["memory_policy"] == "conditional_stagnation_frontier_v1"
        assert isinstance(row["routing"]["stagnation_trigger"], bool)
        prefix.append(row)

def test_cold_never_uses_stagnation_frontier():
    row=engine.episode(bank.stream(bank.DEV_SEEDS[0],0)[0],0,[],"cold",isolated=False)
    assert row["routing"]["stagnation_trigger"] is False
    assert row["routing"]["frontier_tie_break"] is False
