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
from typing import Any, Callable, Mapping, Sequence

from genesis import (
    java_calendar_specialist,
    java_state_consistency_mutations,
    java_sibling_guard_mutations,
    java_stream_iterator_mutations,
    java_empty_segment_parser_mutations,
    java_default_normalization_mutations,
    java_expression_mutations,
    java_progress_mutations,
    java_range_mutations,
    java_structural_mutations,
    java_symbol_mutations,
    java_string_literal_mutations,
    java_test_switch_mutations,
    scalar_mutations,
    external_repair_learning,
)
from genesis.repair_ir import RepairPlan, compose, plan_from_candidate, render_candidate
from genesis.languages.understanding import ModuleRegistry
from genesis.languages.experience import ExperienceLedger
from genesis.insights.registry import InsightRegistry
from genesis.insights.hypotheses import hypotheses_for_candidates
from genesis.insights.compile_preflight import screen_candidates
from genesis.trust_root import digest_of

SCHEMA = "genesis-capability-routed-compositional-repair-v4"

# The weights encode only abstract ER1 lessons.  Narrow specialists receive a
# modest boost when they actually activate; they do not receive target IDs.
FAMILY_LIMITS: dict[str, int] = {
    "retained_structural": 96,
    "java_state_consistency": 64,
    "java_sibling_guard": 64,
    "java_stream_iterator": 64,
    "java_string_literal": 64,
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
    "retained_structural": 125,
    "java_state_consistency": 145,
    "java_sibling_guard": 140,
    "java_stream_iterator": 142,
    "java_string_literal": 118,
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
    ("java_state_consistency", java_state_consistency_mutations.generate),
    ("java_string_literal", java_string_literal_mutations.generate),
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
    retained_memory: Mapping[str, Any] | None = None,
    balance_sources: bool = False,
    enable_sibling_guard: bool = False,
    enable_stream_iterator: bool = False,
) -> tuple[list[tuple[str, dict[str, Any], int]], dict[str, Any]]:
    effective = _effective_prefixes(root, include_prefixes, focus_paths)
    focus_set = set(_normalize_paths(root, focus_paths))
    gathered: list[tuple[str, dict[str, Any], int]] = []
    meta: dict[str, Any] = {}

    def collect(generator, family_budget: int, *, retained: bool = False):
        def call(prefixes, budget):
            if retained:
                return external_repair_learning.retained_variants(
                    retained_memory, root,
                    include_prefixes=prefixes, max_candidates=budget,
                )
            return generator(root, include_prefixes=prefixes, max_candidates=budget)

        if balance_sources and len(focus_set) > 1:
            budget_per_file = max(1, (family_budget + len(focus_set) - 1) // len(focus_set))
            collected = []
            digest = ""
            for focus in sorted(focus_set):
                result = call((focus,), budget_per_file)
                collected.extend(result.get("candidates") or [])
                digest = str(result.get("memory_digest") or digest)
            return collected[:family_budget], digest
        result = call(effective, family_budget)
        return list(result.get("candidates") or []), str(result.get("memory_digest") or "")

    selected_families = (
        ((("java_sibling_guard", java_sibling_guard_mutations.generate),)
          if enable_sibling_guard else ())
        + ((("java_stream_iterator", java_stream_iterator_mutations.generate),)
           if enable_stream_iterator else ())
        + FAMILIES
    )
    for family, generator in selected_families:
        family_budget = min(per_family_budget, FAMILY_LIMITS[family])
        raw, _ = collect(generator, family_budget)
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

    if retained_memory is not None:
        family = "retained_structural"
        family_budget = min(per_family_budget, FAMILY_LIMITS[family])
        raw, memory_digest = collect(
            external_repair_learning.retained_variants, family_budget, retained=True,
        )
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
            "memory_digest": memory_digest,
        }
    else:
        meta["retained_structural"] = {
            "generated": 0,
            "accepted": 0,
            "activated": False,
            "memory_digest": "",
        }

    return gathered, meta



