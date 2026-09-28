"""Deterministic local E0 benchmark for the Energy/Compute Frontier.

This benchmark characterizes observable compute/latency/memory dynamics before any
optimization pressure is introduced. It never reports or estimates energy.
"""
from __future__ import annotations

import hashlib
import json
import platform
import statistics
import sys
import time
import tracemalloc
from typing import Any

from genesis.energy_measurement import create_resource_measurement

SCHEMA = "genesis-energy-e0-benchmark-v1"
DEFAULT_WORK_UNITS = (200, 2_000, 20_000)
DEFAULT_REPEATS = 5


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _work(units: int) -> tuple[str, int]:
    state = b"genesis-e0"
    for index in range(units):
        state = hashlib.sha256(state + index.to_bytes(8, "big")).digest()
    return state.hex(), units


def _expected_output(units: int) -> str:
    expected = b"genesis-e0"
    for index in range(units):
        expected = hashlib.sha256(expected + index.to_bytes(8, "big")).digest()
    return expected.hex()


def run_once(units: int) -> dict[str, Any]:
    if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
        raise ValueError("work units must be a positive integer")

    tracing_was_active = tracemalloc.is_tracing()
    if not tracing_was_active:
        tracemalloc.start()
    cpu_start = time.process_time_ns()
    wall_start = time.perf_counter_ns()
    output_digest, node_executions = _work(units)
    wall_ns = time.perf_counter_ns() - wall_start
    cpu_ns = time.process_time_ns() - cpu_start
    _, observed_peak_bytes = tracemalloc.get_traced_memory()
    if not tracing_was_active:
        tracemalloc.stop()
    peak_bytes = None if tracing_was_active else observed_peak_bytes

    subject = {"benchmark": SCHEMA, "work_units": units}
    passed = output_digest == _expected_output(units)
    cases = [{"case_digest": _digest(subject), "passed": passed, "node_executions": node_executions}]
    return create_resource_measurement(
        subject_digest=_digest(subject),
        evaluator_digest=_digest({"evaluator": "exact-output-completion-v1"}),
        case_set_digest=_digest({"cases": [subject]}),
        budget_digest=_digest({"work_units": units, "algorithm": "sha256-chain-v1"}),
        hardware_identity={
            "machine": platform.machine() or "unknown",
            "processor": platform.processor() or "unknown",
            "platform": platform.platform(),
        },
        runtime_identity={
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
        measurement_provenance={
            "cpu_clock": "time.process_time_ns",
            "wall_clock": "time.perf_counter_ns",
            "memory": ("tracemalloc.get_traced_memory" if not tracing_was_active else "unavailable-preexisting-tracer-preserved"),
        },
        case_results=cases,
        cpu_process_time_ns=cpu_ns,
        wall_latency_ns=wall_ns,
        peak_memory_bytes=peak_bytes,
    ) | {"output_digest": output_digest}


def run_benchmark(
    *, work_units: tuple[int, ...] = DEFAULT_WORK_UNITS, repeats: int = DEFAULT_REPEATS
) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("at least two repeats are required to characterize variance")
    if len(work_units) < 2 or any(a >= b for a, b in zip(work_units, work_units[1:])):
        raise ValueError("work units must contain at least two strictly increasing levels")
    rows = []
    for units in work_units:
        samples = [run_once(units) for _ in range(repeats)]
        cpu = [row["resources"]["cpu_process_time_ns"] for row in samples]
        wall = [row["resources"]["wall_latency_ns"] for row in samples]
        rows.append({
            "work_units": units,
            "samples": samples,
            "summary": {
                "cpu_process_time_ns_median": int(statistics.median(cpu)),
                "cpu_process_time_ns_min": min(cpu),
                "cpu_process_time_ns_max": max(cpu),
                "wall_latency_ns_median": int(statistics.median(wall)),
                "wall_latency_ns_min": min(wall),
                "wall_latency_ns_max": max(wall),
            },
        })

    cpu_separated = all(a["summary"]["cpu_process_time_ns_max"] < b["summary"]["cpu_process_time_ns_min"] for a, b in zip(rows, rows[1:]))
    wall_separated = all(a["summary"]["wall_latency_ns_max"] < b["summary"]["wall_latency_ns_min"] for a, b in zip(rows, rows[1:]))
    dynamic = {
        "cpu_proxy_has_resolved_dynamic_range": cpu_separated,
        "wall_latency_has_resolved_dynamic_range": wall_separated,
        "criterion": "all adjacent workload sample ranges are strictly non-overlapping",
    }
    return {
        "schema": SCHEMA,
        "python_executable": sys.executable,
        "repeats": repeats,
        "energy_claim": False,
        "energy_joules": None,
        "rows": rows,
        "dynamic_range_checks": dynamic,
    }


def main() -> None:
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
