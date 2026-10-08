#!/usr/bin/env python3
"""Preregistered no-human-patch Java repair comparison across three new projects.

Runs 2 arms. Proposals are entirely frozen BEFORE evaluating any proposal.
The baseline disables the new G11 state consistency family, matching the
previous repair operator vocabulary. All arms receive the same buggy source.
The independent full suite is the only evidence of a successful repair.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist
from genesis.failure_localization import prioritize
from genesis.trust_root import digest_of
from scripts.run_autonomous_defects4j_lang import (
    D4J, D4J_ROOT, _run, _d4j_export, _failing_count,
)

MANIFEST = ROOT / "experiment/g11/G11_3REPO_PREREG_20261008.json"
BENCH = Path("/home/anthony/benchmarks/g11-fresh-three-20261008")
FREEZE = BENCH / "FROZEN_3REPO_CANDIDATES.json"
RESULT = ROOT / "experiment/g11/G11_3REPO_RESULTS_20261008.json"


def sha(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


def check_manifest() -> dict:
    prereg = json.loads(MANIFEST.read_text())
    body = {k: v for k, v in prereg.items() if k != "preregistration_digest"}
    if prereg["preregistration_digest"] != digest_of(body):
        raise RuntimeError("preregistration digest wrong")
    for rec in prereg["projects"]:
        project = rec["project"]
        path = D4J_ROOT / f"framework/projects/{project}/active-bugs.csv"
        with path.open() as f:
            rows = list(csv.DictReader(f))
        selected = rows[int(rec["seed_sha256"], 16) % len(rows)]
        if (selected["bug.id"] != str(rec["bug_id"])
                or selected["revision.id.buggy"] != rec["buggy_revision"]
                or sha(rec["seed"]) != rec["seed_sha256"]):
            raise RuntimeError("project metadata selection mismatch")
    return prereg


def paths_for_case(project: str, bug: int, root: Path, prefix: str) -> list[str]:
    loaded = D4J_ROOT / f"framework/projects/{project}/loaded_classes/{bug}.src"
    result = []
    if loaded.is_file():
        for line in loaded.read_text().splitlines():
            classname = line.strip().split("$", 1)[0]
            file = f"{prefix.rstrip('/')}/{classname.replace('.', '/')}.java"
            if classname and (root / file).is_file():
                result.append(file)
    if not result:
        # Fail closed; broad scans can unintentionally change evaluation
        # conditions and cannot be substituted post-registration.
        raise RuntimeError(f"no dynamic loaded classes for {project}-{bug}")
    return sorted(set(result))


def freeze(prereg: dict) -> dict:
    if FREEZE.exists():
        raise RuntimeError("FROZEN file already exists; do not rewrite")
    cases = []
    for chosen in prereg["projects"]:
        project, bug = chosen["project"], chosen["bug_id"]
        root = BENCH / f"{project}-{bug}-buggy"
        if not (root / ".defects4j.config").exists():
            raise RuntimeError(f"buggy-only checkout absent: {project}-{bug}")
        if not (root / "failing_tests").is_file():
            raise RuntimeError(f"reference full tests absent: {project}-{bug}")
        original_failures = sum(
            line.startswith("--- ") for line in (root / "failing_tests").read_text().splitlines()
        )
        if original_failures < 1:
            raise RuntimeError(f"reference must fail: {project}-{bug}")
        prefix = _d4j_export(root, "dir.src.classes")[-1]
        focus = paths_for_case(project, bug, root, prefix)
        names = prioritize((root / "failing_tests").read_text(), focus)
        arms = {}
        for arm in prereg["arms"]:
            with patch.object(
                repair_strategist, "FAMILIES",
                tuple(
                    (name, fn) for name, fn in repair_strategist.FAMILIES
                    if name != "java_state_consistency"
                ),
            ) if arm == "legacy_unchanged" else __import__("contextlib").nullcontext():
                t0 = time.perf_counter()
                result = repair_strategist.generate(
                    root, include_prefixes=[prefix], focus_paths=focus,
                    max_candidates=prereg["budget_per_arm"],
                    per_family_budget=prereg["budget_per_arm"],
                    composition_fraction=prereg["composition_fraction"],
                    source_balance_experimental=arm != "legacy_unchanged",
                    atomic_first_experimental=arm != "legacy_unchanged",
                    priority_focus_paths=names["matched_source_paths"]
                    if arm != "legacy_unchanged" else (),
                )
                t1 = time.perf_counter()
            arm_top = []
            for c in result["candidates"][:prereg["evaluate_top_k_per_arm"]]:
                original = (root / c["path"]).read_text(encoding="utf-8")
                if c["expected_sha256"] != sha(original):
                    raise RuntimeError("candidate source hash mismatch")
                arm_top.append({
                    "path": c["path"],
                    "sha256": sha(c["content_utf8"]),
                    "original_sha256": c["expected_sha256"],
                    "content_utf8": c["content_utf8"],
                    "operators": c["plan"]["component_operators"],
                    "depth": c["plan"]["depth"],
                })
            arms[arm] = {
                "total_candidates": result["candidate_count"],
                "strategy_digest": result["strategy_digest"],
                "planner_seconds": round(t1-t0, 3),
                "candidate_index_digest": digest_of([
                    (r["path"], sha(r["content_utf8"])) for r in result["candidates"]
                ]),
                "top": arm_top,
            }
            print("ARM_FROZEN", project, bug, arm,
                  "generated", len(result["candidates"]),
                  "top", len(arm_top),
                  "source_hint_count", len(names["matched_source_paths"]),
                  flush=True)
        cases.append({
            "project": project,
            "bug_id": bug,
            "buggy_root": str(root),
            "source_prefix": prefix,
            "failure_count_original": original_failures,
            "dynamic_focus_paths": focus,
            "failure_source_hints": names,
            "arms": arms,
        })
    body = {
        "schema": "genesis-g11-three-repo-frozen-candidates-v1",
        "preregistration_digest": prereg["preregistration_digest"],
        "all_cases": cases,
        "human_solution_seen": False,
        "fixed_revisions_checked_out": False,
        "candidate_evaluator_separate": True,
    }
    frozen = {**body, "freeze_digest": digest_of(body)}
    FREEZE.write_text(json.dumps(frozen, indent=2, sort_keys=True)+"\n")
    print("ALL_CASES_ALL_ARMS_FROZEN", frozen["freeze_digest"], flush=True)
    return frozen


def validate(project_root: Path, path: str, text: str, original_sha: str, triggers: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="g11-3repo-test-", dir=str(BENCH)) as temp:
        work = Path(temp) / "buggy"
        shutil.copytree(
            project_root, work,
            ignore=shutil.ignore_patterns(
                ".git", "target", "build", "*.class", "*.log", ".gradle"
            ),
        )
        source = (work / path).resolve()
        if not source.is_relative_to(work.resolve()) or not source.is_file():
            return {"error": "invalid_path", "compiled": False, "full_suite_pass": False}
        if sha(source.read_text()) != original_sha:
            return {"error": "source_mismatch", "compiled": False, "full_suite_pass": False}
        source.write_text(text)
        compile_run = _run([str(D4J), "compile"], cwd=work, check=False, timeout=180)
        if compile_run.returncode:
            return {"compiled": False, "full_suite_pass": False,
                    "compile_output_digest": sha(compile_run.stdout),
                    "error": "compile_failed"}
        # Public trigger only triage; complete suite always controls PASS.
        # Any uncertainty/incomplete trigger command is conservatively recorded
        # as inconclusive rather than as a validated failure or success.
        trigger_results = []
        for trigger in triggers[:8]:
            try:
                triage = _run(
                    [str(D4J), "test", "-t", trigger],
                    cwd=work, check=False, timeout=120,
                )
                failures = _failing_count(triage.stdout)
                trigger_results.append({
                    "test": trigger,
                    "failing_tests": failures,
                    "exit": triage.returncode,
                    "digest": sha(triage.stdout),
                })
            except Exception as exc:
                trigger_results.append({
                    "test": trigger, "failing_tests": None,
                    "error": type(exc).__name__,
                })
        known_trigger_failure = any(
            item.get("failing_tests", 0) is not None
            and item.get("failing_tests", 0) > 0
            for item in trigger_results
        )
        if known_trigger_failure:
            return {
                "compiled": True,
                "trigger_results": trigger_results,
                "full_suite_ran": False,
                "full_suite_failures": None,
                "full_suite_pass": False,
                "error": "public_trigger_still_fails",
            }
        full = _run([str(D4J), "test"], cwd=work, check=False, timeout=240)
        count = _failing_count(full.stdout)
        return {
            "compiled": True,
            "trigger_results": trigger_results,
            "full_suite_ran": True,
            "test_exit": full.returncode,
            "full_suite_failures": count,
            "full_suite_pass": count == 0 and full.returncode == 0,
            "test_output_digest": sha(full.stdout),
            "error": None if count is not None else "unparseable_full_suite",
        }


def evaluate(prereg: dict, frozen: dict) -> dict:
    if digest_of({k: v for k, v in frozen.items() if k != "freeze_digest"}) != frozen["freeze_digest"]:
        raise RuntimeError("tampered freeze")
    evaluations = []
    for case in frozen["all_cases"]:
        project = case["project"]
        root = Path(case["buggy_root"])
        unique = {}
        for arm in prereg["arms"]:
            for item in case["arms"][arm]["top"]:
                key = (item["path"], item["sha256"])
                if key in unique and item != unique[key]:
                    raise RuntimeError("hash collision/candidate mismatch")
                unique[key] = item
        validations = {}
        trigger_lines = [
            line.removeprefix("--- ").strip()
            for line in (root / "failing_tests").read_text().splitlines()
            if line.startswith("--- ")
        ]
        for index, (key, item) in enumerate(sorted(unique.items()), 1):
            outcome = validate(root, item["path"], item["content_utf8"],
                               item["original_sha256"], trigger_lines)
            validations[key] = outcome
            print("VALIDATED", project, case["bug_id"],
                  index, "of", len(unique), "compiled", outcome["compiled"],
                  "failures", outcome.get("full_suite_failures"),
                  "error", outcome.get("error"), flush=True)
        arms = {}
        for arm in prereg["arms"]:
            top = case["arms"][arm]["top"]
            indexes = [
                rank for rank, item in enumerate(top, 1)
                if validations[(item["path"], item["sha256"])]["full_suite_pass"]
            ]
            arms[arm] = {
                "generated": case["arms"][arm]["total_candidates"],
                "tested_top_k": len(top),
                "compile_passes": sum(bool(
                    validations[(item["path"], item["sha256"])]["compiled"]
                ) for item in top),
                "full_suite_passes": len(indexes),
                "first_passing_rank": min(indexes) if indexes else None,
                "candidate_index_digest": case["arms"][arm]["candidate_index_digest"],
                "planner_seconds": case["arms"][arm]["planner_seconds"],
                "top_operator_families": [
                    item["operators"] for item in top
                ],
                "top_source_classes": [
                    Path(item["path"]).stem for item in top
                ],
            }
        evaluations.append({
            "project": project,
            "bug_id": case["bug_id"],
            "original_failure_count": case["failure_count_original"],
            "distinct_candidates_evaluated": len(unique),
            "full_suite_valid_unique_candidates": sum(
                bool(o["full_suite_pass"]) for o in validations.values()
            ),
            "outcomes": [
                {"path": key[0], "sha256": key[1], "result": outcome}
                for key, outcome in sorted(validations.items())
            ],
            "arms": arms,
        })
    summary = {
        arm: sum(int(x["arms"][arm]["first_passing_rank"] is not None)
                 for x in evaluations)
        for arm in prereg["arms"]
    }
    body = {
        "schema": "genesis-g11-three-repo-prospective-results-v1",
        "preregistration_digest": prereg["preregistration_digest"],
        "freeze_digest": frozen["freeze_digest"],
        "case_count": len(evaluations),
        "cases_solved_per_arm": summary,
        "cases": evaluations,
        "unseen_prior_to_candidate_freeze": True,
        "no_fixed_revision_or_human_solution": True,
        "independent_full_suite_required": True,
        "claim_scope": "three fresh diverse Java projects; exploratory, not general RSI",
    }
    result = {**body, "result_digest": digest_of(body)}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n")
    print("COMPLETED", json.dumps(summary), "report", RESULT, flush=True)
    return result


if __name__ == "__main__":
    prereg = check_manifest()
    frozen = freeze(prereg) if not FREEZE.exists() else json.loads(FREEZE.read_text())
    evaluate(prereg, frozen)