def _understanding_overlap(start: int, end: int, node: Mapping[str, Any]) -> bool:
    left = node.get("start")
    right = node.get("end")
    if not isinstance(left, int) or not isinstance(right, int):
        return False
    if start == end:
        return left <= start <= right
    return start < right and left < end


def _understanding_bonus(plan: RepairPlan, nodes: Sequence[Mapping[str, Any]]) -> int:
    """Conservative generic structural ranking prior; NOT a repair validator.

    Positional scores are only valid for ASCII files because javac offsets are
    UTF-16 while Python edit spans use codepoint offsets.
    """
    relevant = [
        node for node in nodes
        if any(_understanding_overlap(edit.start, edit.end, node) for edit in plan.edits)
    ]
    if not relevant:
        return 0
    kinds = {str(node.get("kind")) for node in relevant}
    bonus = 4 if "function_declaration" in kinds else 0
    if kinds.intersection({"if_control", "while_control", "for_control", "conditional_control"}):
        bonus += 6
    if any(node.get("type") for node in relevant):
        bonus += 3
    if any(node.get("symbol_id") for node in relevant):
        bonus += 2
    return min(15, bonus)


def _score_from_understanding(
    root: Path,
    atomic: Sequence[RepairPlan],
    *,
    registry: ModuleRegistry,
    ledger: ExperienceLedger | None,
    insight_registry: InsightRegistry | None,
    rerank: bool,
    max_files: int,
    focus_paths: Sequence[str],
) -> tuple[list[RepairPlan], dict[str, Any], dict[str, dict[str, Any]]]:
    """Analyze only buggy-side candidate paths and optionally log observations."""
    if max_files < 1 or max_files > 32:
        raise ValueError("max_understanding_files must be in [1, 32]")
    focus = set(_normalize_paths(root, focus_paths))
    paths = sorted({plan.path for plan in atomic}, key=lambda p: (p not in focus, p))
    reports: dict[str, dict[str, Any]] = {}
    metadata: list[dict[str, Any]] = []
    for relpath in paths[:max_files]:
        path = (root / relpath).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        try:
            report = registry.analyze(path)
            reports[relpath] = report
            if ledger is not None:
                ledger.record(report, operator="repair-planning-observation")
            diagnostic = (
                insight_registry.inspect(path, understanding=report, ledger=ledger)
                if insight_registry is not None else None
            )
            metadata.append({
                "path": relpath,
                "language": report["language"],
                "module_id": report["module_id"],
                "fidelity": report["fidelity"],
                "analysis_digest": report["analysis_digest"],
                "diagnostic_count": len(report["diagnostics"]),
                "features": report["features"],
                "domain_insight_digest": diagnostic["insight_digest"] if diagnostic else None,
                "domain_findings": diagnostic["findings"] if diagnostic else [],
                "domain_coverage": diagnostic["coverage_by_domain"] if diagnostic else None,
            })
        except Exception as exc:
            metadata.append({"path": relpath, "analysis_error": type(exc).__name__})
    adjusted: list[RepairPlan] = []
    total_bonus = 0
    potential_bonus = 0
    potential_plan_count = 0
    for plan in atomic:
        report = reports.get(plan.path)
        bonus = 0
        if report is not None:
            # Avoid lying about javac's UTF-16 offsets for non-ASCII source.
            original = _original_text(root, plan.path, {})
            if original is not None and original.isascii():
                bonus = _understanding_bonus(plan, report["nodes"])
        potential_bonus += bonus
        potential_plan_count += int(bonus > 0)
        applied_bonus = bonus if rerank else 0
        total_bonus += applied_bonus
        adjusted.append(RepairPlan(
            path=plan.path,
            expected_sha256=plan.expected_sha256,
            edits=plan.edits,
            component_ids=plan.component_ids,
            component_operators=plan.component_operators,
            depth=plan.depth,
            score=plan.score + applied_bonus,
        ))
    metadata_payload = {
        "schema": "genesis-g11-planner-analysis-v1",
        "analyzed_file_count": len(reports),
        "selected_file_count": min(len(paths), max_files),
        "adjusted_atomic_plan_count": sum(a.score != b.score for a, b in zip(atomic, adjusted)),
        "total_structural_score_bonus": total_bonus,
        "experimental_reranking_enabled": rerank,
        "potential_bonus_without_application": potential_bonus,
        "potential_plan_count": potential_plan_count,
        "reports": metadata,
        "ledger_recording_enabled": ledger is not None,
        "position_scoring_limited_to_ascii": True,
    }
    return adjusted, metadata_payload, reports


