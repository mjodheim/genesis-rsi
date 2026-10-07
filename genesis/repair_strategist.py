"""Capability-routed compositional repair strategist.

ER1 J1-J9 showed two repeated failure modes:
1. candidate budget was spent on source files the failing execution never used;
2. useful repair primitives were treated as isolated whole-file mutations even
   when real fixes required coordinated edits.

This module changes the search machinery rather than adding another benchmark
specialist.  It:
- routes generators to an optional dynamic causal source frontier;
- normalizes heterogeneous mutation families into one repair-plan IR;
- ranks applicable capabilities deterministically;
- composes compatible same-file plans to bounded depth;
- emits a single evaluator-facing candidate schema.

The strategist consumes only buggy source, tests available in that checkout,
optional dynamic source paths, and frozen learned machinery.  It does not read
human patches, issue text, benchmark identities, or external models.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
from typing import Any, Callable, Sequence

from genesis import (
    java_calendar_specialist,
    java_empty_segment_parser_mutations,
    java_default_normalization_mutations,
    java_expression_mutations,
    java_progress_mutations,
    java_range_mutations,
    java_structural_mutations,
    java_symbol_mutations,
    java_test_switch_mutations,
    scalar_mutations,
)
from genesis.repair_ir import RepairPlan, compose, plan_from_candidate, render_candidate
from genesis.trust_root import digest_of

SCHEMA = "genesis-capability-routed-compositional-repair-v2"

# The weights encode only abstract ER1 lessons.  Narrow specialists receive a
# modest boost when they actually activate; they do not receive target IDs.
FAMILY_LIMITS: dict[str, int] = {
    "java_default_normalization": 64,
    "java_expression": 64,
    "java_test_switch": 96,
    "java_empty_segment": 96,
    "java_calendar": 64,
    "java_range": 96,
    "java_symbol": 96,
    "java_progress": 96,
    "java_structural": 96,
    "scalar": 96,
}

FAMILY_WEIGHTS: dict[str, int] = {
    "java_default_normalization": 120,
    "java_expression": 110,
    "java_test_switch": 105,
    "java_empty_segment": 100,
    "java_calendar": 100,
    "java_range": 90,
    "java_symbol": 85,
    "java_progress": 80,
    "java_structural": 65,
    "scalar": 50,
}

Generator = Callable[..., dict[str, Any]]
FAMILIES: tuple[tuple[str, Generator], ...] = (
    ("java_default_normalization", java_default_normalization_mutations.generate),
    ("java_expression", java_expression_mutations.generate),
    ("java_test_switch", java_test_switch_mutations.generate),
    ("java_empty_segment", java_empty_segment_parser_mutations.generate),
    ("java_calendar", java_calendar_specialist.generate),
    ("java_range", java_range_mutations.generate),
    ("java_symbol", java_symbol_mutations.generate),
    ("java_progress", java_progress_mutations.generate),
    ("java_structural", java_structural_mutations.generate),
    ("scalar", scalar_mutations.generate),
)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_paths(root: Path, paths: Sequence[str]) -> tuple[str, ...]:
    result: list[str] = []
    for raw in paths:
        value = str(raw).replace("\\", "/").strip("/")
        if not value or ".." in Path(value).parts:
            continue
        path = root / value
        if path.is_file() and value not in result:
            result.append(value)
    return tuple(sorted(result))


def _effective_prefixes(
    root: Path,
    include_prefixes: Sequence[str],
    focus_paths: Sequence[str],
) -> tuple[str, ...]:
    focus = _normalize_paths(root, focus_paths)
    if focus:
        # Dynamic causal evidence is strictly stronger than a broad src prefix.
        return focus
    prefixes = tuple(str(x).replace("\\", "/").strip("/") for x in include_prefixes if str(x).strip("/"))
    return prefixes


def _original_text(root: Path, path: str, cache: dict[str, str]) -> str | None:
    if path in cache:
        return cache[path]
    target = root / path
    try:
        value = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    cache[path] = value
    return value


def _scalar_to_variant(candidate: dict[str, Any]) -> dict[str, Any] | None:
    mutations = candidate.get("mutations")
    if not isinstance(mutations, list) or len(mutations) != 1:
        return None
    mutation = mutations[0]
    if not isinstance(mutation, dict):
        return None
    content = mutation.get("content_utf8")
    path = mutation.get("path")
    expected = mutation.get("expected_sha256")
    if not all(isinstance(x, str) for x in (content, path, expected)):
        return None
    provenance = candidate.get("provenance") or {}
    operator = str(provenance.get("operator") or "scalar")
    return {
        "id": candidate.get("id"),
        "candidate_digest": candidate.get("candidate_digest"),
        "path": path,
        "operator": operator,
        "expected_sha256": expected,
        "content_utf8": content,
        "external_model_calls": 0,
    }


def _normalize_candidate(candidate: dict[str, Any], family: str) -> dict[str, Any] | None:
    if family == "scalar":
        rec = _scalar_to_variant(candidate)
        if rec is None:
            return None
    else:
        if not isinstance(candidate.get("path"), str) or not isinstance(candidate.get("content_utf8"), str):
            return None
        rec = dict(candidate)
    rec["source_family"] = family
    return rec


def _candidate_score(family: str, candidate: dict[str, Any], *, focused: bool) -> int:
    score = FAMILY_WEIGHTS[family]
    if focused:
        score += 200
    detail = candidate.get("detail") or {}
    mode = str(detail.get("mode") or "")
    if "coordinated" in mode:
        score += 35
    site_count = detail.get("site_count")
    if isinstance(site_count, int) and site_count > 1:
        score += min(30, site_count * 5)
    if family == "java_test_switch":
        score += 15
    return score


def _family_candidates(
    root: Path,
    *,
    include_prefixes: Sequence[str],
    focus_paths: Sequence[str],
    per_family_budget: int,
) -> tuple[list[tuple[str, dict[str, Any], int]], dict[str, Any]]:
    effective = _effective_prefixes(root, include_prefixes, focus_paths)
    focus_set = set(_normalize_paths(root, focus_paths))
    gathered: list[tuple[str, dict[str, Any], int]] = []
    meta: dict[str, Any] = {}

    for family, generator in FAMILIES:
        family_budget = min(per_family_budget, FAMILY_LIMITS[family])
        result = generator(
            root,
            include_prefixes=effective,
            max_candidates=family_budget,
        )
        raw = result.get("candidates") or []
        accepted = 0
        for candidate in raw:
            if not isinstance(candidate, dict):
                continue
            rec = _normalize_candidate(candidate, family)
            if rec is None:
                continue
            path = str(rec["path"])
            if focus_set and path not in focus_set:
                continue
            score = _candidate_score(family, rec, focused=path in focus_set)
            gathered.append((family, rec, score))
            accepted += 1
        meta[family] = {
            "generated": len(raw),
            "accepted": accepted,
            "activated": accepted > 0,
        }

    return gathered, meta


def _build_plans(
    root: Path,
    records: Sequence[tuple[str, dict[str, Any], int]],
) -> tuple[list[RepairPlan], dict[str, str]]:
    cache: dict[str, str] = {}
    plans: list[RepairPlan] = []
    seen: set[tuple[str, str]] = set()

    for _family, candidate, score in records:
        path = str(candidate["path"])
        original = _original_text(root, path, cache)
        if original is None:
            continue
        expected = str(candidate.get("expected_sha256") or "")
        if expected and expected != _sha(original):
            continue
        plan = plan_from_candidate(path=path, original=original, candidate=candidate, score=score)
        if plan is None:
            continue
        rendered = render_candidate(original, plan)
        key = (path, _sha(str(rendered["content_utf8"])))
        if key in seen:
            continue
        seen.add(key)
        plans.append(plan)

    return plans, cache


def _compose_plans(
    atomic: Sequence[RepairPlan],
    *,
    max_compositions: int,
    max_atomic_per_path: int,
) -> list[RepairPlan]:
    grouped: dict[str, list[RepairPlan]] = defaultdict(list)
    for plan in atomic:
        grouped[plan.path].append(plan)

    composed: list[RepairPlan] = []
    seen: set[str] = set()
    for path in sorted(grouped):
        items = sorted(
            grouped[path],
            key=lambda p: (-p.score, p.digest),
        )[:max_atomic_per_path]
        for i, left in enumerate(items):
            for right in items[i + 1 :]:
                plan = compose(left, right)
                if plan is None:
                    continue
                # Favor compositions that add a distinct capability or join
                # separate edits from the same abstract operator.
                if set(left.component_operators) != set(right.component_operators):
                    plan = RepairPlan(
                        path=plan.path,
                        expected_sha256=plan.expected_sha256,
                        edits=plan.edits,
                        component_ids=plan.component_ids,
                        component_operators=plan.component_operators,
                        depth=plan.depth,
                        score=plan.score + 20,
                    )
                if plan.digest in seen:
                    continue
                seen.add(plan.digest)
                composed.append(plan)
                if len(composed) >= max_compositions:
                    return composed
    return composed


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    focus_paths: Sequence[str] = (),
    max_candidates: int = 10_000,
    per_family_budget: int | None = None,
    composition_fraction: float = 0.40,
    max_atomic_per_path: int = 72,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    if not (0.0 <= composition_fraction <= 0.8):
        raise ValueError("composition_fraction must be in [0.0, 0.8]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    family_budget = per_family_budget or min(128, max_candidates)
    records, family_meta = _family_candidates(
        base,
        include_prefixes=include_prefixes,
        focus_paths=focus_paths,
        per_family_budget=family_budget,
    )
    atomic, originals = _build_plans(base, records)

    # Reserve an explicit part of the budget for composition.  Atomic
    # candidates remain represented because they are the strongest ablation.
    composition_budget = min(
        int(max_candidates * composition_fraction),
        max(0, max_candidates - 1),
    )
    composed = _compose_plans(
        atomic,
        max_compositions=composition_budget,
        max_atomic_per_path=max_atomic_per_path,
    )

    all_plans = [*atomic, *composed]
    all_plans.sort(
        key=lambda p: (
            -p.score,
            -int(p.depth > 1),
            p.depth,
            p.path,
            p.digest,
        )
    )

    out: list[dict[str, Any]] = []
    seen_contents: set[tuple[str, str]] = set()
    atomic_count = 0
    composed_count = 0
    for plan in all_plans:
        original = originals.get(plan.path)
        if original is None:
            original = _original_text(base, plan.path, originals)
        if original is None:
            continue
        candidate = render_candidate(original, plan, logical_index=len(out))
        key = (plan.path, _sha(str(candidate["content_utf8"])))
        if key in seen_contents:
            continue
        seen_contents.add(key)
        out.append(candidate)
        if plan.depth > 1:
            composed_count += 1
        else:
            atomic_count += 1
        if len(out) >= max_candidates:
            break

    normalized_focus = list(_normalize_paths(base, focus_paths))
    payload = {
        "schema": SCHEMA,
        "candidate_count": len(out),
        "atomic_candidate_count": atomic_count,
        "composed_candidate_count": composed_count,
        "focus_paths": normalized_focus,
        "causal_routing_enabled": bool(normalized_focus),
        "composition_enabled": composition_fraction > 0,
        "max_plan_depth": max((c["plan"]["depth"] for c in out), default=0),
        "family_activation": family_meta,
        "training_boundary": "ER1-J1-through-J10-consumed-evidence",
        "qualification_boundary": "future ER1-J11-plus cases unseen until machinery freeze",
        "external_model_calls": 0,
        "candidates": out,
    }
    without_candidates = {k: v for k, v in payload.items() if k != "candidates"}
    return {
        **payload,
        "strategy_digest": digest_of(without_candidates),
    }
