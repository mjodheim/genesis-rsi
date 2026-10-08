"""Trusted V2 retrospective promotion gate — cannot approve known cases.

Even a successful development rerank must not be deployed based on exposed
benchmark outcomes. On any future prospective run, a separate evaluator
must supply independently frozen case receipts and an external authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genesis.trust_root import digest_of
from genesis.v2.discovery import validate_study

SCHEMA = "genesis-v2-retrospective-promotion-assessment-v1"


def assess_development(study: Mapping[str, Any]) -> dict[str, Any]:
    report = validate_study(study)
    base = report["baseline_check"]
    evolved = report["descendant_check"]
    if len(base["individual"]) != len(evolved["individual"]):
        raise ValueError("parent and child must be judged on identical cases")
    per_case = []
    for parent, child in zip(base["individual"], evolved["individual"]):
        if parent["case_id"] != child["case_id"] or parent["evaluated"] != child["evaluated"]:
            raise ValueError("parent and child do not have equal budgets/cases")
        per_case.append({
            "case_id": parent["case_id"],
            "equal_budget": True,
            "compilation_delta": child["compiled"] - parent["compiled"],
            "full_suite_delta": child["full_suite_valid"] - parent["full_suite_valid"],
            "baseline_compiled": parent["compiled"],
            "descendant_compiled": child["compiled"],
        })
    regressions = [
        c["case_id"] for c in per_case
        if c["compilation_delta"] < 0 or c["full_suite_delta"] < 0
    ]
    body = {
        "schema": SCHEMA,
        "source_study_digest": report["study_digest"],
        "evidence_type": "already_exposed_development_replay",
        "case_count": len(per_case),
        "candidate_budget_per_case": report["top_k_each_case"],
        "development_compilation_gain": report["development_compilation_gain"],
        "development_full_suite_gain": report["development_full_suite_gain"],
        "cases_with_regression": sorted(regressions),
        "per_case": per_case,
        "fresh_holdout_evidence_present": False,
        "production_promotion_allowed": False,
        "self_discovered_semantic_capability_proven": False,
        "gate_reasons": [
            "corpus_already_exposed",
            *(
                ["no_new_full_suite_repairs"]
                if report["development_full_suite_gain"] <= 0 else []
            ),
            *(["per_project_regression"] if regressions else []),
            "external_authority_and_fresh_prospective_tests_required",
        ],
    }
    return {**body, "gate_digest": digest_of(body)}


def validate_assessment(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != SCHEMA:
        raise ValueError("unknown development promotion gate")
    data = {k:v for k,v in value.items() if k != "gate_digest"}
    if value.get("gate_digest") != digest_of(data):
        raise ValueError("tampered promotion gate")
    if (value.get("fresh_holdout_evidence_present") is not False
            or value.get("production_promotion_allowed") is not False
            or value.get("self_discovered_semantic_capability_proven") is not False):
        raise ValueError("exposed retrospective study cannot approve promotion")
    if any(not row.get("equal_budget") for row in value.get("per_case", [])):
        raise ValueError("unequal candidate comparison")
    return dict(value)