def _build_plans(
    root: Path,
    records: Sequence[tuple[str, dict[str, Any], int]],
) -> tuple[list[RepairPlan], dict[str, str]]:
    cache: dict[str, str] = {}
    best_by_content: dict[tuple[str, str], RepairPlan] = {}

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
        previous = best_by_content.get(key)
        if previous is None or (-plan.score, plan.digest) < (-previous.score, previous.digest):
            best_by_content[key] = plan

    plans = [
        best_by_content[key]
        for key in sorted(best_by_content, key=lambda item: (item[0], item[1]))
    ]
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
    retained_memory: Mapping[str, Any] | None = None,
    understanding_registry: ModuleRegistry | None = None,
    understanding_ledger: ExperienceLedger | None = None,
    insight_registry: InsightRegistry | None = None,
    understanding_rerank: bool = False,
    understanding_hypotheses: bool = False,
    source_balance_experimental: bool = False,
    compile_preflight_javac: Path | None = None,
    compile_preflight_classpath: Sequence[str] = (),
    max_compile_preflight_candidates: int = 80,
    atomic_first_experimental: bool = False,
    priority_focus_paths: Sequence[str] = (),
    sibling_guard_experimental: bool = False,
    stream_iterator_experimental: bool = False,
    g12_retained_probe_slots: int = 0,
    max_understanding_files: int = 4,
) -> dict[str, Any]:
    if understanding_ledger is not None and understanding_registry is None:
        raise ValueError("experience ledger requires an enabled understanding registry")
    if insight_registry is not None and understanding_registry is None:
        raise ValueError("domain insights require an enabled understanding registry")
    if understanding_rerank and understanding_registry is None:
        raise ValueError("experimental reranking requires an understanding registry")
    if understanding_hypotheses and understanding_registry is None:
        raise ValueError("repair hypotheses require an understanding registry")
    if source_balance_experimental and len(_normalize_paths(Path(root).resolve(), focus_paths)) > 32:
        raise ValueError("source balancing is bounded to 32 focus files")
    if isinstance(g12_retained_probe_slots, bool) or not 0 <= g12_retained_probe_slots <= 4:
        raise ValueError("G12 retained probe slots must be in [0,4]")
    if g12_retained_probe_slots and retained_memory is None:
        raise ValueError("G12 retained probe slots require retained training memory")
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
        retained_memory=retained_memory,
        balance_sources=source_balance_experimental,
        enable_sibling_guard=sibling_guard_experimental,
        enable_stream_iterator=stream_iterator_experimental,
    )
    if g12_retained_probe_slots:
        # Without this opt-in, identical candidate content produced by the
        # human-authored family wins the deduplication score and ERASES the
        # learner's provenance. Give replay-validated retained edits a
        # provisional score advantage solely for bounded exploration.
        records = [
            (family, rec, score + 250 if family == "retained_structural" else score)
            for family, rec, score in records
        ]
    atomic, originals = _build_plans(base, records)
    understanding_summary = None
    understanding_reports: dict[str, dict[str, Any]] = {}
    if understanding_registry is not None:
        atomic, understanding_summary, understanding_reports = _score_from_understanding(
            base, atomic,
            registry=understanding_registry,
            ledger=understanding_ledger,
            insight_registry=insight_registry,
            rerank=understanding_rerank,
            max_files=max_understanding_files,
            focus_paths=focus_paths,
        )

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
    # Default remains unchanged for existing frozen evaluations. In the
    # experimental atomic frontier, reversible single-step edits precede
    # risky compositions, so a good atomic patch is not buried under dozens
    # of high-scoring but invalid unrelated two-edit variants.
    all_plans.sort(
        key=lambda p: (
            int(p.depth > 1) if atomic_first_experimental else 0,
            -p.score,
            -int(p.depth > 1),
            p.depth,
            p.path,
            p.digest,
        )
    )
    if source_balance_experimental and focus_paths:
        from collections import deque
        groups: dict[str, deque[RepairPlan]] = {}
        for plan in all_plans:
            groups.setdefault(plan.path, deque()).append(plan)
        rotated: list[RepairPlan] = []
        priority_order: dict[str, int] = {}
        for candidate in priority_focus_paths:
            path = str(candidate).replace("\\", "/").strip("/")
            if path in groups and path not in priority_order:
                priority_order[path] = len(priority_order)
        active = deque(sorted(
            groups,
            key=lambda p: (p not in priority_order, priority_order.get(p, 10**6), p),
        ))
        while active:
            path = active.popleft()
            rotated.append(groups[path].popleft())
            if groups[path]:
                active.append(path)
        all_plans = rotated

    selected_retained_probes = 0
    if g12_retained_probe_slots:
        reserved: list[RepairPlan] = []
        for plan in all_plans:
            if (plan.depth == 1
                    and "retained_structural_operator" in plan.component_operators
                    and len(reserved) < min(g12_retained_probe_slots, max_candidates)):
                reserved.append(plan)
        if reserved:
            chosen = {p.digest for p in reserved}
            all_plans = [*reserved, *(p for p in all_plans if p.digest not in chosen)]
        selected_retained_probes = len(reserved)

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

    preflight_summary = None
    if compile_preflight_javac is not None:
        # Experimental compiler-only source validity screening. No oracle is
        # consulted; compile failures are never mislabeled behavioral failures.
        out, preflight_summary = screen_candidates(
            base, out, javac=compile_preflight_javac,
            classpath=compile_preflight_classpath,
            max_candidates=min(max_compile_preflight_candidates, len(out)),
        ) if out else (out, None)
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
        "training_boundary": "ER1-J1-through-J11-consumed-evidence; J12 positive held out from training",
        "qualification_boundary": "future ER1-J13-plus cases unseen until machinery freeze",
        "external_model_calls": 0,
        "candidates": out,
    }
    if g12_retained_probe_slots:
        payload["g12_retained_probe"] = {
            "schema": "genesis-g12-retained-exploration-v1",
            "requested_slots": g12_retained_probe_slots,
            "selected_slots": selected_retained_probes,
            "training_memory_digest": retained_memory["memory_digest"],
            "promotion_does_not_prove_repair": True,
            "opt_in_only": True,
        }
    if preflight_summary is not None:
        payload["g11_compile_preflight"] = preflight_summary
    if atomic_first_experimental:
        payload["g11_atomic_first_experimental"] = True
    if sibling_guard_experimental:
        payload["g11_sibling_guard_experimental"] = True
    if stream_iterator_experimental:
        payload["g11_stream_iterator_experimental"] = True
    if priority_focus_paths:
        payload["g11_priority_focus_paths"] = list(_normalize_paths(base, priority_focus_paths))
    if source_balance_experimental:
        from collections import Counter
        payload["source_balance_experimental"] = True
        payload["selected_candidate_paths"] = dict(sorted(Counter(c["path"] for c in out).items()))
    if understanding_summary is not None:
        if understanding_hypotheses:
            # Hypotheses run AFTER ranking. They never alter candidate selection.
            understanding_summary["repair_hypotheses"] = hypotheses_for_candidates(
                root=base, reports=understanding_reports,
                candidates=out, max_candidates=min(24, max_candidates),
            )
        payload["g11_understanding"] = understanding_summary
    # Keep the disabled path bit-for-bit backward compatible with v4.
    without_candidates = {k: v for k, v in payload.items() if k != "candidates"}
    return {**payload, "strategy_digest": digest_of(without_candidates)}
