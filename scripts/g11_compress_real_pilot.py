#!/usr/bin/env python3
"""Frozen blind G11 Compress-6 pilot. Does NOT inspect the human fixed revision.

The buggy checkout must be prepared separately. This standalone local tool
owns validation: candidate generator receives only buggy source, no oracle
outputs, no fixed reference, no human patch, no benchmark issue description.
The sealed per-arm candidate freeze precedes any candidate validation.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist
from genesis.insights import InsightRegistry, JavaPerformanceModule, JavaSecurityModule
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry
from genesis.trust_root import digest_of
from scripts.run_autonomous_defects4j_lang import (
    D4J, D4J_ROOT, JAVA, JAVAC, _d4j_export, _run, _failing_count,
)

MANIFEST = ROOT / "experiment/g11/G11_COMPRESS6_PREREG_20261008.json"
RESULTS = ROOT / "experiment/g11/G11_COMPRESS6_RESULTS_20261008.json"
BENCH = Path("/home/anthony/benchmarks/g11-compress6-20261008")
BUGGY = BENCH / "buggy"
FREEZE = BENCH / "FROZEN_CANDIDATES.json"
ARMS = ("baseline", "source_balanced", "balanced_g11_hypotheses")


def digest_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def check_manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text())
    unsigned = {k: v for k, v in manifest.items() if k != "preregistration_digest"}
    if manifest["preregistration_digest"] != digest_of(unsigned):
        raise RuntimeError("preregistration digest invalid")
    with (D4J_ROOT / "framework/projects/Compress/active-bugs.csv").open() as fh:
        rows = list(csv.DictReader(fh))
    selected = rows[int(manifest["selection_digest"], 16) % len(rows)]
    if (selected["bug.id"] != str(manifest["bug_id"])
            or selected["revision.id.buggy"] != manifest["buggy_revision"]
            or hashlib.sha256(manifest["selection_seed"].encode()).hexdigest() != manifest["selection_digest"]):
        raise RuntimeError("selection provenance mismatch")
    if not (BUGGY / ".defects4j.config").is_file():
        raise RuntimeError("buggy-only checkout missing")
    if (BUGGY / ".defects4j.config").read_text().find("Compress") < 0:
        raise RuntimeError("unexpected Defects4J project checkout")
    return manifest


def focus_files(root: Path, srcdir: str) -> list[str]:
    loaded = D4J_ROOT / "framework/projects/Compress/loaded_classes/6.src"
    files = []
    for entry in loaded.read_text().splitlines():
        classname = entry.strip().split("$", 1)[0]
        relative = srcdir.strip("/") + "/" + classname.replace(".", "/") + ".java"
        if classname and (root / relative).is_file():
            files.append(relative)
    return sorted(set(files))


def generated_candidates(manifest: dict) -> dict:
    if FREEZE.exists():
        raise RuntimeError("candidate freeze already exists; refuse silent overwrite")
    prefix = _d4j_export(BUGGY, "dir.src.classes")[-1]
    focus = focus_files(BUGGY, prefix)
    if not focus:
        raise RuntimeError("no focus paths from the dynamic class list")
    registry = ModuleRegistry()
    registry.register(JavaCompilerModule(java=JAVA, javac=JAVAC))
    insights = InsightRegistry()
    insights.register(JavaSecurityModule())
    insights.register(JavaPerformanceModule())

    arms: dict[str, Any] = {}
    for name in ARMS:
        time_start = time.perf_counter()
        enhanced = name == "balanced_g11_hypotheses"
        strategy = repair_strategist.generate(
            BUGGY,
            include_prefixes=[prefix],
            focus_paths=focus,
            max_candidates=int(manifest["budget_each"]),
            per_family_budget=int(manifest["budget_each"]),
            composition_fraction=float(manifest["composition_fraction"]),
            understanding_registry=registry if enhanced else None,
            insight_registry=insights if enhanced else None,
            understanding_hypotheses=enhanced,
            understanding_rerank=False,
            source_balance_experimental=name != "baseline",
            max_understanding_files=4,
        )
        candidates = strategy["candidates"]
        top = candidates[:int(manifest["top_k_full_suite"])]
        arms[name] = {
            "planner_seconds": round(time.perf_counter() - time_start, 4),
            "candidate_count": len(candidates),
            "strategy_digest": strategy["strategy_digest"],
            "candidate_order_digest": digest_of([
                (c["path"], digest_bytes(c["content_utf8"].encode())) for c in candidates
            ]),
            "source_analysis": strategy.get("g11_understanding"),
            "top": [
                {
                    "path": c["path"],
                    "text": c["content_utf8"],
                    "source_expected_sha256": c["expected_sha256"],
                    "candidate_sha256": digest_bytes(c["content_utf8"].encode()),
                    "candidate_digest": c["candidate_digest"],
                }
                for c in top
            ],
        }
        print("FROZE_ARM", name, "candidates", len(candidates),
              "top", len(top), "hypotheses",
              (strategy.get("g11_understanding") or {}).get("repair_hypotheses", {}).get("hypothesis_count", 0),
              flush=True)
    if (
        arms["source_balanced"]["candidate_order_digest"]
        != arms["balanced_g11_hypotheses"]["candidate_order_digest"]
    ):
        raise RuntimeError("shadow annotation changed candidate order")
    payload = {
        "schema": "genesis-g11-compress6-frozen-candidates-v1",
        "preregistration_digest": manifest["preregistration_digest"],
        "buggy_root": str(BUGGY),
        "source_prefix": prefix,
        "focus_paths": focus,
        "candidate_arms": arms,
        "generator_did_not_receive_test_oracle": True,
        "human_fixed_revision_checked_out": False,
    }
    frozen = {**payload, "freeze_digest": digest_of(payload)}
    FREEZE.write_text(json.dumps(frozen, indent=2, sort_keys=True) + "\n")
    print("ALL_ARMS_FROZEN", frozen["freeze_digest"], flush=True)
    return frozen


def evaluate_unique(source: Path, text: str, key: str, original_sha: str) -> dict:
    """Compile and run complete Defects4J test suite in a fresh buggy-only copy."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="g11-codec-validate-", dir=str(BENCH)) as temp:
        workspace = Path(temp) / "project"
        shutil.copytree(BUGGY, workspace, ignore=shutil.ignore_patterns(
            ".git", "target", "build", ".gradle", "*.class", "*.log"
        ))
        dest = workspace / source
        if not dest.is_file():
            return {"compiled": False, "failing_tests": None, "error": "candidate path missing"}
        if digest_bytes(dest.read_bytes()) != original_sha:
            return {"compiled": False, "failing_tests": None, "error": "source preimage mismatch"}
        dest.write_text(text, encoding="utf-8")
        try:
            compile_r = _run([str(D4J), "compile"], cwd=workspace, check=False, timeout=180)
            if compile_r.returncode != 0:
                return {
                    "compiled": False, "failing_tests": None,
                    "compile_exit": compile_r.returncode,
                    "compile_output_sha256": digest_bytes(compile_r.stdout.encode()),
                    "error": "compile failed",
                }
            tests = _run([str(D4J), "test"], cwd=workspace, check=False, timeout=240)
            failures = _failing_count(tests.stdout)
            return {
                "compiled": True,
                "failing_tests": failures,
                "test_exit": tests.returncode,
                "validated_full_suite": tests.returncode == 0 and failures == 0,
                "test_output_sha256": digest_bytes(tests.stdout.encode()),
                "error": None if failures is not None else "unparseable test result",
            }
        except Exception as exc:
            return {
                "compiled": False,
                "failing_tests": None,
                "validated_full_suite": False,
                "error": type(exc).__name__,
            }


