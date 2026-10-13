import pytest

from scripts.collect_circuit3_traces import collect


def test_training_traces_are_deterministic_and_budgeted():
    first = collect(budget=100, families=("and", "or"), max_tasks=3)
    second = collect(budget=100, families=("and", "or"), max_tasks=3)
    assert first == second and len(first) == 3
    assert all(row["family"] in ("and", "or") and row["evaluations"] <= 100 for row in first)
    assert all(signal["evaluation"] <= 100 for row in first for signal in row["novel_signals"])


@pytest.mark.parametrize("families", [("less",), ("and", "less"), (), ("random",)])
def test_collector_rejects_held_out_or_unapproved_families(families):
    with pytest.raises(ValueError, match="learning families"):
        collect(budget=100, families=families)


def test_collector_rejects_invalid_limits():
    with pytest.raises(ValueError):
        collect(budget=0, families=("and",))
    with pytest.raises(ValueError):
        collect(budget=100, families=("and",), max_tasks=0)
