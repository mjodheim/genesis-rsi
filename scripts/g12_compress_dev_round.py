#!/usr/bin/env python3
"""G12 reproducible development-only automatic structural operator retention.

Uses already exposed Compress-6 and the human-authored generic candidate
generator. Genesis itself synthesizes the declarative *structural* operator
after the independent full suite validates the generated candidate.
This is not a newly discovered semantic algorithm or an unseen benchmark.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import repair_strategist
from genesis.g12_operator_lab import freeze_training_search, validate_and_learn
from genesis.learning import self_extension
from genesis.trust_root import digest_of
from scripts.g11_compress_real_pilot import (
    BUGGY, evaluate_unique, focus_files,
)
from scripts.run_autonomous_defects4j_lang import _d4j_export

BASE = Path("/home/anthony/benchmarks/g12-development-compress6")
FREEZE = BASE / "frozen_candidates.json"
MEMORY = BASE / "acquired_operator_memory.json"
RECEIPT = ROOT / "experiment/g12/G12_COMPRESS6_DEVELOPMENT_RESULT_20261008.json"
SUMMARY = ROOT / "experiment/g12/G12_COMPRESS6_DEVELOPMENT_MANIFEST_20261008.json"


def verified_previous_failure() -> dict:
    path = ROOT/"experiment/g11/G11_COMPRESS6_RESULTS_20261008.json"
    original = json.loads(path.read_text())
    if original["report_digest"] != digest_of({
        k:v for k,v in original.items() if k!="report_digest"
    }):
        raise RuntimeError("prior frozen experiment report digest invalid")
    if original["fully_validated_unique_candidates"] != 0:
        raise RuntimeError("a previous passing candidate means no repair gap")
    if original["project"] != "Compress" or original["bug_id"] != 6:
        raise RuntimeError("unexpected previous development case")
    for arm in original["arms"].values():
        if arm["first_validated_rank"] is not None:
            raise RuntimeError("previous candidate batch has a winner")
    return {
        "report_digest": original["report_digest"],
        "candidate_budget": 8,
        "charged_candidate_executions": 8,
        "winner": None, "autonomous_passed": False,
        "schedule": {
            "scheduled_count": 8,
            "family_input_counts": {"learned": 0, "retained": 0, "scalar": 8},
            "family_scheduled_counts": {"scalar": 8},
        },
    }


def generate() -> list[dict]:
    source = _d4j_export(BUGGY, "dir.src.classes")[-1]
    focus = focus_files(BUGGY, source)
    favored = [path for path in focus if path.endswith("/ZipArchiveEntry.java")]
    # Source preference from previously exposed development diagnosis. The
    # candidate itself comes from the existing G11 planner, not a fixed patch.
    result = repair_strategist.generate(
        BUGGY, include_prefixes=[source], focus_paths=focus,
        max_candidates=80, per_family_budget=80, composition_fraction=0.4,
        source_balance_experimental=True,
        atomic_first_experimental=True,
        priority_focus_paths=favored,
    )
    if not result["candidates"]:
        raise RuntimeError("planner produced no repair candidates")
    return [result["candidates"][0]]


def evaluator(relative: str, content: str, preimage: str) -> dict:
    result = evaluate_unique(
        Path(relative), content, hashlib.sha256(content.encode()).hexdigest(),
        preimage,
    )
    # Normalize the existing independent Defects4J evaluator semantics.
    return {
        "compiled": bool(result.get("compiled")),
        "full_suite_ran": bool(result.get("compiled")) and result.get("failing_tests") is not None,
        "full_suite_pass": result.get("validated_full_suite") is True,
        "full_suite_failures": result.get("failing_tests"),
        "test_exit": result.get("test_exit"),
        "validator_error": result.get("error"),
        "test_output_sha256": result.get("test_output_sha256"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("freeze", "evaluate"))
    args = parser.parse_args()
    if RECEIPT.exists():
        raise RuntimeError("this development learning round has already been evaluated")
    prior = verified_previous_failure()
    candidates = generate()
    BASE.mkdir(parents=True, exist_ok=True)
    if args.phase == "freeze":
        frozen = freeze_training_search(
            root=BUGGY, candidates=candidates,
            previous_failure=prior, freeze_path=FREEZE,
            role="released_training", max_candidates=1,
        )
        manifest = {
            "schema": "genesis-g12-development-source-provenance-v1",
            "previous_failure_digest": prior["report_digest"],
            "candidate_source": "G11 repair strategist, source-priority development arm",
            "candidate_path": frozen["candidate_order"][0]["path"],
            "candidate_new_sha256": frozen["candidate_order"][0]["new_sha256"],
            "freeze_digest": frozen["freeze_digest"],
            "candidate_source_human_authored_semantics": True,
            "operator_synthesis_by_machine": "A6c source-diff template induction",
            "heldout_success": False,
        }
        SUMMARY.parent.mkdir(parents=True, exist_ok=True)
        SUMMARY.write_text(json.dumps({
            **manifest, "manifest_digest": digest_of(manifest),
        }, indent=2, sort_keys=True)+"\n")
        print("G12_DEV_FROZEN",frozen["freeze_digest"],flush=True)
        return
    if not FREEZE.exists() or not SUMMARY.exists():
        raise RuntimeError("must freeze and checkpoint candidate before evaluating")
    frozen=json.loads(FREEZE.read_text())
    summary=json.loads(SUMMARY.read_text())
    if summary["freeze_digest"] != frozen["freeze_digest"]:
        raise RuntimeError("signed development manifest mismatches frozen candidates")
    result=validate_and_learn(
        root=BUGGY, candidates=candidates, frozen=frozen,
        freeze_path=FREEZE, previous_failure=prior,
        evaluator=evaluator, memory_path=MEMORY,
        result_path=RECEIPT, role="released_training",
        context_lines=1,  # freeze original G12 development protocol
    )
    if not result["validated_operator_acquisition"]:
        raise RuntimeError("no full-suite-validated repair; no operator promoted")
    learned = self_extension.validate_memory(json.loads(MEMORY.read_text()))
    print("G12_DEV_VALIDATED",result["attempt_count"],
          "generations",learned["generation"],
          "operators",len(learned["operators"]),
          "operator_replay",result["validated_operator_acquisition"]["replay_verified_on_training_source"],
          "report",RECEIPT,flush=True)


if __name__ == "__main__":
    main()
