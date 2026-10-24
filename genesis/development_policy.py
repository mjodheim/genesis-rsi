"""Bounded, inert development-policy artifacts for the Genesis/Mira boundary.

The policy is data, never code.  Genesis may reorder an admitted repair-rule
alphabet and vary a finite candidate budget.  It cannot execute or judge a
repair.  Promotion consumes complete, matched observations produced by an
external judge.

This is DEVELOPMENT apparatus.  It is not evidence of general repair ability
or recursive self-improvement.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


SCHEMA = "mira-genesis-development-policy-v1"
ALLOWED_RULES = (
    "csharp-semicolon",
    "java-semicolon",
    "js-variable-semicolon",
    "python-block-colon",
    "rust-let-semicolon",
)
MIN_CANDIDATES = 1
MAX_CANDIDATES = 8
MAX_FILES = 1


class DevelopmentPolicyError(ValueError):
    """Raised when an artifact or its selection evidence is not admissible."""


def _canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def create(
    *,
    rule_order: Sequence[str] = ALLOWED_RULES,
    max_candidates: int = 4,
    generation: int = 0,
    parent_policy_digest: str = "",
) -> dict[str, Any]:
    """Build one canonical, content-addressed policy artifact."""
    rules = [str(rule) for rule in rule_order]
    if sorted(rules) != sorted(ALLOWED_RULES):
        raise DevelopmentPolicyError("rule_order must be an exact permutation of the allowlist")
    if not MIN_CANDIDATES <= int(max_candidates) <= MAX_CANDIDATES:
        raise DevelopmentPolicyError("max_candidates is outside the admitted bounds")
    if int(generation) < 0:
        raise DevelopmentPolicyError("generation must be non-negative")
    parent = str(parent_policy_digest)
    if int(generation) == 0 and parent:
        raise DevelopmentPolicyError("generation zero cannot name a parent")
    if int(generation) > 0 and len(parent) != 64:
        raise DevelopmentPolicyError("a descendant must name a SHA-256 parent")
    payload = {
        "generation": int(generation),
        "max_candidates": int(max_candidates),
        "max_files": MAX_FILES,
        "parent_policy_digest": parent,
        "rule_order": rules,
        "schema": SCHEMA,
    }
    return {**payload, "policy_digest": _digest(payload)}


def validate(record: Mapping[str, Any]) -> dict[str, Any]:
    """Reject unknown fields, malformed bounds, lineage breaks and digest drift."""
    if not isinstance(record, Mapping):
        raise DevelopmentPolicyError("policy is not a mapping")
    expected = {
        "generation", "max_candidates", "max_files", "parent_policy_digest",
        "policy_digest", "rule_order", "schema",
    }
    if set(record) != expected or record.get("schema") != SCHEMA:
        raise DevelopmentPolicyError("policy fields or schema are not recognised")
    if record.get("max_files") != MAX_FILES:
        raise DevelopmentPolicyError("only one-file atomic policies are admitted")
    rebuilt = create(
        rule_order=record.get("rule_order") or [],
        max_candidates=int(record.get("max_candidates", 0)),
        generation=int(record.get("generation", -1)),
        parent_policy_digest=str(record.get("parent_policy_digest") or ""),
    )
    if rebuilt != dict(record):
        raise DevelopmentPolicyError("policy does not reconstruct from its canonical fields")
    return rebuilt


def dumps(record: Mapping[str, Any]) -> str:
    """Portable canonical JSON used by consumers and interoperability tests."""
    return _canonical_json(validate(record))


def descendants(parent: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Enumerate the finite one-step neighbourhood without inventing rules."""
    held = validate(parent)
    generation = held["generation"] + 1
    parent_digest = held["policy_digest"]
    proposals: list[dict[str, Any]] = []
    rules = held["rule_order"]
    for index in range(len(rules) - 1):
        changed = list(rules)
        changed[index], changed[index + 1] = changed[index + 1], changed[index]
        proposals.append(create(rule_order=changed, max_candidates=held["max_candidates"],
                                generation=generation, parent_policy_digest=parent_digest))
    for budget in (held["max_candidates"] - 1, held["max_candidates"] + 1):
        if MIN_CANDIDATES <= budget <= MAX_CANDIDATES:
            proposals.append(create(rule_order=rules, max_candidates=budget,
                                    generation=generation, parent_policy_digest=parent_digest))
    return tuple({item["policy_digest"]: item for item in proposals}.values())


