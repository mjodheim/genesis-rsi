"""Composable repair-plan intermediate representation.

The IR turns whole-file mutation candidates into deterministic text edits,
allows compatible edits to be composed, and renders the resulting plan back
to the single-file candidate format used by the ER evaluators.

It deliberately contains no benchmark-, repository-, language-feature- or
bug-specific policy.  Strategy lives in repair_strategist.py.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any, Iterable, Sequence

from genesis.trust_root import digest_of


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TextEdit:
    path: str
    start: int
    end: int
    replacement: str
    operator: str
    component_digest: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start": self.start,
            "end": self.end,
            "replacement": self.replacement,
            "operator": self.operator,
            "component_digest": self.component_digest,
        }


@dataclass(frozen=True)
class RepairPlan:
    path: str
    expected_sha256: str
    edits: tuple[TextEdit, ...]
    component_ids: tuple[str, ...]
    component_operators: tuple[str, ...]
    depth: int
    score: int

    @property
    def digest(self) -> str:
        return digest_of(
            {
                "path": self.path,
                "expected_sha256": self.expected_sha256,
                "edits": [edit.as_payload() for edit in self.edits],
                "component_ids": list(self.component_ids),
                "component_operators": list(self.component_operators),
                "depth": self.depth,
                "score": self.score,
            }
        )


def edits_from_variant(
    *,
    path: str,
    original: str,
    mutated: str,
    operator: str,
    component_digest: str,
) -> tuple[TextEdit, ...]:
    """Recover the minimal outer changed span in linear time.

    Most Genesis atomic generators make one local edit.  Coordinated atomic
    generators may change several nearby sites; representing their complete
    outer span as one indivisible edit preserves semantics and prevents unsafe
    nested composition while avoiding quadratic general-purpose diffing.
    """
    if original == mutated:
        return ()

    limit = min(len(original), len(mutated))
    prefix = 0
    while prefix < limit and original[prefix] == mutated[prefix]:
        prefix += 1

    suffix = 0
    original_remaining = len(original) - prefix
    mutated_remaining = len(mutated) - prefix
    max_suffix = min(original_remaining, mutated_remaining)
    while (
        suffix < max_suffix
        and original[len(original) - 1 - suffix]
        == mutated[len(mutated) - 1 - suffix]
    ):
        suffix += 1

    original_end = len(original) - suffix
    mutated_end = len(mutated) - suffix
    return (
        TextEdit(
            path=path,
            start=prefix,
            end=original_end,
            replacement=mutated[prefix:mutated_end],
            operator=operator,
            component_digest=component_digest,
        ),
    )


def _edits_conflict(left: TextEdit, right: TextEdit) -> bool:
    if left.path != right.path:
        return True
    # Two insertions at exactly the same anchor are ambiguous unless identical.
    if left.start == left.end == right.start == right.end:
        return left.replacement != right.replacement
    # Insertions strictly inside a replaced/deleted interval conflict.
    if left.start == left.end:
        return right.start < left.start < right.end
    if right.start == right.end:
        return left.start < right.start < left.end
    return not (left.end <= right.start or right.end <= left.start)


def compatible(edit_groups: Sequence[Sequence[TextEdit]]) -> bool:
    flat = [edit for group in edit_groups for edit in group]
    for i, left in enumerate(flat):
        for right in flat[i + 1 :]:
            if _edits_conflict(left, right):
                return False
    return True


def apply_edits(original: str, edits: Iterable[TextEdit]) -> str:
    ordered = sorted(edits, key=lambda e: (e.start, e.end), reverse=True)
    out = original
    last_start = len(original) + 1
    for edit in ordered:
        if edit.start < 0 or edit.end < edit.start or edit.end > len(original):
            raise ValueError("edit outside original text")
        if edit.end > last_start:
            raise ValueError("overlapping edits")
        out = out[: edit.start] + edit.replacement + out[edit.end :]
        last_start = edit.start
    return out


def plan_from_candidate(
    *,
    path: str,
    original: str,
    candidate: dict[str, Any],
    score: int,
) -> RepairPlan | None:
    mutated = candidate.get("content_utf8")
    if not isinstance(mutated, str):
        return None
    operator = str(candidate.get("operator") or candidate.get("kind") or "unknown")
    cd = str(candidate.get("candidate_digest") or digest_of(candidate))
    edits = edits_from_variant(
        path=path,
        original=original,
        mutated=mutated,
        operator=operator,
        component_digest=cd,
    )
    if not edits:
        return None
    cid = str(candidate.get("id") or cd[:16])
    return RepairPlan(
        path=path,
        expected_sha256=sha256_text(original),
        edits=edits,
        component_ids=(cid,),
        component_operators=(operator,),
        depth=1,
        score=score,
    )


def compose(left: RepairPlan, right: RepairPlan, *, score_bonus: int = 15) -> RepairPlan | None:
    if left.path != right.path or left.expected_sha256 != right.expected_sha256:
        return None
    if not compatible((left.edits, right.edits)):
        return None

    # Identical text edits add no capability; collapse them.
    unique: dict[tuple[int, int, str], TextEdit] = {}
    for edit in (*left.edits, *right.edits):
        unique[(edit.start, edit.end, edit.replacement)] = edit
    edits = tuple(sorted(unique.values(), key=lambda e: (e.start, e.end, e.replacement)))
    depth = left.depth + right.depth
    if len(edits) < max(len(left.edits), len(right.edits)):
        return None

    ids = tuple(dict.fromkeys((*left.component_ids, *right.component_ids)))
    ops = tuple(dict.fromkeys((*left.component_operators, *right.component_operators)))
    return RepairPlan(
        path=left.path,
        expected_sha256=left.expected_sha256,
        edits=edits,
        component_ids=ids,
        component_operators=ops,
        depth=depth,
        score=max(left.score, right.score) + min(left.score, right.score) // 4 + score_bonus,
    )


def render_candidate(original: str, plan: RepairPlan, *, logical_index: int | None = None) -> dict[str, Any]:
    mutated = apply_edits(original, plan.edits)
    payload = {
        "path": plan.path,
        "operator": "repair_plan",
        "expected_sha256": plan.expected_sha256,
        "content_sha256": sha256_text(mutated),
        "component_ids": list(plan.component_ids),
        "component_operators": list(plan.component_operators),
        "depth": plan.depth,
        "score": plan.score,
        "edits": [edit.as_payload() for edit in plan.edits],
    }
    cd = digest_of(payload)
    out: dict[str, Any] = {
        "kind": "java_plan",
        "id": f"repair-plan-{cd[:16]}",
        "candidate_digest": cd,
        "path": plan.path,
        "operator": "repair_plan",
        "expected_sha256": plan.expected_sha256,
        "content_utf8": mutated,
        "plan": {
            "depth": plan.depth,
            "score": plan.score,
            "component_ids": list(plan.component_ids),
            "component_operators": list(plan.component_operators),
            "edit_count": len(plan.edits),
        },
        "external_model_calls": 0,
    }
    if logical_index is not None:
        out["logical_index"] = logical_index
    return out