def evaluate_frozen(manifest: dict) -> dict:
    frozen = json.loads(FREEZE.read_text())
    unsigned = {k: v for k, v in frozen.items() if k != "freeze_digest"}
    if digest_of(unsigned) != frozen["freeze_digest"]:
        raise RuntimeError("freeze integrity check failed")
    if frozen["preregistration_digest"] != manifest["preregistration_digest"]:
        raise RuntimeError("preregistration changed")
    entries = {}
    for arm in frozen["candidate_arms"].values():
        for c in arm["top"]:
            target = Path(c["path"])
            if target.is_absolute() or ".." in target.parts:
                raise RuntimeError("unsafe candidate target path")
            key = (c["path"], c["candidate_sha256"])
            if digest_bytes(c["text"].encode()) != c["candidate_sha256"]:
                raise RuntimeError("candidate content changed after freeze")
            if key in entries and entries[key] != c:
                raise RuntimeError("inconsistent duplicate candidate")
            entries[key] = c

    decisions = {}
    for index, (key, candidate) in enumerate(sorted(entries.items()), 1):
        outcome = evaluate_unique(
            Path(candidate["path"]), candidate["text"], str(key),
            candidate["source_expected_sha256"],
        )
        decisions[key] = outcome
        print("VALIDATED", index, "of", len(entries), key[1][:10],
              "compiled", outcome.get("compiled"),
              "failing", outcome.get("failing_tests"),
              "error", outcome.get("error"), flush=True)

    scored = {}
    for name in ARMS:
        arm = frozen["candidate_arms"][name]
        evaluated = [
            decisions[(c["path"], c["candidate_sha256"])]
            for c in arm["top"]
        ]
        passes = [
            i+1 for i, item in enumerate(evaluated)
            if item.get("validated_full_suite", False)
        ]
        scored[name] = {
            "candidate_count": arm["candidate_count"],
            "evaluated_top_k": len(evaluated),
            "fully_validated_repair_count": len(passes),
            "first_validated_rank": min(passes) if passes else None,
            "compiled_count": sum(bool(item.get("compiled")) for item in evaluated),
            "unparseable_or_exception_count": sum(item.get("failing_tests") is None for item in evaluated),
            "planner_seconds": arm["planner_seconds"],
            "hypothesis_count": (arm.get("source_analysis") or {}).get(
                "repair_hypotheses", {}
            ).get("hypothesis_count", 0),
            "candidate_order_digest": arm["candidate_order_digest"],
        }
    body = {
        "schema": "genesis-g11-compress6-real-project-evaluation-v1",
        "preregistration_digest": manifest["preregistration_digest"],
        "freeze_digest": frozen["freeze_digest"],
        "project": "Compress",
        "bug_id": 6,
        "original_compiles": True,
        "original_full_suite_failing_count": 1,
        "all_arms_frozen_before_validation": True,
        "unique_candidates_evaluated": len(decisions),
        "fully_validated_unique_candidates": sum(bool(x.get("validated_full_suite", False))
                                                for x in decisions.values()),
        "validator_outcomes": [
            {"path": key[0], "sha256": key[1], "outcome": decision}
            for key, decision in sorted(decisions.items())
        ],
        "arms": scored,
        "fixed_checkout_or_human_patch_used": False,
        "read_only_source_analysis": True,
        "result_limit": "one real-project defect, top-8 full suites, no RSI/generalization claim",
    }
    result = {**body, "report_digest": digest_of(body)}
    RESULTS.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("REAL_PROJECT_REPORT", RESULTS, json.dumps({
        name: scored[name]["first_validated_rank"] for name in ARMS
    }), flush=True)
    return result


if __name__ == "__main__":
    manifest = check_manifest()
    frozen = generated_candidates(manifest)
    evaluate_frozen(manifest)
