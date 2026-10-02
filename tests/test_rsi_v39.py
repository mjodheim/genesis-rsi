"""V39 development boundaries; no fresh scientific claim."""
from experiment.rsi_v35 import bank as v35_bank
from experiment.rsi_v39 import bank, engine

def test_development_reuses_consumed_v35_tasks_and_new_seeds_are_disjoint():
    assert bank.DEV_SEEDS == v35_bank.DEV_SEEDS
    assert not set(bank.FRESH_SEEDS) & set(v35_bank.FRESH_SEEDS) & set(bank.DEV_SEEDS)
    for seed in bank.DEV_SEEDS:
        for epoch in range(4):
            assert bank.stream(seed, epoch) == v35_bank.stream(seed, epoch)

def test_v39_keeps_budget_and_exposes_fixed_memory_policy():
    rows = []
    tasks = bank.stream(bank.DEV_SEEDS[0], 0)
    for position, task in enumerate(tasks[:3]):
        row = engine.episode(task, position, rows, "adaptive", isolated=False)
        assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS == 14
        assert row["routing"]["probe_evaluations"] == 2
        assert row["routing"]["memory_policy"] == "compatibility_plus_novelty_frontier_v1"
        assert len(row["routing"]["probe_roles"]) == 2
        rows.append(row)

def test_controls_remain_bounded():
    task = bank.stream(bank.DEV_SEEDS[0], 0)[0]
    for arm in ("recency", "greedy", "cold"):
        row = engine.episode(task, 0, [], arm, isolated=False)
        assert row["charged_evaluations"] <= 14
        assert row["routing"]["frontier_tie_break"] is False