def _score(policy: Mapping[str, Any], observations: Iterable[Mapping[str, Any]],
           case_ids: tuple[str, ...], matched_budget: int) -> tuple[int, int, int]:
    held = validate(policy)
    rows = list(observations)
    if len(rows) != len(case_ids):
        raise DevelopmentPolicyError("every policy needs one observation per matched case")
    by_case: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "candidate_budget", "candidates_used", "case_id", "false_positive",
            "judge_digest", "passed", "policy_digest",
        }:
            raise DevelopmentPolicyError("observation fields are not recognised")
        case_id = str(row["case_id"])
        if case_id in by_case or case_id not in case_ids:
            raise DevelopmentPolicyError("observations contain duplicate or foreign cases")
        if row["policy_digest"] != held["policy_digest"]:
            raise DevelopmentPolicyError("observation is attributed to another policy")
        if row["candidate_budget"] != matched_budget:
            raise DevelopmentPolicyError("policies were not judged under a matched budget")
        used = int(row["candidates_used"])
        if used < 0 or used > matched_budget or used > held["max_candidates"]:
            raise DevelopmentPolicyError("candidate use exceeds the admitted budget")
        if len(str(row["judge_digest"])) != 64:
            raise DevelopmentPolicyError("observation has no external-judge identity")
        if not isinstance(row["passed"], bool) or not isinstance(row["false_positive"], bool):
            raise DevelopmentPolicyError("judge outcomes must be booleans")
        by_case[case_id] = row
    if tuple(sorted(by_case)) != case_ids:
        raise DevelopmentPolicyError("the matched case set is incomplete")
    passed = sum(bool(row["passed"]) for row in rows)
    false_positives = sum(bool(row["false_positive"]) for row in rows)
    candidates_used = sum(int(row["candidates_used"]) for row in rows)
    return passed, -false_positives, -candidates_used


def select(
    parent: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    observations: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    case_ids: Sequence[str],
    matched_budget: int,
) -> dict[str, Any]:
    """Adopt only a strictly better descendant under complete external evidence."""
    held_parent = validate(parent)
    cases = tuple(sorted(str(case_id) for case_id in case_ids))
    if not cases or len(set(cases)) != len(cases):
        raise DevelopmentPolicyError("selection needs a non-empty unique case set")
    if not MIN_CANDIDATES <= int(matched_budget) <= MAX_CANDIDATES:
        raise DevelopmentPolicyError("matched budget is outside the admitted bounds")

    pool = [held_parent]
    for candidate in candidates:
        held = validate(candidate)
        if (held["generation"] != held_parent["generation"] + 1 or
                held["parent_policy_digest"] != held_parent["policy_digest"]):
            raise DevelopmentPolicyError("candidate is not a direct descendant of the parent")
        pool.append(held)
    if len({item["policy_digest"] for item in pool}) != len(pool):
        raise DevelopmentPolicyError("selection pool contains duplicate policies")

    scores: dict[str, tuple[int, int, int]] = {}
    for policy in pool:
        digest = policy["policy_digest"]
        scores[digest] = _score(policy, observations.get(digest, ()), cases, matched_budget)
    winner = max(pool, key=lambda item: (scores[item["policy_digest"]], item["policy_digest"]))
    parent_score = scores[held_parent["policy_digest"]]
    winner_score = scores[winner["policy_digest"]]
    adopted = winner["policy_digest"] != held_parent["policy_digest"] and winner_score > parent_score
    selected = winner if adopted else held_parent
    evidence_payload = {
        "case_ids": list(cases),
        "matched_budget": int(matched_budget),
        "scores": {digest: list(scores[digest]) for digest in sorted(scores)},
    }
    certificate_payload = {
        "adopted": adopted,
        "evidence_digest": _digest(evidence_payload),
        "parent_policy_digest": held_parent["policy_digest"],
        "schema": "mira-genesis-development-policy-selection-v1",
        "selected_policy_digest": selected["policy_digest"],
    }
    return {
        **certificate_payload,
        "certificate_digest": _digest(certificate_payload),
        "parent_score": list(parent_score),
        "selected_policy": selected,
        "selected_score": list(scores[selected["policy_digest"]]),
    }
