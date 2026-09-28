"""Deterministic local E0 benchmark for the Energy/Compute Frontier.

Characterizes compute-proxy/latency/memory dynamics before optimization. It
never reports or estimates energy.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import platform
import ssl
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from genesis.energy_measurement import create_resource_measurement

SCHEMA = "genesis-energy-e0-benchmark-v2"
DEFAULT_WORK_UNITS = (200, 2_000, 20_000)
DEFAULT_REPEATS = 5


def _digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _source_digest(function: Any) -> str:
    return hashlib.sha256(inspect.getsource(function).encode("utf-8")).hexdigest()


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


def _cpu_model() -> str:
    if sys.platform.startswith("linux"):
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.lower().startswith(("model name", "hardware")) and ":" in line:
                    return line.split(":", 1)[1].strip() or "unknown"
        except OSError:
            pass
    return platform.processor() or platform.machine() or "unknown"


def run_once(units: int) -> dict[str, Any]:
    if isinstance(units, bool) or not isinstance(units, int) or units <= 0:
        raise ValueError("work units must be a positive integer")

    tracing_was_active = tracemalloc.is_tracing()
    if not tracing_was_active:
        tracemalloc.start()
    try:
        cpu_start = time.process_time_ns()
        wall_start = time.perf_counter_ns()
        output_digest, _reported_node_executions = _work(units)
        wall_ns = time.perf_counter_ns() - wall_start
        cpu_ns = time.process_time_ns() - cpu_start
        _, observed_peak_bytes = tracemalloc.get_traced_memory()
    finally:
        if not tracing_was_active and tracemalloc.is_tracing():
            tracemalloc.stop()

    peak_bytes = None if tracing_was_active else observed_peak_bytes
    workload_digest = _source_digest(_work)
    evaluator_digest = _source_digest(_expected_output)
    subject = {"benchmark": SCHEMA, "workload_sha256": workload_digest}
    case = {"subject": subject, "work_units": units}
    # Node executions are imposed by the externally defined benchmark case,
    # never trusted from the mutable workload return value.
    node_executions = units
    expected_output = _expected_output(units)
    passed = output_digest == expected_output
    cases = [{"case_digest": _digest(case), "passed": passed, "node_executions": node_executions}]
    measurement = create_resource_measurement(
        subject_digest=_digest(subject),
        evaluator_digest=evaluator_digest,
        case_set_digest=_digest({"cases": [case]}),
        budget_digest=_digest({"max_node_executions": units, "algorithm": "sha256-chain-v1"}),
        hardware_identity={
            "machine": platform.machine() or "unknown",
            "cpu_model": _cpu_model(),
            "platform": platform.platform(),
        },
        runtime_identity={
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "python_build": list(platform.python_build()),
            "openssl_version": ssl.OPENSSL_VERSION,
            "hashlib_sha256": hashlib.sha256().name,
        },
        measurement_provenance={
            "cpu_clock": "time.process_time_ns",
            "wall_clock": "time.perf_counter_ns",
            "memory": ("tracemalloc.get_traced_memory" if not tracing_was_active else "unavailable-preexisting-tracer-preserved"),
            "workload_sha256": workload_digest,
            "evaluator_sha256": evaluator_digest,
        },
        case_results=cases,
        cpu_process_time_ns=cpu_ns,
        wall_latency_ns=wall_ns,
        peak_memory_bytes=peak_bytes,
    )
    # Output is authenticated separately because the generic resource schema
    # intentionally does not define workload-specific result fields.
    return {
        **measurement,
        "output_digest": output_digest,
        "output_binding_digest": _digest({
            "measurement_digest": measurement["measurement_digest"],
            "output_digest": output_digest,
        }),
    }


def run_benchmark(
    *, work_units: tuple[int, ...] = DEFAULT_WORK_UNITS, repeats: int = DEFAULT_REPEATS
) -> dict[str, Any]:
    if repeats < 2:
        raise ValueError("at least two repeats are required to characterize variance")
    if len(work_units) < 2 or any(a >= b for a, b in zip(work_units, work_units[1:])):
        raise ValueError("work units must contain at least two strictly increasing levels")

    grouped: dict[int, list[dict[str, Any]]] = {units: [] for units in work_units}
    # Rotate the order each repeat to reduce monotonic warm-up/thermal confounding.
    for repeat in range(repeats):
        order = work_units[repeat % len(work_units):] + work_units[:repeat % len(work_units)]
        for units in order:
            grouped[units].append(run_once(units))

    rows = []
    for units in work_units:
        samples = grouped[units]
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

    all_valid = all(
        sample["capability"] == {"passed": 1, "evaluated": 1}
        for row in rows for sample in row["samples"]
    )
    cpu_separated = all(
        a["summary"]["cpu_process_time_ns_max"] < b["summary"]["cpu_process_time_ns_min"]
        for a, b in zip(rows, rows[1:])
    )
    wall_separated = all(
        a["summary"]["wall_latency_ns_max"] < b["summary"]["wall_latency_ns_min"]
        for a, b in zip(rows, rows[1:])
    )
    dynamic = {
        "all_samples_valid": all_valid,
        "cpu_proxy_has_resolved_dynamic_range": all_valid and cpu_separated,
        "wall_latency_has_resolved_dynamic_range": all_valid and wall_separated,
        "criterion": "all samples valid and all adjacent workload sample ranges strictly non-overlapping",
    }
    return {
        "schema": SCHEMA,
        "python_executable": sys.executable,
        "repeats": repeats,
        "sampling_order": "rotating-interleaved",
        "energy_claim": False,
        "energy_joules": None,
        "rows": rows,
        "dynamic_range_checks": dynamic,
    }


def main() -> None:
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
