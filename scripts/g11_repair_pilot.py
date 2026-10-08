#!/usr/bin/env python3
"""Pre-registered, paired G11 ranking pilot on synthetic Java repairs.

This is NOT an autonomous external repair benchmark. It cannot validate ER4.
No examples, oracle harnesses or patches are supplied to repair_strategist.
All arms and candidate indexes freeze before any candidate is evaluated.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist
from genesis.insights import InsightRegistry, JavaSecurityModule, JavaPerformanceModule
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry
from genesis.trust_root import digest_of

JDK = Path("/home/anthony/tools/jdk11/bin")
PREREG = ROOT / "experiment/g11/G11_REPAIR_PILOT_PREREG_20261008.json"
REPORT = ROOT / "experiment/g11/G11_REPAIR_PILOT_RESULTS_20261008.json"
MAX_CANDIDATES = 64
TOP_K = 24
ARMS = ("baseline", "understanding", "understanding_security_performance")

# Sources and independent expected value tables selected *before* any generation.
# The planner only sees the buggy source in a temporary src directory.
CASES = (
    ("A", "public class TrialA { public static int f(int x) { if (x < 5) return 1; return 0; } }\n",
        [(-4, 1), (0, 1), (4, 1), (5, 1), (6, 0), (99, 0)]),
    ("B", "public class TrialB { public static int f(int x) { if (x < 2) return 0; if (x > 10) return 10; return x; } }\n",
        [(-3, 0), (0, 0), (1, 1), (2, 2), (6, 6), (10, 10), (11, 10), (25, 10)]),
    ("C", "public class TrialC { public static int f(int x) { if (x > 0) return 1; return 0; } }\n",
        [(-3, 0), (-1, 0), (0, 1), (1, 1), (3, 1)]),
    ("D", "public class TrialD { public static int f(int x, int y) { return x < y ? x : y; } }\n",
        [((-1, 3), 3), ((5, 2), 5), ((1, 1), 1), ((-7, -3), -3), ((9, 10), 10)]),
    ("E", "public class TrialE { public static int f(int n) { int count = 0; for (int i=0; i<=n; i++) count++; return count; } }\n",
        [(-2, 0), (0, 0), (1, 1), (2, 2), (3, 3), (6, 6)]),
    ("F", "public class TrialF { public static boolean f(int x) { return x % 2 == 1; } }\n",
        [(-5, True), (-3, True), (-2, False), (-1, True), (0, False), (1, True), (2, False), (3, True)]),
    ("G", 'public class TrialG { public static String f(String x) { if (x == null) return null; return x.trim(); } }\n',
        [(None, ""), ("", ""), (" hi ", "hi"), ("a", "a"), ("  ", "")]),
    ("H", "public class TrialH { public static int f(int x) { return x + 1; } }\n",
        [(-3, -1), (0, 2), (1, 3), (3, 5), (11, 13)]),
)


def java_lit(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=True)
    raise TypeError(v)


def java_test_source(cid: str, checks: list[tuple[Any, Any]]) -> str:
    rows = []
    for i, (args, expected) in enumerate(checks):
        values = args if isinstance(args, tuple) else (args,)
        call = f"Trial{cid}.f(" + ",".join(java_lit(x) for x in values) + ")"
        rows.append(
            f'if (!java.util.Objects.equals({call}, {java_lit(expected)})) '
            f'throw new AssertionError("check {cid}:{i}");'
        )
    return 'public class IndependentOracle { public static void main(String[] args) {\n' + '\n'.join(rows) + '\n} }\n'


def preregistration() -> dict[str, Any]:
    items = []
    for cid, source, cases in CASES:
        tests = java_test_source(cid, cases)
        items.append({
            "case_id": cid,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "oracle_sha256": hashlib.sha256(tests.encode()).hexdigest(),
            "oracle_assertion_count": len(cases),
        })
    body = {
        "schema": "genesis-g11-java-repair-pilot-preregistration-v1",
        "base_commit": "f4c6b05b",
        "languages": ["java"],
        "arms": list(ARMS),
        "candidate_budget_per_arm": MAX_CANDIDATES,
        "top_k_compiled_and_validated_per_arm": TOP_K,
        "composition_fraction": 0.4,
        "per_family_budget": MAX_CANDIDATES,
        "case_count": len(items),
        "cases": items,
        "oracle_hidden_from_planner": True,
        "all_arms_freeze_before_oracle": True,
        "human_revealed_patches_used": False,
        "er4_holdout_cases_used": False,
        "memory_learning_during_test": False,
        "score_policy": "full_assertion_suite_pass_only; compilation + oracle execution",
        "claim_limit": "synthetic constrained pilot; not real-world autonomous repair evidence",
    }
    return {**body, "preregistration_digest": digest_of(body)}


def command(args: list[str], *, timeout: int) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           text=True, timeout=timeout)
        return p.returncode == 0, p.stdout[-300:]
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, type(exc).__name__


def validate_candidate(src: str, cid: str, tests: str, identifier: str) -> dict[str, Any]:
    # Synthetic source produced by trusted Genesis mutation families; no
    # external repos run. This is timeout-limited but NOT an OS sandbox.
    with tempfile.TemporaryDirectory(prefix="g11-verify-") as td:
        dir = Path(td)
        source = dir / f"Trial{cid}.java"
        harness = dir / "IndependentOracle.java"
        source.write_text(src, encoding="utf-8")
        harness.write_text(tests, encoding="utf-8")
        compile_ok, compile_detail = command(
            [str(JDK/"javac"), "-encoding", "UTF-8", "-proc:none",
             "-d", str(dir), str(source), str(harness)], timeout=12)
        if not compile_ok:
            return {"candidate_hash": identifier, "compiled": False,
                    "full_suite_passed": False, "failure": "compilation",
                    "detail": compile_detail[:150]}
        passed, output = command(
            [str(JDK/"java"), "-Xmx96m", "-cp", str(dir), "IndependentOracle"],
            timeout=5)
        return {"candidate_hash": identifier, "compiled": True,
                "full_suite_passed": passed,
                "failure": None if passed else "oracle_assertion",
                "detail": output[:150] if not passed else ""}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preregister", action="store_true")
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    manifest = preregistration()
    if args.preregister and not args.run:
        PREREG.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        print(json.dumps({"preregistered": str(PREREG),
                          "manifest_digest": manifest["preregistration_digest"]}))
        return 0
    if not args.run:
        parser.error("choose --preregister or --run")
    if json.loads(PREREG.read_text()) != manifest:
        raise RuntimeError("preregistration mismatch: REFUSE TO RUN")
    if not all((JDK / exe).is_file() for exe in ("java", "javac")):
        raise RuntimeError("JDK11 missing")
    language = ModuleRegistry()
    language.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
    insights = InsightRegistry()
    insights.register(JavaSecurityModule())
    insights.register(JavaPerformanceModule())

    # First freeze every arm's indexes with no access to oracle or solutions.
    generation = []
    oracle_sources = {}
    with tempfile.TemporaryDirectory(prefix="g11-plan-") as td:
        for cid, src, checks in CASES:
            oracle_sources[cid] = java_test_source(cid, checks)
            project = Path(td) / cid
            (project/"src").mkdir(parents=True)
            (project/"src"/f"Trial{cid}.java").write_text(src)
            case_arms = {}
            for arm in ARMS:
                started = time.perf_counter()
                result = repair_strategist.generate(
                    project,
                    include_prefixes=["src"],
                    focus_paths=[f"src/Trial{cid}.java"],
                    max_candidates=MAX_CANDIDATES,
                    per_family_budget=MAX_CANDIDATES,
                    understanding_registry=language if arm != "baseline" else None,
                    insight_registry=insights if arm == "understanding_security_performance" else None,
                )
                elapsed = time.perf_counter() - started
                candidates = result["candidates"]
                case_arms[arm] = {
                    "candidate_count": len(candidates),
                    "planner_digest": result["strategy_digest"],
                    "planner_elapsed_seconds": round(elapsed, 3),
                    "top_hashes": [c["content_sha256"] for c in candidates[:TOP_K]],
                    "candidate_order_digest": digest_of(
                        [c["content_sha256"] for c in candidates]),
                    "g11_report": result.get("g11_understanding"),
                    "candidates": candidates[:TOP_K],
                }
            generation.append({"case_id": cid, "source": src, "arms": case_arms})

        frozen = [
            {"case_id": case["case_id"],
             "arms": {name: {"candidate_order_digest": arm["candidate_order_digest"],
                             "top_hashes": arm["top_hashes"]}
                      for name, arm in case["arms"].items()}}
            for case in generation
        ]
        freeze_digest = digest_of(frozen)
        print("ALL_ARMS_FROZEN", freeze_digest, flush=True)

        # No mutation into planner: case oracle tests are loaded only at this
        # point and never placed under the candidate source tree.
        evaluation = []
        for case in generation:
            cid = case["case_id"]
            harness = oracle_sources[cid]
            original = validate_candidate(case["source"], cid, harness, "original")
            if original["full_suite_passed"]:
                raise RuntimeError(f"Case {cid} not actually buggy: REFUSE TO REPORT")
            jobs: dict[str, str] = {}
            for arm in case["arms"].values():
                for candidate in arm["candidates"]:
                    key = candidate["content_sha256"]
                    if key in jobs and jobs[key] != candidate["content_utf8"]:
                        raise RuntimeError("candidate SHA256 collision")
                    jobs[key] = candidate["content_utf8"]
            validations = {}
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = {
                    pool.submit(validate_candidate, code, cid, harness, key): key
                    for key, code in jobs.items()
                }
                for future in as_completed(futures):
                    key = futures[future]
                    validations[key] = future.result()
            reported_arms = {}
            for arm_name, arm in case["arms"].items():
                ordered = arm["top_hashes"]
                passes = [i + 1 for i, key in enumerate(ordered)
                          if validations[key]["full_suite_passed"]]
                reported_arms[arm_name] = {
                    "generated_count": arm["candidate_count"],
                    "evaluated_top_k": len(ordered),
                    "passed_in_top_k": len(passes),
                    "first_validated_rank": min(passes) if passes else None,
                    "candidate_order_digest": arm["candidate_order_digest"],
                    "planner_seconds": arm["planner_elapsed_seconds"],
                    "planner_strategy_digest": arm["planner_digest"],
                    "understanding_metadata": arm["g11_report"],
                    "compile_success_count": sum(bool(validations[k]["compiled"]) for k in ordered),
                }
            summary = {
                "case_id": cid,
                "source_sha256": hashlib.sha256(case["source"].encode()).hexdigest(),
                "original_compiles": original["compiled"],
                "original_fails_full_suite": not original["full_suite_passed"],
                "unique_candidates_evaluated": len(validations),
                "unique_candidates_passed": sum(bool(v["full_suite_passed"]) for v in validations.values()),
                "arms": reported_arms,
                "validation_digest": digest_of(sorted(
                    (key, v["compiled"], v["full_suite_passed"])
                    for key, v in validations.items())),
            }
            evaluation.append(summary)
            print("CASE_DONE", cid, json.dumps({
                a: info["first_validated_rank"] for a, info in reported_arms.items()
            }, sort_keys=True), "unique", len(validations), flush=True)

    counts = {arm: sum(row["arms"][arm]["first_validated_rank"] is not None
                       for row in evaluation) for arm in ARMS}
    totals = {arm: round(sum(row["arms"][arm]["planner_seconds"] for row in evaluation), 3)
              for arm in ARMS}
    body = {
        "schema": "genesis-g11-java-repair-pilot-results-v1",
        "preregistration_digest": manifest["preregistration_digest"],
        "freeze_digest": freeze_digest,
        "case_count": len(evaluation),
        "all_cases_verified_buggy_before_passing_candidates": True,
        "full_suite_passed_case_counts_by_arm": counts,
        "planner_wall_seconds_by_arm": totals,
        "cases": evaluation,
        "training_memory_used": False,
        "er4_holdouts_used": False,
        "candidate_validation_isolated_from_generator": True,
        "limitation": "synthetic fixtures, top-24 ranking, no independent external evaluation; performance module only provides annotations",
    }
    REPORT.write_text(json.dumps({**body, "report_digest": digest_of(body)},
                                  indent=2, sort_keys=True) + "\n")
    print("REPORT", str(REPORT), json.dumps(counts, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
