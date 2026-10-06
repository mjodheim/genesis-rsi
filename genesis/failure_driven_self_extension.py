"""Failure-driven transformation self-extension for the A6c autonomy track.

The scientific boundary is deliberately strict:

1. an autonomous failure is diagnosed without seeing a solution;
2. that diagnosis is retained before any repair-derived acquisition;
3. only a later candidate that has already passed its frozen evaluator may teach
   a structural operator;
4. the operator must replay the passing patch exactly and reproduce its content
   digest;
5. later tasks may use the retained operator without another model call.

This module stores capability, provenance and causal order.  It does not decide
whether a candidate is correct; frozen task evaluators remain authoritative.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis import capability_gaps, structural_operators
from genesis.trust_root import digest_of

MEMORY_SCHEMA = "genesis-a6c-failure-driven-self-extension-memory-v1"
EVENT_SCHEMA = "genesis-a6c-self-extension-event-v1"


class FailureDrivenSelfExtensionError(RuntimeError):
    """Raised when self-extension would break its causal/provenance boundary."""


def _validate_diagnosis(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != capability_gaps.GAP_SCHEMA:
        raise FailureDrivenSelfExtensionError("unsupported capability-gap diagnosis")
    value = dict(record)
    recorded = str(value.pop("diagnosis_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise FailureDrivenSelfExtensionError("capability-gap diagnosis does not reproduce its digest")
    return dict(record)


def _validate_event(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != EVENT_SCHEMA:
        raise FailureDrivenSelfExtensionError("unsupported self-extension event")
    value = dict(record)
    recorded = str(value.pop("event_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise FailureDrivenSelfExtensionError("self-extension event does not reproduce its digest")
    if value.get("kind") not in {"gap_observed", "operator_acquired"}:
        raise FailureDrivenSelfExtensionError("unsupported self-extension event kind")
    return dict(record)


def _event(kind: str, **fields: Any) -> dict[str, Any]:
    payload = {
        "schema": EVENT_SCHEMA,
        "kind": str(kind),
        **fields,
    }
    return {**payload, "event_digest": digest_of(payload)}


def create_memory(
    *,
    generation: int = 0,
    parent_memory_digest: str = "",
    operators: Sequence[Mapping[str, Any]] = (),
    events: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Build canonical append-only A6c capability memory."""
    generation = int(generation)
    if generation < 0:
        raise FailureDrivenSelfExtensionError("memory generation may not be negative")

    validated_operators = [
        structural_operators.validate_operator(operator)
        for operator in operators
    ]
    by_digest: dict[str, dict[str, Any]] = {}
    for operator in validated_operators:
        digest = str(operator["operator_digest"])
        if digest in by_digest:
            raise FailureDrivenSelfExtensionError("memory contains a duplicate structural operator")
        by_digest[digest] = operator

    validated_events = [_validate_event(event) for event in events]
    event_digests = [str(event["event_digest"]) for event in validated_events]
    if len(set(event_digests)) != len(event_digests):
        raise FailureDrivenSelfExtensionError("memory contains a duplicate self-extension event")

    parent = str(parent_memory_digest or "")
    if generation == 0 and parent:
        raise FailureDrivenSelfExtensionError("seed memory may not name a parent")
    if generation > 0 and not parent:
        raise FailureDrivenSelfExtensionError("descendant memory must name its parent")

    payload = {
        "schema": MEMORY_SCHEMA,
        "generation": generation,
        "parent_memory_digest": parent,
        "operators": [by_digest[key] for key in sorted(by_digest)],
        "events": validated_events,
        "external_model_calls_for_memory_logic": 0,
    }
    return {**payload, "memory_digest": digest_of(payload)}


def empty_memory() -> dict[str, Any]:
    return create_memory()


