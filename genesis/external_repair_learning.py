"""Trusted helpers for autonomous external-repair learning.

This module bridges a frozen blind campaign result to Genesis' existing
failure-driven self-extension memory.  It enforces the causal order:

blind miss -> retain diagnosis -> reveal validated solution -> acquire operator

The helpers never decide whether a repair is correct; the external evaluator
and the trusted campaign orchestrator remain authoritative.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis import failure_driven_self_extension as self_extension
from genesis.trust_root import digest_of

SCHEMA = "genesis-external-repair-learning-v1"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_prefixes(prefixes: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(x).replace("\\", "/").strip("/") for x in prefixes if str(x).strip("/")}))


def _in_scope(relative: str, prefixes: Sequence[str]) -> bool:
    wanted = _normalize_prefixes(prefixes)
    return not wanted or any(relative == p or relative.startswith(p + "/") for p in wanted)


def solution_candidate_from_roots(
    buggy_root: str | Path,
    fixed_root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a candidate from a sealed fixed checkout after reveal is permitted.

    Only changed files that already exist in both roots are included.  New or
    deleted files are reported as unsupported because the retained structural
    operator machinery currently learns edits to existing text files.
    """
    buggy = Path(buggy_root).resolve()
    fixed = Path(fixed_root).resolve()
    if not buggy.is_dir() or not fixed.is_dir():
        raise ValueError("buggy and fixed roots must exist")

    paths: set[str] = set()
    for root in (buggy, fixed):
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(part in {".git", "target", "build", "node_modules", "__pycache__"} for part in Path(rel).parts[:-1]):
                continue
            if _in_scope(rel, include_prefixes):
                paths.add(rel)

    mutations: list[dict[str, Any]] = []
    unsupported: list[dict[str, str]] = []
    for rel in sorted(paths):
        bp = buggy / rel
        fp = fixed / rel
        if not bp.exists() or not fp.exists():
            unsupported.append({"path": rel, "reason": "new_or_deleted_file"})
            continue
        try:
            before = bp.read_text(encoding="utf-8")
            after = fp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            unsupported.append({"path": rel, "reason": "non_utf8"})
            continue
        if before == after:
            continue
        mutations.append(
            {
                "path": rel,
                "expected_sha256": _sha(before),
                "expected_absent": False,
                "content_utf8": after,
            }
        )

    payload = {
        "schema": "genesis-revealed-solution-candidate-v1",
        "mutations": mutations,
        "unsupported": unsupported,
        "external_model_calls": 0,
    }
    return {**payload, "candidate_digest": digest_of(payload)}


def blind_result_for_gap(
    result: Mapping[str, Any],
    *,
    family_activation: Mapping[str, Mapping[str, Any]] | None = None,
    candidate_budget: int = 10_000,
) -> dict[str, Any]:
    """Translate an ER-style result into the self-extension diagnosis envelope."""
    activation = dict(family_activation or {})
    family_inputs = {
        name: int(dict(meta).get("accepted", dict(meta).get("generated", 0)) or 0)
        for name, meta in activation.items()
    }
    evaluated = int(result.get("evaluated_count", 0) or 0)
    # Coverage-pruned candidates still consume a frozen logical candidate slot.
    # Treat the full evaluated count as charged search budget; otherwise a
    # causally focused evaluator can be misdiagnosed as a toolchain failure.
    charged = evaluated
    winner = result.get("winner")
    schedule = {
        "scheduled_count": evaluated,
        "family_input_counts": {
            "learned": int(family_inputs.get("retained_structural", 0)),
            "retained": int(family_inputs.get("retained_structural", 0)),
            **family_inputs,
        },
        "family_scheduled_counts": family_inputs,
    }
    payload = {
        "candidate_budget": int(candidate_budget),
        "charged_candidate_executions": charged,
        "winner": winner,
        "autonomous_passed": winner is not None,
        "schedule": schedule,
        "source_result_digest": str(result.get("shared_result_sha256") or result.get("result_sha256") or result.get("result_digest") or ""),
    }
    return {**payload, "report_digest": digest_of(payload)}


def diagnose_and_retain(
    memory: Mapping[str, Any],
    root: str | Path,
    blind_result: Mapping[str, Any],
    *,
    target_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """Diagnose a frozen miss and persist the gap before any solution reveal."""
    if blind_result.get("winner") is not None or bool(blind_result.get("autonomous_passed")):
        raise ValueError("diagnose_and_retain requires a blind miss")
    diagnosis = self_extension.diagnose_failure(
        root,
        blind_result,
        target_prefixes=target_prefixes,
    )
    retained = self_extension.retain_gap(memory, diagnosis)
    payload = {
        "schema": SCHEMA,
        "phase": "gap_retained_pre_reveal",
        "diagnosis": diagnosis,
        "memory": retained,
        "solution_visible": False,
        "external_model_calls": 0,
    }
    return {**payload, "learning_digest": digest_of(payload)}


def acquire_from_revealed_solution(
    retained_memory: Mapping[str, Any],
    buggy_root: str | Path,
    fixed_root: str | Path,
    *,
    diagnosis: Mapping[str, Any],
    passing_result_digest: str,
    target_prefixes: Sequence[str] = (),
    context_lines: int = 1,
) -> dict[str, Any]:
    """Acquire replay-verified capability after the trusted reveal gate opens."""
    candidate = solution_candidate_from_roots(
        buggy_root,
        fixed_root,
        include_prefixes=target_prefixes,
    )
    if not candidate["mutations"]:
        raise ValueError("revealed solution contains no supported changed source file")
    learned = self_extension.acquire_from_passing_candidate(
        retained_memory,
        buggy_root,
        candidate,
        diagnosis=diagnosis,
        passing_result_digest=passing_result_digest,
        context_lines=context_lines,
    )
    payload = {
        "schema": SCHEMA,
        "phase": "operator_acquired_post_reveal",
        "solution_candidate_digest": candidate["candidate_digest"],
        "added_operator_digests": list(learned["added_operator_digests"]),
        "memory": learned["memory"],
        "acquisition": learned["acquisition"],
        "external_model_calls": 0,
    }
    return {**payload, "learning_digest": digest_of(payload)}


def retained_variants(
    memory: Mapping[str, Any],
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 96,
) -> dict[str, Any]:
    """Expose retained structural operators as repair-strategist variants."""
    reuse = self_extension.generate_candidates(
        memory,
        root,
        include_prefixes=include_prefixes,
        max_candidates=max_candidates,
    )
    variants: list[dict[str, Any]] = []
    for raw in reuse["candidate_set"]["candidates"]:
        mutations = list(raw.get("mutations") or [])
        if len(mutations) != 1:
            continue
        mutation = dict(mutations[0])
        variants.append(
            {
                "id": raw.get("id"),
                "candidate_digest": raw.get("candidate_digest"),
                "path": mutation.get("path"),
                "operator": "retained_structural_operator",
                "expected_sha256": mutation.get("expected_sha256"),
                "content_utf8": mutation.get("content_utf8"),
                "detail": {
                    "strategy_origin": "replay_verified_retained_operator",
                    "operator_digest": dict(raw.get("provenance") or {}).get("operator_digest"),
                },
                "external_model_calls": 0,
            }
        )
    payload = {
        "schema": "genesis-retained-repair-variants-v1",
        "memory_digest": reuse["memory_digest"],
        "candidate_count": len(variants),
        "external_model_calls": 0,
        "candidates": variants,
    }
    return {**payload, "set_digest": digest_of({k: v for k, v in payload.items() if k != "candidates"})}
