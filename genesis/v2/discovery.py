"""Genesis V2: immutable judge plus evolvable candidate-selection controller.

The mutable policy can ONLY assign bounded scores to public, pre-evaluation
features. Proposals are self-generated from a finite genome mutation grammar.
The judge, candidate outcomes, comparison budgets and adoption rule are kept
outside that grammar.

Historical replay is engineering development, NEVER a blinded benchmark or
evidence of autonomous repair on a new case.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genesis.trust_root import digest_of
from genesis.v2.genome import (
    FEATURES, GenomeError, make_seed, mutate, neighborhood, rank, validate_genome,
)
from genesis.v2.traces import TraceError, validate_catalogue

SCHEMA = "genesis-v2-retrospective-discovery-v1"


class DiscoveryError(ValueError):
    pass


def _valid_cases(cases: Sequence[Mapping[str, Any]], top_k: int) -> None:
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 12:
        raise DiscoveryError("candidate budget must be in [1,12]")
    if not cases or len(cases) > 50:
        raise DiscoveryError("at least one bounded case required")
    if any(case.get("candidate_count", 0) < top_k for case in cases):
        raise DiscoveryError("equal-budget comparison requires enough tested candidates")


def select(genome: Mapping[str, Any], case: Mapping[str, Any], top_k: int) -> list[str]:
    """Policy only observes source features, NEVER success/failure labels."""
    valid = validate_genome(genome)
    if not 1 <= top_k <= len(case["candidates"]):
        raise DiscoveryError("invalid number of candidate selections")
    # Stable original index breaks ties to reproduce legacy candidate ordering.
    ranking = sorted(
        enumerate(case["candidates"]),
        key=lambda pair: (-rank(valid, pair[1]["features"]), pair[0]),
    )
    return [candidate["id"] for _, candidate in ranking[:top_k]]


def _measure(
    genome: Mapping[str, Any], cases: Sequence[Mapping[str, Any]], top_k: int
) -> dict[str, Any]:
    """Trusted judge: full-suite successes primary, compilations secondary."""
    _valid_cases(cases, top_k)
    valid = validate_genome(genome)
    individual = []
    for case in cases:
        selected = set(select(valid, case, top_k))
        observed = [c for c in case["candidates"] if c["id"] in selected]
        if len(observed) != top_k:
            raise DiscoveryError("candidate IDs are ambiguous")
        passes = sum(c["full_suite_pass"] for c in observed)
        compile_passes = sum(c["compiled"] for c in observed)
        individual.append({
            "case_id": case["case_id"],
            "evaluated": top_k,
            "full_suite_valid": passes,
            "compiled": compile_passes,
            "has_full_suite_success": passes > 0,
            "selected_candidate_digest": digest_of(sorted(selected)),
        })
    metric = {
        "case_count": len(individual),
        "candidates_per_case": top_k,
        "test_budget": len(individual) * top_k,
        "projects_with_full_suite_success": sum(r["has_full_suite_success"] for r in individual),
        "full_suite_valid_candidates": sum(r["full_suite_valid"] for r in individual),
        "compile_valid_candidates": sum(r["compiled"] for r in individual),
        "individual": individual,
    }
    return {**metric, "measurement_digest": digest_of(metric)}


def _fitness(measurement: Mapping[str, Any]) -> tuple[int, int, int]:
    return (
        measurement["projects_with_full_suite_success"],
        measurement["full_suite_valid_candidates"],
        measurement["compile_valid_candidates"],
    )


def evolve_in_training(
    *,
    parent: Mapping[str, Any],
    training_cases: Sequence[Mapping[str, Any]],
    top_k: int,
    max_generations: int = 2,
) -> dict[str, Any]:
    """Train ONLY on supplied development cases; validation cases stay outside.

    2 generations bound search cost (max 20 tested descendants). No operator
    uses the training results as a feature, and no candidate is executed.
    """
    if (isinstance(max_generations, bool) or not isinstance(max_generations, int)
            or not 1 <= max_generations <= 5):
        raise DiscoveryError("max generations must be in [1,5]")
    _valid_cases(training_cases, top_k)
    champion = validate_genome(parent)
    parent_measurement = _measure(champion, training_cases, top_k)
    current = parent_measurement
    lineage = []
    for _ in range(max_generations):
        candidates = neighborhood(champion)
        proposals = []
        champion_score = _fitness(current)
        for genome in candidates:
            measure = _measure(genome, training_cases, top_k)
            proposals.append({
                "genome": genome,
                "measurement": measure,
                "strict_training_improvement": _fitness(measure) > champion_score,
            })
        improved = [p for p in proposals if p["strict_training_improvement"]]
        # Fixed tie breaking. Never let a val-set observation enter selection.
        selected = sorted(
            improved,
            key=lambda p: (
                tuple(-score for score in _fitness(p["measurement"])),
                p["genome"]["genome_digest"],
            )
        )[0] if improved else None
        body = {
            "generation_from": champion["generation"],
            "parent_genome_digest": champion["genome_digest"],
            "proposal_count": len(proposals),
            "candidate_proposals": [{
                "genome_digest": p["genome"]["genome_digest"],
                "mutation": p["genome"]["mutation"],
                "training_measurement_digest": p["measurement"]["measurement_digest"],
                "training_fitness": list(_fitness(p["measurement"])),
            } for p in proposals],
            "chosen_genome_digest": selected["genome"]["genome_digest"] if selected else None,
            "mechanism": "finite_self_proposed_genome_mutations",
            "evaluation_scope": "released_development_training",
        }
        lineage.append({**body, "search_step_digest": digest_of(body)})
        if selected is None:
            break
        champion = selected["genome"]
        current = selected["measurement"]
    result = {
        "seed_genome": dict(parent),
        "seed_training_measurement": parent_measurement,
        "learned_genome": champion,
        "learned_training_measurement": current,
        "search_steps": lineage,
        "total_mutants_considered": sum(step["proposal_count"] for step in lineage),
        "training_only": True,
    }
    return {**result, "training_search_digest": digest_of(result)}


def retrospective_study(
    catalogue: Mapping[str, Any],
    *,
    training_case_ids: Sequence[str],
    development_check_case_ids: Sequence[str],
    top_k: int = 8,
    max_generations: int = 2,
) -> dict[str, Any]:
    """Train, freeze champion, *then* inspect a separate development check set.

    Both partitions come from exposed projects: *neither* is a new holdout.
    Any real deployment would require an external independent authority and
    new preregistration. This method cannot adopt or deploy changes.
    """
    cat = validate_catalogue(catalogue)
    training_ids = list(training_case_ids)
    check_ids = list(development_check_case_ids)
    ids = {c["case_id"]: c for c in cat["cases"]}
    if (not training_ids or not check_ids
            or len(set(training_ids)) != len(training_ids)
            or len(set(check_ids)) != len(check_ids)
            or set(training_ids) & set(check_ids)
            or set(training_ids) | set(check_ids) != set(ids)):
        raise DiscoveryError("train/check must partition all released cases without overlap")
    train = [ids[i] for i in training_ids]
    check = [ids[i] for i in check_ids]
    seed = make_seed()
    train_outcome = evolve_in_training(
        parent=seed, training_cases=train, top_k=top_k,
        max_generations=max_generations,
    )
    descendant = train_outcome["learned_genome"]
    # Crucially, the dev-check set was not consulted during genome selection.
    baseline_check = _measure(seed, check, top_k)
    descendant_check = _measure(descendant, check, top_k)
    # A development-only diagnostic. We refuse *real promotion* regardless
    # of a positive outcome here; the cases are already publicly exposed.
    body = {
        "schema": SCHEMA,
        "catalogue_digest": cat["catalogue_digest"],
        "training_cases": training_ids,
        "development_check_cases": check_ids,
        "top_k_each_case": top_k,
        "max_generations": max_generations,
        "training_search": train_outcome,
        "baseline_check": baseline_check,
        "descendant_check": descendant_check,
        "development_compilation_gain": (
            descendant_check["compile_valid_candidates"]
            - baseline_check["compile_valid_candidates"]
        ),
        "development_full_suite_gain": (
            descendant_check["projects_with_full_suite_success"]
            - baseline_check["projects_with_full_suite_success"]
        ),
        "decision": "never_promote_from_exposed_data",
        "production_genome_unchanged": True,
        "fresh_unseen_repair_claims": 0,
        "self_discovered_semantic_repair_operators": 0,
        "mutable_genome_can_access_evaluator": False,
        "budget_and_outcomes_owned_by_immutable_judge": True,
        "no_new_program_executions": True,
    }
    return {**body, "study_digest": digest_of(body)}


def validate_study(report: Mapping[str, Any]) -> dict[str, Any]:
    if report.get("schema") != SCHEMA:
        raise DiscoveryError("unsupported V2 study")
    body = {k:v for k,v in report.items() if k != "study_digest"}
    if report.get("study_digest") != digest_of(body):
        raise DiscoveryError("study digest invalid")
    if (report.get("decision") != "never_promote_from_exposed_data"
            or report.get("production_genome_unchanged") is not True
            or report.get("fresh_unseen_repair_claims") != 0
            or report.get("mutable_genome_can_access_evaluator") is not False):
        raise DiscoveryError("inconsistent scientific boundary")
    training = report["training_search"]
    unsigned_training = {k:v for k,v in training.items()
                         if k != "training_search_digest"}
    if training.get("training_search_digest") != digest_of(unsigned_training):
        raise DiscoveryError("training search digest invalid")
    for key in ("seed_training_measurement", "learned_training_measurement"):
        measure = training[key]
        if measure["measurement_digest"] != digest_of({
            k:v for k,v in measure.items() if k != "measurement_digest"
        }):
            raise DiscoveryError("tampered training metrics")
    for key in ("baseline_check", "descendant_check"):
        measure = report[key]
        if measure["measurement_digest"] != digest_of({
            k:v for k,v in measure.items() if k != "measurement_digest"
        }):
            raise DiscoveryError("tampered check metrics")
    seed = validate_genome(training["seed_genome"])
    current = seed
    for index, step in enumerate(training["search_steps"]):
        if step["search_step_digest"] != digest_of({
            k:v for k,v in step.items() if k != "search_step_digest"
        }):
            raise DiscoveryError("tampered lineage step")
        if (step["parent_genome_digest"] != current["genome_digest"]
                or step["generation_from"] != current["generation"]):
            raise DiscoveryError("lineage not descended from prior policy")
        possibilities = neighborhood(current)
        proposals = step["candidate_proposals"]
        if len(proposals) != len(possibilities) or step["proposal_count"] != len(possibilities):
            raise DiscoveryError("missing genome proposals")
        for proposed, expected in zip(proposals, possibilities):
            if proposed["genome_digest"] != expected["genome_digest"] or proposed["mutation"] != expected["mutation"]:
                raise DiscoveryError("genome proposal was never generated")
        chosen = step["chosen_genome_digest"]
        if chosen is None:
            if index != len(training["search_steps"]) - 1:
                raise DiscoveryError("lineage advances after declining a proposal")
        else:
            candidate = next((p for p in possibilities if p["genome_digest"] == chosen), None)
            if candidate is None:
                raise DiscoveryError("chosen genome not in bounded proposal grammar")
            current = candidate
    if current != training["learned_genome"]:
        raise DiscoveryError("descendant not supported by the lineage")
    if (report["development_compilation_gain"]
            != report["descendant_check"]["compile_valid_candidates"]
            - report["baseline_check"]["compile_valid_candidates"]):
        raise DiscoveryError("compilation gain inconsistent with measurements")
    if (report["development_full_suite_gain"]
            != report["descendant_check"]["projects_with_full_suite_success"]
            - report["baseline_check"]["projects_with_full_suite_success"]):
        raise DiscoveryError("full-suite gain inconsistent with measurements")
    return dict(report)
