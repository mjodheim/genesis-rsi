"""Regressions for the deterministic Energy/Compute E0 benchmark."""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiment" / "energy_frontier" / "e0_benchmark.py"


def _load():
    spec = importlib.util.spec_from_file_location("energy_e0_benchmark", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load()


def test_e0_single_run_keeps_energy_unavailable():
    row = bench.run_once(8)
    assert row["resources"]["energy_joules"] is None
    assert row["resources"]["energy_measurement_available"] is False
    assert row["resources"]["cpu_time_is_compute_proxy"] is True
    assert row["resources"]["node_executions"] == 8
    assert row["capability"] == {"passed": 1, "evaluated": 1}


def test_e0_repeated_benchmark_records_separate_resource_dimensions():
    result = bench.run_benchmark(work_units=(8, 64), repeats=2)
    assert result["energy_claim"] is False
    assert result["energy_joules"] is None
    assert result["repeats"] == 2
    assert [row["work_units"] for row in result["rows"]] == [8, 64]
    for row in result["rows"]:
        assert len(row["samples"]) == 2
        assert "cpu_process_time_ns_median" in row["summary"]
        assert "wall_latency_ns_median" in row["summary"]
        for sample in row["samples"]:
            assert sample["resources"]["energy_joules"] is None


def test_e0_evaluator_detects_corrupted_work(monkeypatch):
    monkeypatch.setattr(bench, "_work", lambda units: ("00" * 32, units))
    row = bench.run_once(8)
    assert row["capability"] == {"passed": 0, "evaluated": 1}


def test_e0_rejects_duplicate_or_unordered_work_levels():
    import pytest
    with pytest.raises(ValueError, match="strictly increasing"):
        bench.run_benchmark(work_units=(8, 8), repeats=2)
    with pytest.raises(ValueError, match="strictly increasing"):
        bench.run_benchmark(work_units=(64, 8), repeats=2)


def test_e0_preserves_preexisting_tracemalloc_session():
    import tracemalloc
    tracemalloc.start()
    try:
        row = bench.run_once(8)
        assert tracemalloc.is_tracing()
        assert row["resources"]["peak_memory_bytes"] is None
    finally:
        tracemalloc.stop()
