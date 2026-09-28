"""Energy/Compute Frontier measurement records.

Independent from RSI scoring. Observable resource dimensions remain separate, and joules
are never inferred from CPU time, latency, node counts, or TDP.
"""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping, Sequence\n\nfrom genesis.energy_instrument import EnergyInstrumentError, validate_energy_provenance\n
RESOURCE_SCHEMA = "genesis-energy-resource-measurement-v1"
ENERGY_PROVENANCE_FIELDS = (
    "measurement_method", "interval_start", "interval_end", "baseline_treatment",
)


class EnergyMeasurementError(ValueError):
    pass


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise EnergyMeasurementError("resource measurement contains non-canonical data") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def create_resource_measurement(
    *, subject_digest: str, evaluator_digest: str, case_set_digest: str, budget_digest: str,
    hardware_identity: Mapping[str, Any], runtime_identity: Mapping[str, Any],
    measurement_provenance: Mapping[str, Any], case_results: Sequence[Mapping[str, Any]],
    cpu_process_time_ns: int, wall_latency_ns: int, peak_memory_bytes: int | None,
    energy_joules: float | None = None, energy_instrument: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if any(not value for value in (subject_digest, evaluator_digest, case_set_digest, budget_digest)):
        raise EnergyMeasurementError("subject, evaluator, case-set and budget identities are required")
    for name, value in (("hardware", hardware_identity), ("runtime", runtime_identity), ("measurement provenance", measurement_provenance)):
        if not isinstance(value, Mapping) or not value:
            raise EnergyMeasurementError(f"{name} identity is required")
    if cpu_process_time_ns < 0 or wall_latency_ns < 0:
        raise EnergyMeasurementError("time measurements cannot be negative")
    if peak_memory_bytes is not None and peak_memory_bytes < 0:
        raise EnergyMeasurementError("peak memory cannot be negative")
    if (energy_joules is None) != (energy_instrument is None):
        raise EnergyMeasurementError("joules require an identified real energy instrument")
    if energy_joules is not None:
        if isinstance(energy_joules, bool) or not isinstance(energy_joules, (int, float)):
            raise EnergyMeasurementError("joules must be a direct numeric observation")
        if not math.isfinite(float(energy_joules)) or energy_joules < 0:
            raise EnergyMeasurementError("joules must be finite and non-negative")
        if not isinstance(energy_instrument, Mapping) or not energy_instrument:
            raise EnergyMeasurementError("valid energy instrument provenance is required")
        if any(
            not isinstance(energy_instrument.get(field), str)
            or not str(energy_instrument.get(field)).strip()
            for field in ENERGY_PROVENANCE_FIELDS
        ):
            raise EnergyMeasurementError(
                "energy instrument provenance requires method, interval boundaries and baseline treatment"
            )

    normalized = []
    seen = set()
    for raw in case_results:
        case_digest = str(raw.get("case_digest") or "")
        if not case_digest or case_digest in seen:
            raise EnergyMeasurementError("case results require unique content identities")
        seen.add(case_digest)
        passed = raw.get("passed")
        if not isinstance(passed, bool):
            raise EnergyMeasurementError("case passed must be a Boolean")
        calls = raw.get("node_executions")
        if isinstance(calls, bool) or not isinstance(calls, int) or calls < 0:
            raise EnergyMeasurementError("node executions must be a non-negative integer")
        normalized.append({"case_digest": case_digest, "passed": passed, "node_executions": calls})
    normalized.sort(key=lambda row: row["case_digest"])

    payload = {
        "schema": RESOURCE_SCHEMA,
        "subject_digest": str(subject_digest),
        "evaluator_digest": str(evaluator_digest),
        "case_set_digest": str(case_set_digest),
        "budget_digest": str(budget_digest),
        "hardware_identity": dict(hardware_identity),
        "runtime_identity": dict(runtime_identity),
        "measurement_provenance": dict(measurement_provenance),
        "case_results": normalized,
        "capability": {"passed": sum(1 for row in normalized if row["passed"]), "evaluated": len(normalized)},
        "resources": {
            "node_executions": sum(row["node_executions"] for row in normalized),
            "cpu_process_time_ns": int(cpu_process_time_ns),
            "cpu_time_is_compute_proxy": True,
            "wall_latency_ns": int(wall_latency_ns),
            "peak_memory_bytes": peak_memory_bytes,
            "energy_joules": energy_joules,
            "energy_measurement_available": energy_joules is not None,
            "energy_instrument": dict(energy_instrument) if energy_instrument is not None else None,
        },
    }
    return {**payload, "measurement_digest": _digest(payload)}
