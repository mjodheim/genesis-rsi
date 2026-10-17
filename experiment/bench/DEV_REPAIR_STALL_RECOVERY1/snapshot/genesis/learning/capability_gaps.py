"""Deterministic capability-gap diagnosis for A6c / Genesis G3.

This module does not propose a repair.  It classifies *why* the frozen
autonomous search could not express or reach one, so the post-outcome
acquisition layer knows whether a new operator class is warranted.

The legacy A6c reasons are preserved for compatibility.  Genesis G3 adds a
richer internal failure-model record so later machinery changes can target the
limiting component instead of collapsing everything into "expressivity or
search".
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis import patch_templates, scalar_mutations
from genesis.learning import failure_model
from genesis.trust_root import digest_of

GAP_SCHEMA = "genesis-capability-gap-diagnosis-v1"


def _target_suffixes(root: Path, prefixes: Sequence[str]) -> list[str]:
    suffixes: set[str] = set()
    for raw in prefixes:
        normalized = str(raw).strip("/")
        if not normalized:
            continue
        path = root / normalized
        if path.is_file():
            suffixes.add(path.suffix.lower())
            continue
        if path.is_dir():
            for item in path.rglob("*"):
                if item.is_file():
                    suffixes.add(item.suffix.lower())
    return sorted(suffixes)


def diagnose(
    root: str | Path,
    autonomous_result: Mapping[str, Any],
    *,
    target_prefixes: Sequence[str] = (),
) -> dict[str, Any]:
    """Classify a failed autonomous run without looking at any solution."""
    base = Path(root).resolve()
    schedule = dict(autonomous_result.get("schedule") or {})
    scheduled = int(schedule.get("scheduled_count", 0))
    charged = int(autonomous_result.get("charged_candidate_executions", 0))
    budget = int(autonomous_result.get("candidate_budget", 0) or 0)
    family_inputs = dict(schedule.get("family_input_counts") or {})
    family_scheduled = dict(schedule.get("family_scheduled_counts") or {})
    winner = autonomous_result.get("winner")

    suffixes = _target_suffixes(base, target_prefixes)
    scalar_supported = set(scalar_mutations.SUPPORTED_SUFFIXES)
    line_supported = set(getattr(patch_templates, "_SUPPORTED_SUFFIXES", ()))
    unsupported_by_legacy = [
        suffix for suffix in suffixes
        if suffix and suffix not in scalar_supported and suffix not in line_supported
    ]

    reasons: list[str] = []
    if winner is not None:
        reasons.append("no_gap_winner_present")
    else:
        if scheduled == 0:
            reasons.append("no_candidate_generated")
        if unsupported_by_legacy:
            reasons.append("legacy_generator_text_kind_gap")
        if scheduled > 0 and charged >= scheduled and scheduled < max(1, budget):
            reasons.append("candidate_space_exhausted_before_budget")
        if budget > 0 and charged >= budget:
            reasons.append("budget_exhausted_without_passing_candidate")
        if int(family_inputs.get("learned", 0)) == 0 and int(family_inputs.get("retained", 0)) == 0:
            reasons.append("no_applicable_retained_transformation")
        if scheduled > 0 and not unsupported_by_legacy:
            reasons.append("expressivity_or_search_gap")

    internal_failure = failure_model.diagnose(
        base,
        autonomous_result,
        target_prefixes=target_prefixes,
    )
    primary_failure = str(internal_failure.get("primary_failure_class", "unknown"))

    acquisition_recommended = winner is None and any(
        reason in reasons
        for reason in (
            "no_candidate_generated",
            "legacy_generator_text_kind_gap",
            "candidate_space_exhausted_before_budget",
            "budget_exhausted_without_passing_candidate",
            "expressivity_or_search_gap",
        )
    ) and primary_failure not in {"toolchain", "evaluation", "retrieval", "planner"}

    recommended_mode = "none"
    if acquisition_recommended:
        if primary_failure == "search":
            recommended_mode = "change_search_before_learning_new_operator"
        elif primary_failure == "representation":
            recommended_mode = "extend_representation_then_synthesize_operator"
        else:
            recommended_mode = (
                "synthesize_replay_verified_structural_operator_from_next_passing_outcome"
            )

    payload = {
        "schema": GAP_SCHEMA,
        "autonomous_report_digest": autonomous_result.get("report_digest"),
        "target_prefixes": list(target_prefixes),
        "target_suffixes": suffixes,
        "legacy_unsupported_suffixes": unsupported_by_legacy,
        "scheduled_count": scheduled,
        "charged_candidate_executions": charged,
        "candidate_budget": budget,
        "family_input_counts": family_inputs,
        "family_scheduled_counts": family_scheduled,
        "reasons": reasons,
        "failure_model": internal_failure,
        "primary_failure_class": primary_failure,
        "operator_acquisition_recommended": acquisition_recommended,
        "recommended_mode": recommended_mode,
        "external_model_calls": 0,
    }
    return {**payload, "diagnosis_digest": digest_of(payload)}
