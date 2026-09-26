"""External matched-budget evaluation records for cognitive architectures.

This module deliberately sits outside lineage-held proposal machinery. It binds evaluator identity,
case-set identity, external budget, capability outcomes and directly observed resource measurements
to an architecture. CPU process time is a compute proxy only; energy is absent unless supplied by a
real measurement instrument.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

MEASUREMENT_SCHEMA = "genesis-cognitive-measurement-v1"
COMPARISON_SCHEMA = "genesis-cognitive-matched-comparison-v1"


class CognitiveMeasurementError(ValueError):
    """Raised when external cognitive evidence is incomplete or mismatched."""


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CognitiveMeasurementError("measurement contains non-canonical data") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExternalBudget:
    case_limit: int
    max_node_executions_per_case: int

    def __post_init__(self) -> None:
        if self.case_limit < 1 or self.max_node_executions_per_case < 0:
            raise CognitiveMeasurementError("external evaluation budget is invalid")

    def record(self) -> dict[str, int]:
        return {
            "case_limit": self.case_limit,
            "max_node_executions_per_case": self.max_node_executions_per_case,
        }


def create_measurement(
    *,
    architecture_digest: str,
    evaluator_digest: str,
    case_set_digest: str,
    budget: ExternalBudget,
    case_results: Sequence[Mapping[str, Any]],
    cpu_process_time_ns: int,
    peak_memory_bytes: int | None = None,
    energy_joules: float | None = None,
    energy_instrument: str | None = None,
) -> dict[str, Any]:
    """Create content-addressed external evidence without inferring unmeasured energy."""
    if not architecture_digest or not evaluator_digest or not case_set_digest:
        raise CognitiveMeasurementError("architecture, evaluator and case-set identities are required")
    if len(case_results) > budget.case_limit:
        raise CognitiveMeasurementError("measurement exceeds external case budget")
    if cpu_process_time_ns < 0:
        raise CognitiveMeasurementError("CPU process time cannot be negative")
    if peak_memory_bytes is not None and peak_memory_bytes < 0:
        raise CognitiveMeasurementError("peak memory cannot be negative")
    if (energy_joules is None) != (energy_instrument is None):
        raise CognitiveMeasurementError(
            "energy value and real measurement instrument identity must be supplied together"
        )
    if energy_joules is not None and energy_joules < 0:
        raise CognitiveMeasurementError("measured energy cannot be negative")

    normalized = []
    seen = set()
    for raw in case_results:
        case_digest = str(raw.get("case_digest") or "")
        if not case_digest or case_digest in seen:
            raise CognitiveMeasurementError("case results require unique content identities")
        seen.add(case_digest)
        calls = int(raw.get("node_executions", -1))
        if calls < 0 or calls > budget.max_node_executions_per_case:
            raise CognitiveMeasurementError("case exceeds external node-execution budget")
        normalized.append({
            "case_digest": case_digest,
            "passed": bool(raw.get("passed", False)),
            "node_executions": calls,
        })
    normalized.sort(key=lambda row: row["case_digest"])
    passed = sum(1 for row in normalized if row["passed"])
    payload = {
        "schema": MEASUREMENT_SCHEMA,
        "architecture_digest": str(architecture_digest),
        "evaluator_digest": str(evaluator_digest),
        "case_set_digest": str(case_set_digest),
        "budget": budget.record(),
        "case_results": normalized,
        "capability": {"passed": passed, "evaluated": len(normalized)},
        "resources": {
            "node_executions": sum(row["node_executions"] for row in normalized),
            "cpu_process_time_ns": int(cpu_process_time_ns),
            "cpu_time_is_compute_proxy": True,
            "peak_memory_bytes": peak_memory_bytes,
            "energy_joules": energy_joules,
            "energy_measurement_available": energy_joules is not None,
            "energy_instrument": energy_instrument,
        },
    }
    return {**payload, "measurement_digest": _digest(payload)}


def compare_matched(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Bind two measurements only when evaluator, cases and external budget are identical."""
    for field in ("evaluator_digest", "case_set_digest", "budget"):
        if parent.get(field) != candidate.get(field):
            raise CognitiveMeasurementError("comparison is not matched on %s" % field)
    if parent.get("architecture_digest") == candidate.get("architecture_digest"):
        raise CognitiveMeasurementError("comparison requires distinct architecture identities")
    parent_cases = tuple(row.get("case_digest") for row in parent.get("case_results", ()))
    candidate_cases = tuple(row.get("case_digest") for row in candidate.get("case_results", ()))
    if parent_cases != candidate_cases:
        raise CognitiveMeasurementError("comparison requires identical evaluated case identities")
    for record in (parent, candidate):
        expected = record.get("measurement_digest")
        payload = {key: value for key, value in record.items() if key != "measurement_digest"}
        if record.get("schema") != MEASUREMENT_SCHEMA or expected != _digest(payload):
            raise CognitiveMeasurementError("measurement identity does not reproduce")

    pcap, ccap = parent["capability"], candidate["capability"]
    pres, cres = parent["resources"], candidate["resources"]
    payload = {
        "schema": COMPARISON_SCHEMA,
        "parent_measurement_digest": parent["measurement_digest"],
        "candidate_measurement_digest": candidate["measurement_digest"],
        "matched_evaluator_digest": parent["evaluator_digest"],
        "matched_case_set_digest": parent["case_set_digest"],
        "matched_budget": parent["budget"],
        "capability_delta_passed": int(ccap["passed"]) - int(pcap["passed"]),
        "node_executions_delta": int(cres["node_executions"]) - int(pres["node_executions"]),
        "cpu_process_time_delta_ns": int(cres["cpu_process_time_ns"]) - int(pres["cpu_process_time_ns"]),
        "energy_delta_joules": (
            float(cres["energy_joules"]) - float(pres["energy_joules"])
            if cres.get("energy_measurement_available") and pres.get("energy_measurement_available")
            else None
        ),
        "energy_comparison_available": bool(
            cres.get("energy_measurement_available") and pres.get("energy_measurement_available")
        ),
    }
    return {**payload, "comparison_digest": _digest(payload)}
