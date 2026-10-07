"""External evaluator helpers for the bounded Genesis v2 G10 campaign.

This file is deliberately outside mutable genesis/ lineage machinery.  It owns
truth assignment for the synthetic software-repair assay; lineage code receives
only task files and candidate outcomes, never the expected repaired files.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Mapping

from genesis.evolution import recursive_chain
from genesis.runtime import recursive_chain_executor
from genesis.trust_root import digest_of

MEASUREMENT_SCHEMA = "genesis-g10-profile-measurement-v1"


def _write_case(root: Path, case: Mapping[str, Any]) -> None:
    for rel, content in dict(case["files"]).items():
        path = root / str(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(content), encoding="utf-8")


def _evaluate_exact(root: Path, case: Mapping[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    expected_files = dict(case.get("expected_files") or {})
    mismatches: list[str] = []
    for rel, expected in expected_files.items():
        path = root / str(rel)
        if not path.is_file() or path.read_text(encoding="utf-8") != str(expected):
            mismatches.append(str(rel))
    return {
        "passed": not mismatches,
        "mismatched_files": mismatches,
        "wall_time_seconds": round(time.monotonic() - started, 6),
    }


def _apply_candidate(root: Path, candidate: Mapping[str, Any]) -> tuple[bool, str | None]:
    mutations = list(candidate.get("mutations") or [])
    if not mutations:
        return False, "candidate has no mutations"
    seen: set[str] = set()
    for mutation in mutations:
        rel = str(mutation.get("path") or "")
        if not rel or rel in seen:
            return False, "candidate mutation path is empty or duplicated"
        seen.add(rel)
        target = (root / rel).resolve()
        if not str(target).startswith(str(root.resolve()) + "/"):
            return False, "unsafe mutation path"
        if not target.is_file():
            return False, "mutation target missing"
        before = target.read_text(encoding="utf-8")
        expected = str(mutation.get("expected_sha256") or "")
        if hashlib.sha256(before.encode("utf-8")).hexdigest() != expected:
            return False, "mutation expected source digest mismatch"
        target.write_text(str(mutation.get("content_utf8") or ""), encoding="utf-8")
    return True, None


def raw_failures(bank: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for case in bank["cases"]:
        with tempfile.TemporaryDirectory(prefix="genesis-g10-raw-") as temp:
            root = Path(temp)
            _write_case(root, case)
            evaluation = _evaluate_exact(root, case)
            records.append({
                "case_id": case["id"],
                "group": case["group"],
                "passed": bool(evaluation["passed"]),
            })
    return records


def evaluate_profile(
    repository_root: str | Path,
    profile: Mapping[str, Any],
    bank: Mapping[str, Any],
    *,
    max_candidates_per_case: int,
) -> dict[str, Any]:
    repository = Path(repository_root).resolve()
    held = recursive_chain.validate_profile(profile)
    solved = 0
    total_executions = 0
    cases: list[dict[str, Any]] = []
    started = time.monotonic()
    cpu_started = time.process_time_ns()

    for case in bank["cases"]:
        with tempfile.TemporaryDirectory(prefix="genesis-g10-task-") as temp:
            task = Path(temp)
            _write_case(task, case)
            generated = recursive_chain_executor.generate_candidates(
                task,
                held,
                repository_root=repository,
                max_candidates=max_candidates_per_case,
            )
            case_record: dict[str, Any] = {
                "case_id": case["id"],
                "group": case["group"],
                "candidate_count": generated["candidate_count"],
                "candidate_budget": max_candidates_per_case,
                "candidate_executions": 0,
                "passed": False,
                "winner": None,
                "evaluations": [],
                "generation_digest": generated["generation_digest"],
            }
            for candidate in generated["candidates"][:max_candidates_per_case]:
                with tempfile.TemporaryDirectory(prefix="genesis-g10-candidate-") as candidate_temp:
                    candidate_root = Path(candidate_temp)
                    _write_case(candidate_root, case)
                    applied, problem = _apply_candidate(candidate_root, candidate)
                    case_record["candidate_executions"] += 1
                    total_executions += 1
                    evaluation = (
                        _evaluate_exact(candidate_root, case)
                        if applied
                        else {"passed": False, "apply_error": problem}
                    )
                    item = {
                        "candidate_id": candidate["candidate_id"],
                        "candidate_digest": candidate["candidate_digest"],
                        "route": candidate["route"],
                        "recursive_trace": candidate.get("recursive_trace") or {},
                        "passed": bool(evaluation.get("passed")),
                        "evaluation": evaluation,
                    }
                    case_record["evaluations"].append(item)
                    if item["passed"]:
                        case_record["passed"] = True
                        case_record["winner"] = item
                        solved += 1
                        break
            cases.append(case_record)

    groups: dict[str, int] = {}
    for case in cases:
        groups[case["group"]] = groups.get(case["group"], 0) + int(case["passed"])
    payload = {
        "schema": MEASUREMENT_SCHEMA,
        "profile_digest": held["profile_digest"],
        "campaign_generation": held["campaign_generation"],
        "bank_digest": bank["bank_digest"],
        "solved": solved,
        "case_count": len(cases),
        "success_rate": solved / len(cases) if cases else 0.0,
        "group_solved": groups,
        "candidate_executions": total_executions,
        "candidate_budget_per_case": max_candidates_per_case,
        "candidate_budget_total": max_candidates_per_case * len(cases),
        "within_candidate_budget": total_executions <= max_candidates_per_case * len(cases),
        "external_model_calls": 0,
        "wall_time_seconds": round(time.monotonic() - started, 6),
        "controller_cpu_process_time_ns": int(time.process_time_ns() - cpu_started),
        "cases": cases,
    }
    return {**payload, "measurement_digest": digest_of(payload)}


def build_discovery_evidence(measurement: Mapping[str, Any]) -> dict[str, Any]:
    traces: list[dict[str, Any]] = []
    for case in measurement["cases"]:
        if not case["passed"] or not case.get("winner"):
            continue
        winner = case["winner"]
        trace = dict(winner.get("recursive_trace") or {})
        traces.append({
            "case_id": case["case_id"],
            "group": case["group"],
            "candidate_digest": winner["candidate_digest"],
            "route": winner["route"],
            "candidate_execution_index": len(case["evaluations"]),
            "capability_level": int(trace.get("capability_level", 0)),
            "mode": str(trace.get("mode") or ""),
            "scope_ids": list(trace.get("scope_ids") or []),
            "template_digests": list(trace.get("template_digests") or []),
            "base_template_digest": str(trace.get("base_template_digest") or ""),
        })
    payload = {
        "schema": recursive_chain.DISCOVERY_SCHEMA,
        "profile_digest": measurement["profile_digest"],
        "measurement_digest": measurement["measurement_digest"],
        "bank_digest": measurement["bank_digest"],
        "solved": int(measurement["solved"]),
        "case_count": int(measurement["case_count"]),
        "candidate_executions": int(measurement["candidate_executions"]),
        "candidate_budget_per_case": int(measurement["candidate_budget_per_case"]),
        "external_model_calls": int(measurement["external_model_calls"]),
        "successful_traces": traces,
    }
    return {**payload, "discovery_digest": digest_of(payload)}


def pass_ids(measurement: Mapping[str, Any]) -> set[str]:
    return {
        str(case["case_id"])
        for case in measurement["cases"]
        if case["passed"]
    }
