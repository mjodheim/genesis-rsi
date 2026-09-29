"""Regressions for the deterministic Energy/Compute E0 benchmark."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "experiment" / "energy_frontier" / "e0_benchmark.py"


def _load():
    spec = importlib.util.spec_from_file_location("energy_e0_benchmark", PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bench = _load()


def test_e0_single_run_keeps_energy_unavailable_and_binds_identity():
    row = bench.run_once(8)
    assert row["resources"]["energy_joules"] is None
    assert row["resources"]["energy_measurement_available"] is False
    assert row["resources"]["cpu_time_is_compute_proxy"] is True
    assert row["resources"]["node_executions"] == 8
    assert row["capability"] == {"passed": 1, "evaluated": 1}
    assert len(row["measurement_provenance"]["workload_sha256"]) == 64
    assert len(row["measurement_provenance"]["evaluator_sha256"]) == 64
    assert len(row["output_binding_digest"]) == 64
    assert row["hardware_identity"]["cpu_model"]
    assert row["measurement_provenance"]["node_executions_semantics"] == (
        "externally_imposed_work_budget_not_observed_execution_count"
    )
    assert row["measurement_provenance"]["oracle_timing"] == "precomputed_before_measured_interval"
    assert row["measurement_provenance"]["case_identity_subject_independent"] is True


def test_e0_repeated_benchmark_records_separate_resource_dimensions():
    result = bench.run_benchmark(work_units=(8, 64), repeats=2)
    assert result["energy_claim"] is False
    assert result["energy_joules"] is None
    assert result["repeats"] == 2
    assert result["sampling_order"] == "rotating-interleaved"
    assert [row["work_units"] for row in result["rows"]] == [8, 64]
    for row in result["rows"]:
        assert len(row["samples"]) == 2
        assert "cpu_process_time_ns_median" in row["summary"]
        assert "wall_latency_ns_median" in row["summary"]
        for sample in row["samples"]:
            assert sample["resources"]["energy_joules"] is None


def test_e0_evaluator_detects_corrupted_work_and_disables_dynamic_range(monkeypatch):
    monkeypatch.setattr(bench, "_work", lambda units: ("00" * 32, units))
    row = bench.run_once(8)
    assert row["capability"] == {"passed": 0, "evaluated": 1}
    result = bench.run_benchmark(work_units=(8, 64), repeats=2)
    assert result["dynamic_range_checks"]["all_samples_valid"] is False
    assert result["dynamic_range_checks"]["cpu_proxy_has_resolved_dynamic_range"] is False
    assert result["dynamic_range_checks"]["wall_latency_has_resolved_dynamic_range"] is False


def test_e0_does_not_trust_workload_reported_cost(monkeypatch):
    original = bench._work
    monkeypatch.setattr(bench, "_work", lambda units: (original(units)[0], 999999))
    row = bench.run_once(8)
    assert row["resources"]["node_executions"] == 8
    assert row["capability"] == {"passed": 1, "evaluated": 1}


def test_e0_records_runtime_backend_identity():
    row = bench.run_once(8)
    runtime = row["runtime_identity"]
    assert runtime["python_build"]
    assert runtime["openssl_version"]
    assert runtime["hashlib_sha256"] == "sha256"


def test_e0_rejects_duplicate_or_unordered_work_levels():
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


def test_e0_stops_own_tracer_when_workload_raises(monkeypatch):
    import tracemalloc
    if tracemalloc.is_tracing():
        tracemalloc.stop()

    def boom(units):
        raise RuntimeError("boom")

    monkeypatch.setattr(bench, "_work", boom)
    with pytest.raises(RuntimeError, match="boom"):
        bench.run_once(8)
    assert not tracemalloc.is_tracing()


def test_e0_case_identity_is_independent_of_subject_identity(monkeypatch):
    first = bench.run_once(8)
    original_source_digest = bench._source_digest
    monkeypatch.setattr(
        bench,
        "_source_digest",
        lambda function: ("f" * 64 if function is bench._work else original_source_digest(function)),
    )
    second = bench.run_once(8)
    assert first["subject_digest"] != second["subject_digest"]
    assert first["case_set_digest"] == second["case_set_digest"]


def test_e0_oracle_is_computed_before_measured_work(monkeypatch):
    events = []
    original_expected = bench._expected_output
    original_work = bench._work

    def expected(units):
        events.append("oracle")
        return original_expected(units)

    def work(units):
        events.append("work")
        return original_work(units)

    monkeypatch.setattr(bench, "_expected_output", expected)
    monkeypatch.setattr(bench, "_work", work)
    row = bench.run_once(8)
    assert row["capability"] == {"passed": 1, "evaluated": 1}
    assert events == ["oracle", "work"]
