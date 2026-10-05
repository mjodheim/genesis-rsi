"""V53 selective-scaffold tests."""
from pathlib import Path
import tempfile

from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import bank, benchmark, engine, freeze


def test_v53_freeze_verifies():
    assert freeze.verify() is True


def test_v53_population_is_longer_than_v52_and_deterministic():
    assert bank.FRESH_SEEDS == (530061, 530062, 530063)
    assert bank.WINDOWS == 14
    assert bank.TASKS_PER_WINDOW == 12
    for seed in bank.FRESH_SEEDS:
        tasks = bank.stream(seed)
        assert len(tasks) == 168
        assert tasks[0]["width"] == 3
        assert tasks[-1]["width"] == 16
        assert tasks == bank.stream(seed)


def test_v53_scaffold_gate_is_bounded(tmp_path):
    tasks = bank.stream(bank.FRESH_SEEDS[0])
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    rows = []
    for position, task in enumerate(tasks[:90]):
        row = engine.episode(task, position, exact, abstract, isolated=False)
        assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
        if row["routing"]["scaffold_sources"]:
            assert task["width"] >= engine.SCAFFOLD_MIN_WIDTH
            assert row["root_evaluation"]["quality_milli"] <= engine.SCAFFOLD_ROOT_QUALITY_MAX
            assert not row["routing"]["exact_sources"]
            assert not row["routing"]["abstract_sources"]
        engine.remember(exact, abstract, row)
        rows.append(row)
    exact.close()
    abstract.close()


def test_v53_matched_benchmark_runs(tmp_path):
    tasks = bank.stream(bank.FRESH_SEEDS[0])[:24]
    result = benchmark.run(
        bank.FRESH_SEEDS[0],
        tmp_path,
        tasks=tasks,
        isolated=False,
        scope="TEST",
    )
    assert result["tasks"] == 24
    assert set(result) >= {
        "v53", "v52", "v51", "archive", "cold",
        "scaffold_contribution", "deltas",
    }
    assert result["l9_general_open_ended_passed"] is False