def validate_memory(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != MEMORY_SCHEMA:
        raise FailureDrivenSelfExtensionError("unsupported A6c self-extension memory")
    rebuilt = create_memory(
        generation=int(record.get("generation", -1)),
        parent_memory_digest=str(record.get("parent_memory_digest") or ""),
        operators=list(record.get("operators") or []),
        events=list(record.get("events") or []),
    )
    if rebuilt != dict(record):
        raise FailureDrivenSelfExtensionError("A6c memory does not reconstruct from its fields")
    return rebuilt


def diagnose_failure(
    root: str | Path,
    autonomous_result: Mapping[str, Any],
    *,
    target_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """Diagnose a failed search without inspecting any later solution."""
    if autonomous_result.get("winner") is not None or bool(autonomous_result.get("autonomous_passed")):
        raise FailureDrivenSelfExtensionError("capability-gap diagnosis requires an autonomous miss")
    return capability_gaps.diagnose(
        root,
        autonomous_result,
        target_prefixes=target_prefixes,
    )


def retain_gap(
    memory: Mapping[str, Any],
    diagnosis: Mapping[str, Any],
) -> dict[str, Any]:
    """Persist a pre-solution gap observation so later acquisition has causal order."""
    prior = validate_memory(memory)
    gap = _validate_diagnosis(diagnosis)
    if not bool(gap.get("operator_acquisition_recommended")):
        raise FailureDrivenSelfExtensionError("diagnosis does not recommend operator acquisition")
    if any(
        event.get("kind") == "gap_observed"
        and event.get("diagnosis_digest") == gap["diagnosis_digest"]
        for event in prior["events"]
    ):
        raise FailureDrivenSelfExtensionError("capability gap is already retained")

    event = _event(
        "gap_observed",
        diagnosis_digest=gap["diagnosis_digest"],
        autonomous_report_digest=gap.get("autonomous_report_digest"),
        reasons=list(gap.get("reasons") or []),
        recommended_mode=gap.get("recommended_mode"),
        solution_visible=False,
        external_model_calls=0,
    )
    return create_memory(
        generation=prior["generation"] + 1,
        parent_memory_digest=prior["memory_digest"],
        operators=prior["operators"],
        events=[*prior["events"], event],
    )


def acquire_from_passing_candidate(
    memory: Mapping[str, Any],
    source_root: str | Path,
    candidate: Mapping[str, Any],
    *,
    diagnosis: Mapping[str, Any],
    passing_result_digest: str,
    context_lines: int = 1,
) -> dict[str, Any]:
    """Learn and retain replay-verified structural operators after evaluator PASS."""
    prior = validate_memory(memory)
    gap = _validate_diagnosis(diagnosis)
    passing_digest = str(passing_result_digest or "")
    if not passing_digest:
        raise FailureDrivenSelfExtensionError("passing result digest is required")

    observed = any(
        event.get("kind") == "gap_observed"
        and event.get("diagnosis_digest") == gap["diagnosis_digest"]
        and event.get("solution_visible") is False
        for event in prior["events"]
    )
    if not observed:
        raise FailureDrivenSelfExtensionError(
            "operator acquisition requires the same gap to have been retained before solution use"
        )

    acquisition = structural_operators.acquire_from_candidate(
        source_root,
        candidate,
        source_result_digest=passing_digest,
        context_lines=context_lines,
    )
    if int(acquisition.get("operator_count", 0)) < 1:
        raise FailureDrivenSelfExtensionError("passing outcome yielded no replay-verified operator")

    existing = {operator["operator_digest"]: operator for operator in prior["operators"]}
    added: list[dict[str, Any]] = []
    for raw in acquisition["operators"]:
        operator = structural_operators.validate_operator(raw)
        digest = operator["operator_digest"]
        if digest not in existing:
            existing[digest] = operator
            added.append(operator)

    if not added:
        raise FailureDrivenSelfExtensionError("passing outcome acquired no novel structural operator")

    event = _event(
        "operator_acquired",
        diagnosis_digest=gap["diagnosis_digest"],
        passing_result_digest=passing_digest,
        acquisition_digest=acquisition["acquisition_digest"],
        added_operator_digests=sorted(operator["operator_digest"] for operator in added),
        replay_verified=True,
        external_model_calls=0,
    )
    next_memory = create_memory(
        generation=prior["generation"] + 1,
        parent_memory_digest=prior["memory_digest"],
        operators=list(existing.values()),
        events=[*prior["events"], event],
    )
    return {
        "memory": next_memory,
        "acquisition": acquisition,
        "added_operator_digests": event["added_operator_digests"],
        "external_model_calls": 0,
    }


def generate_candidates(
    memory: Mapping[str, Any],
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 256,
) -> dict[str, Any]:
    """Use retained self-extended capability on a later project/task."""
    held = validate_memory(memory)
    result = structural_operators.generate(
        root,
        held["operators"],
        include_prefixes=include_prefixes,
        max_candidates=max_candidates,
    )
    payload = {
        "memory_digest": held["memory_digest"],
        "memory_generation": held["generation"],
        "operator_count": len(held["operators"]),
        "candidate_set": result,
        "external_model_calls": 0,
    }
    return {**payload, "reuse_digest": digest_of(payload)}
