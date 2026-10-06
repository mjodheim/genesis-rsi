"""Evidence-backed internal failure attribution for Genesis G3.

The model never inspects a hidden solution.  It combines observable scheduler,
retrieval, language-substrate, toolchain and evaluator evidence to decide which
part of Genesis is the best next intervention target.

This is DEVELOPMENT apparatus.  Scores are explicit deterministic heuristics,
not learned probabilities, and "underdetermined" is a first-class outcome.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis.languages import substrate, toolchains
from genesis.trust_root import digest_of

FAILURE_MODEL_SCHEMA = "genesis-failure-model-v1"

_CLASSES = (
    "knowledge",
    "representation",
    "operator",
    "search",
    "retrieval",
    "toolchain",
    "planner",
    "evaluation",
    "unknown",
)

_INTERVENTIONS = {
    "knowledge": [
        "retrieve_versioned_documentation",
        "inspect_dependency_and_api_contracts",
    ],
    "representation": [
        "upgrade_language_representation",
        "add_or_improve_parser_symbol_type_adapter",
    ],
    "operator": [
        "acquire_or_synthesize_new_operator",
        "test_operator_on_fresh_matched_contexts",
    ],
    "search": [
        "change_search_strategy_or_decomposition",
        "compare_same_budget_search_variants",
    ],
    "retrieval": [
        "repair_memory_index_or_applicability_matching",
        "ablate_retrieval_policy",
    ],
    "toolchain": [
        "provision_or_select_native_toolchain",
        "do_not_spend_repair_budget_until_validation_is_available",
    ],
    "planner": [
        "change_candidate_allocation_or_scheduler_policy",
        "compare_planner_under_identical_candidate_budget",
    ],
    "evaluation": [
        "repair_or_disambiguate_evaluator",
        "freeze_evaluator_before_resuming_search",
    ],
    "unknown": [
        "collect_more_discriminating_evidence",
        "avoid_unjustified_self_modification",
    ],
    "underdetermined": [
        "run_discriminating_ablation_between_top_failure_classes",
        "avoid_committing_to_one_machinery_change_yet",
    ],
}


def _target_files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    result: list[Path] = []
    wanted = [str(item).strip("/") for item in prefixes if str(item).strip("/")]
    if not wanted:
        return result
    for raw in wanted:
        path = root / raw
        if path.is_file():
            result.append(path)
        elif path.is_dir():
            result.extend(item for item in path.rglob("*") if item.is_file())
    return sorted(set(result))


def _toolchain_by_language(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item.get("language")): item
        for item in list(report.get("packs") or [])
        if isinstance(item, Mapping)
    }


def diagnose(
    root: str | Path,
    autonomous_result: Mapping[str, Any],
    *,
    target_prefixes: Sequence[str] = (),
    toolchain_report: Mapping[str, Any] | None = None,
    retrieval_report: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Attribute an autonomous miss to the most evidenced internal limitation."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    schedule = dict(autonomous_result.get("schedule") or {})
    scheduled = int(schedule.get("scheduled_count", 0) or 0)
    charged = int(autonomous_result.get("charged_candidate_executions", 0) or 0)
    budget = int(autonomous_result.get("candidate_budget", 0) or 0)
    family_inputs = dict(schedule.get("family_input_counts") or {})
    family_scheduled = dict(schedule.get("family_scheduled_counts") or {})
    winner = autonomous_result.get("winner")

    scores = {name: 0 for name in _CLASSES}
    evidence: dict[str, list[str]] = {name: [] for name in _CLASSES}

    targets = _target_files(base, target_prefixes)
    supported_targets: list[dict[str, Any]] = []
    unsupported_paths: list[str] = []
    parse_failures: list[str] = []

    for path in targets:
        relative = path.relative_to(base).as_posix()
        language = substrate.language_for_path(relative)
        if language is None:
            unsupported_paths.append(relative)
            continue
        try:
            document = substrate.inspect_file(path, relative_path=relative)
        except (UnicodeDecodeError, ValueError):
            parse_failures.append(relative)
            continue
        supported_targets.append(document)
        if not bool(document.get("parse_ok")):
            parse_failures.append(relative)

    if unsupported_paths:
        scores["representation"] += 90
        evidence["representation"].append(
            f"{len(unsupported_paths)} target file(s) have no admitted language representation"
        )
    if parse_failures:
        scores["representation"] += 80
        evidence["representation"].append(
            f"{len(parse_failures)} target file(s) failed structural parsing"
        )

    tc_report = dict(toolchain_report or toolchains.capability_report(base))
    by_language = _toolchain_by_language(tc_report)
    missing_toolchain_languages: list[str] = []
    for language in sorted({str(item["language"]) for item in supported_targets}):
        record = by_language.get(language)
        if record is not None and not bool(record.get("core_ready")):
            missing_toolchain_languages.append(language)
    if missing_toolchain_languages:
        scores["toolchain"] += 95
        evidence["toolchain"].append(
            "native validation unavailable for " + ", ".join(missing_toolchain_languages)
        )

    evaluator_status = str(
        autonomous_result.get("evaluator_status")
        or autonomous_result.get("evaluation_status")
        or ""
    ).lower()
    if evaluator_status in {"ambiguous", "invalid", "error", "unavailable"}:
        scores["evaluation"] += 100
        evidence["evaluation"].append(f"evaluator status is {evaluator_status!r}")

    if bool(autonomous_result.get("missing_documentation")):
        scores["knowledge"] += 80
        evidence["knowledge"].append("run explicitly reports missing documentation")
    if bool(autonomous_result.get("unknown_api_contract")):
        scores["knowledge"] += 75
        evidence["knowledge"].append("run explicitly reports an unknown API contract")

    retained_inputs = int(family_inputs.get("retained", 0) or 0) + int(
        family_inputs.get("learned", 0) or 0
    )
    retained_scheduled = int(family_scheduled.get("retained", 0) or 0) + int(
        family_scheduled.get("learned", 0) or 0
    )
    retrieval = dict(retrieval_report or {})
    retrievable = int(
        retrieval.get("applicable_count", retrieval.get("retrieved_count", retained_inputs)) or 0
    )
    emitted = int(retrieval.get("emitted_count", retained_scheduled) or 0)

    if retrievable > 0 and emitted == 0:
        scores["retrieval"] += 90
        evidence["retrieval"].append(
            f"{retrievable} retained/applicable item(s) existed but none reached candidate emission"
        )
    if retained_inputs > 0 and scheduled == 0:
        scores["planner"] += 70
        evidence["planner"].append(
            "candidate families were available but scheduler emitted no candidate"
        )

    if winner is None:
        if (
            scheduled == 0
            and retrievable == 0
            and not unsupported_paths
            and not parse_failures
            and not missing_toolchain_languages
        ):
            scores["operator"] += 90
            evidence["operator"].append(
                "supported target and validation path existed but no candidate was representable"
            )

        if scheduled > 0 and charged >= scheduled and scheduled < max(1, budget):
            scores["operator"] += 80
            evidence["operator"].append(
                "entire representable candidate space was exhausted before the available budget"
            )

        if budget > 0 and charged >= budget and scheduled >= budget:
            scores["search"] += 90
            evidence["search"].append(
                "candidate budget was exhausted while candidate space remained available"
            )

        if scheduled > 0 and charged == 0:
            scores["planner"] += 75
            evidence["planner"].append(
                "candidates were scheduled but none reached charged execution"
            )
    else:
        scores["unknown"] = 100
        evidence["unknown"].append("a winner is present; no failure attribution is warranted")

    ranked = sorted(
        ((name, score) for name, score in scores.items() if name != "unknown"),
        key=lambda item: (-item[1], item[0]),
    )
    top_name, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if winner is not None:
        primary = "unknown"
        confidence = 1.0
    elif scores["evaluation"] >= 100:
        # An invalid/ambiguous evaluator is a hard blocker: downstream search,
        # retrieval or operator evidence cannot establish improvement until the
        # measurement boundary is trustworthy again.
        primary = "evaluation"
        confidence = 0.95
    elif top_score < 50:
        primary = "unknown"
        scores["unknown"] = max(scores["unknown"], 60)
        evidence["unknown"].append("observed evidence does not discriminate a failure class")
        confidence = 0.35
    elif second_score >= 50 and top_score - second_score < 15:
        primary = "underdetermined"
        confidence = round(min(0.7, top_score / 120), 3)
    else:
        primary = top_name
        confidence = round(min(0.95, top_score / 100), 3)

    payload = {
        "schema": FAILURE_MODEL_SCHEMA,
        "autonomous_report_digest": autonomous_result.get("report_digest"),
        "target_prefixes": list(target_prefixes),
        "supported_target_languages": sorted(
            {str(item["language"]) for item in supported_targets}
        ),
        "unsupported_target_paths": unsupported_paths,
        "parse_failure_paths": parse_failures,
        "missing_toolchain_languages": missing_toolchain_languages,
        "scores": scores,
        "evidence": {name: values for name, values in evidence.items() if values},
        "primary_failure_class": primary,
        "confidence": confidence,
        "recommended_interventions": list(_INTERVENTIONS[primary]),
        "solution_visible": False,
        "external_model_calls": 0,
    }
    return {**payload, "failure_model_digest": digest_of(payload)}
