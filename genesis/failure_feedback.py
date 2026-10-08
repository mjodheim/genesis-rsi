"""Typed, provenance-preserving observations from failed PUBLIC tests.

This module does not propose that a specific patch is correct. It converts
the already-observed failure into a falsifiable behavioral question. It never
reads private or held-out expected results and never uses human reference
fixes. Suggestions are experimental labels, not accuracy claims.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any
from genesis.trust_root import digest_of

_HEADER = re.compile(
    r"^---\s+(?P<test>[A-Za-z_][\w.$]*)::(?P<method>[A-Za-z_][\w$]*)\s*$",
    re.MULTILINE,
)
_EXPECTED_ACTUAL = re.compile(
    r"expected:<(?P<expected>.*?)>\s+but\s+was:<(?P<actual>.*?)>",
)
_EXPECTED_IDENTITY = re.compile(r"expected same:<.*?>\s+was not:<.*?>")
_EXCEPTION = re.compile(
    r"^(?P<exception>[\w$.]*(?:Exception|Error))(?:\s*:\s*(?P<message>.*))?$",
    re.MULTILINE,
)
_SUGGESTED = {
    "value_mismatch": (
        "recompute public expected-versus-actual path",
        "verify boundaries and state update timing",
    ),
    "identity_mismatch": (
        "check identity-preserving wrapper/factory contract",
        "compare reference identity vs value equality",
    ),
    "assertion_unspecified": (
        "inspect public assertion predicate and dataflow",
        "consider special numeric values and state invariants",
    ),
    "runtime_exception": (
        "minimize the throwing path",
        "inspect nullability, bounds and object lifecycle",
    ),
}


def _classify(text: str) -> tuple[str, str | None, str | None, str | None]:
    if _EXPECTED_IDENTITY.search(text):
        return "identity_mismatch", None, None, None
    value = _EXPECTED_ACTUAL.search(text)
    if value:
        return "value_mismatch", value["expected"][:200], value["actual"][:200], None
    lines = [line.strip() for line in text.splitlines()[:6] if line.strip()]
    for line in lines:
        m = _EXCEPTION.fullmatch(line)
        if m and "Assertion" not in m["exception"]:
            return "runtime_exception", None, None, m["exception"]
    if lines:
        return "assertion_unspecified", None, None, None
    return "unknown", None, None, None


def analyze_public_failures(
    failures_text: str,
    *,
    max_entries: int = 24,
) -> dict[str, Any]:
    if not (1 <= max_entries <= 100):
        raise ValueError("max_entries outside [1,100]")
    # Refuse reading megabytes of accidental private artifacts.
    source = failures_text[:256_000]
    matches = list(_HEADER.finditer(source))[:max_entries]
    observations = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        details = source[match.end():end].lstrip("\n")
        outcome, expected, actual, exception = _classify(details)
        statement = {
            "test_class": match["test"],
            "test_method": match["method"],
            "symptom": outcome,
            "expected_public_observation": expected,
            "actual_public_observation": actual,
            "exception_type": exception,
            "diagnostic_questions": list(_SUGGESTED.get(outcome, ())),
            "repair_proven": False,
            "fault_location_proven": False,
            "source": "public_failing_tests",
        }
        observations.append({**statement, "observation_digest": digest_of(statement)})
    payload = {
        "schema": "genesis-public-failure-observations-v1",
        "failure_count": len(observations),
        "observations": observations,
        "source_is_public_project_test_result": True,
        "human_reference_fix_used": False,
        "operator_family_selected": None,
        "selection_feedback_only": True,
    }
    return {**payload, "evidence_digest": digest_of(payload)}
