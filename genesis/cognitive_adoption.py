"""External adoption, rollback and causal-ablation evidence for cognitive architectures.

These records remain host-side evidence. Mutable lineage machinery may propose architectures, but it
does not receive authority to grade, adopt, roll back or declare a causal win.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from genesis.cognitive_measurement import CognitiveMeasurementError, compare_matched

ADOPTION_SCHEMA = "genesis-cognitive-adoption-v1"
ROLLBACK_SCHEMA = "genesis-cognitive-rollback-v1"
ABLATION_SCHEMA = "genesis-cognitive-causal-ablation-v1"


class CognitiveAdoptionError(ValueError):
    """Raised when external adoption evidence is incomplete or inconsistent."""


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CognitiveAdoptionError("evidence contains non-canonical data") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _verified_comparison(parent: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    try:
        return compare_matched(parent, candidate)
    except CognitiveMeasurementError as exc:
        raise CognitiveAdoptionError(str(exc)) from exc


def create_adoption_record(
    *,
    parent_measurement: Mapping[str, Any],
    candidate_measurement: Mapping[str, Any],
    decision: str,
    authority_digest: str,
    rule_digest: str,
    proposal_digest: str,
) -> dict[str, Any]:
    """Bind an externally supplied decision to reproducible matched evidence."""
    if decision not in {"adopt", "reject"}:
        raise CognitiveAdoptionError("decision must be externally supplied as adopt or reject")
    if not authority_digest or not rule_digest or not proposal_digest:
        raise CognitiveAdoptionError("decision authority, prospective rule and proposal identities are required")
    comparison = _verified_comparison(parent_measurement, candidate_measurement)
    payload = {
        "schema": ADOPTION_SCHEMA,
        "decision": decision,
        "authority_digest": str(authority_digest),
        "rule_digest": str(rule_digest),
        "proposal_digest": str(proposal_digest),
        "parent_architecture_digest": parent_measurement["architecture_digest"],
        "candidate_architecture_digest": candidate_measurement["architecture_digest"],
        "parent_measurement_digest": parent_measurement["measurement_digest"],
        "candidate_measurement_digest": candidate_measurement["measurement_digest"],
        "comparison_digest": comparison["comparison_digest"],
    }
    return {**payload, "adoption_digest": _digest(payload)}


def create_rollback_record(
    *,
    adoption_record: Mapping[str, Any],
    authority_digest: str,
    reason_evidence_digest: str,
) -> dict[str, Any]:
    """Record an external rollback to the exact parent of a prior adopted descendant."""
    expected = adoption_record.get("adoption_digest")
    payload_to_check = {k: v for k, v in adoption_record.items() if k != "adoption_digest"}
    if adoption_record.get("schema") != ADOPTION_SCHEMA or expected != _digest(payload_to_check):
        raise CognitiveAdoptionError("adoption identity does not reproduce")
    if adoption_record.get("decision") != "adopt":
        raise CognitiveAdoptionError("only an adopted descendant can be rolled back")
    if not authority_digest or not reason_evidence_digest:
        raise CognitiveAdoptionError("rollback authority and evidence identities are required")
    payload = {
        "schema": ROLLBACK_SCHEMA,
        "adoption_digest": expected,
        "authority_digest": str(authority_digest),
        "reason_evidence_digest": str(reason_evidence_digest),
        "from_architecture_digest": adoption_record["candidate_architecture_digest"],
        "restore_architecture_digest": adoption_record["parent_architecture_digest"],
    }
    return {**payload, "rollback_digest": _digest(payload)}


def create_causal_ablation_record(
    *,
    parent_measurement: Mapping[str, Any],
    candidate_measurement: Mapping[str, Any],
    ablated_measurement: Mapping[str, Any],
    proposal_digest: str,
    ablation_digest: str,
) -> dict[str, Any]:
    """Describe a paired ablation contrast without declaring that causality was established."""
    if not proposal_digest or not ablation_digest:
        raise CognitiveAdoptionError("proposal and ablation identities are required")
    candidate_comparison = _verified_comparison(parent_measurement, candidate_measurement)
    ablated_comparison = _verified_comparison(parent_measurement, ablated_measurement)
    identities = {
        parent_measurement["architecture_digest"],
        candidate_measurement["architecture_digest"],
        ablated_measurement["architecture_digest"],
    }
    if len(identities) != 3:
        raise CognitiveAdoptionError("parent, candidate and ablated architectures must be distinct")
    payload = {
        "schema": ABLATION_SCHEMA,
        "proposal_digest": str(proposal_digest),
        "ablation_digest": str(ablation_digest),
        "parent_measurement_digest": parent_measurement["measurement_digest"],
        "candidate_measurement_digest": candidate_measurement["measurement_digest"],
        "ablated_measurement_digest": ablated_measurement["measurement_digest"],
        "candidate_comparison_digest": candidate_comparison["comparison_digest"],
        "ablated_comparison_digest": ablated_comparison["comparison_digest"],
        "candidate_capability_delta_passed": candidate_comparison["capability_delta_passed"],
        "ablated_capability_delta_passed": ablated_comparison["capability_delta_passed"],
        "capability_attenuation_under_ablation": (
            candidate_comparison["capability_delta_passed"]
            - ablated_comparison["capability_delta_passed"]
        ),
        "causal_verdict": None,
    }
    return {**payload, "causal_ablation_record_digest": _digest(payload)}
