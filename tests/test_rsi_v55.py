"""V55 feedback-driven diagnostic exploration tests."""
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v55 import engine
from experiment.rsi_v55.diagnostics import (
    diagnose,
    quality_for_distance,
)


def test_sparse_diagnosis_identifies_all_masks_width_10_to_16():
    for width in range(10, 17):
        targets = [1 << bit for bit in range(width)]
        targets += [
            (1 << left) | (1 << right)
            for left in range(width)
            for right in range(left + 1, width)
        ]
        for target in targets:
            root_quality = quality_for_distance(
                width, target.bit_count()
            )
            observations = []
            for _ in range(6):
                state = diagnose(
                    width, root_quality, observations
                )
                if len(state["hypotheses"]) == 1:
                    break
                probe = state["next_probe"]
                assert probe is not None
                quality = quality_for_distance(
                    width, (probe ^ target).bit_count()
                )
                observations.append((probe, quality))
            state = diagnose(width, root_quality, observations)
            assert state["hypotheses"] == (target,)


def test_v55_solves_high_bit_sparse_mask_without_target_access(tmp_path):
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    task = {
        "task_id": "v55-high-bit",
        "window": 13,
        "family": "xor",
        "width": 16,
        "inputs": [
            0, 1, 2, 4, 8, 16, 31, 63,
            127, 255, 511, 1023, 4095, 65535,
        ],
        "target": {
            "width": 16,
            "rotation": 0,
            "mask": (1 << 14) | (1 << 15),
        },
    }
    row = engine.episode(
        task, 0, exact, abstract, isolated=False
    )
    assert row["routing"]["diagnostic_active"] is True
    assert row["routing"]["diagnostic_aborted"] is False
    assert row["solved"] is True
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert len(row["evaluated_diagnostic_probe_sources"]) <= 6

    exact.close()
    abstract.close()


def test_v55_diagnostic_does_not_activate_on_clear_rotation_task(tmp_path):
    exact = ExperimentalMemory(tmp_path / "exact.db")
    abstract = AbstractionMemory(tmp_path / "abstract.db")
    task = {
        "task_id": "v55-rotation",
        "window": 13,
        "family": "rotation",
        "width": 16,
        "inputs": [
            0, 1, 2, 4, 8, 16, 31, 63,
            127, 255, 511, 1023, 4095, 65535,
        ],
        "target": {
            "width": 16,
            "rotation": 7,
            "mask": 0,
        },
    }
    row = engine.episode(
        task, 0, exact, abstract, isolated=False
    )
    assert row["charged_evaluations"] <= engine.MAX_EVALUATIONS
    assert row["routing"]["diagnostic_active"] is False

    exact.close()
    abstract.close()


def test_v55_matched_benchmark_runs_on_synthetic_tasks(tmp_path):
    from experiment.rsi_v55 import benchmark

    tasks = []
    for window, width in enumerate((3, 4, 10, 11)):
        for index in range(3):
            tasks.append({
                "task_id": f"synthetic-{window}-{index}",
                "window": window,
                "family": "xor",
                "width": width,
                "inputs": list(range(min(1 << width, 16))),
                "target": {
                    "width": width,
                    "rotation": 0,
                    "mask": 1 << (index % width),
                },
            })
    result = benchmark.run(
        999999,
        tmp_path,
        tasks=tasks,
        isolated=False,
        scope="TEST",
    )
    assert result["tasks"] == len(tasks)
    assert result["v55"]["evaluations"] <= (
        len(tasks) * engine.MAX_EVALUATIONS
    )
    assert result["l9_general_open_ended_passed"] is False
