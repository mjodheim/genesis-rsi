#!/usr/bin/env python3
"""Second G12 automatic operator retention from already exposed Math-53.

The candidate generation family was written in G11; a machine-induced A6c
structural operator can be acquired automatically only after the isolated
full project tests pass. Never call this a second independent RSI generation.
"""
from __future__ import annotations

import argparse
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
from scripts.g11_three_repo_repair_eval import (
    paths_for_case, validate, _d4j_export
)

BUGGY = Path("/home/anthony/benchmarks/g11-fresh-three-20261008/Math-53-buggy")
BASE = Path("/home/anthony/benchmarks/g12-development-math53")
FREEZE = BASE / "frozen_candidates.json"
MEMORY = BASE / "acquired_operator_memory.json"
RECEIPT = ROOT / "experiment/g12/G12_MATH53_DEVELOPMENT_RESULT_20261008.json"
MANIFEST = ROOT / "experiment/g12/G12_MATH53_DEVELOPMENT_MANIFEST_20261008.json"


def previous_failure():
    prior = json.loads(
        (ROOT / "experiment/g11/G11_3REPO_RESULTS_20261008.json").read_text()
    )
    digest = prior["result_digest"]
    if digest != digest_of({k:v for k,v in prior.items() if k!="result_digest"}):
        raise RuntimeError("earlier results tampered")
    case = next(c for c in prior["cases"]
                if c["project"]=="Math" and c["bug_id"]==53)
    if case["full_suite_valid_unique_candidates"] or any(
        a["first_passing_rank"] is not None for a in case["arms"].values()
    ):
        raise RuntimeError("no original candidate failure")
    return {
        "report_digest": digest,
        "winner": None, "autonomous_passed": False,
        "candidate_budget": 8, "charged_candidate_executions": 8,
        "schedule": {
            "scheduled_count": 8,
            "family_input_counts": {"retained":0,"learned":0,"scalar":8},
            "family_scheduled_counts": {"scalar":8},
        },
    }


def propose():
    prefix = _d4j_export(BUGGY,"dir.src.classes")[-1]
    focus = paths_for_case("Math",53,BUGGY,prefix)
    result = repair_strategist.generate(
        BUGGY, include_prefixes=[prefix], focus_paths=focus,
        max_candidates=80, per_family_budget=80,
        composition_fraction=0.4,
        source_balance_experimental=True, atomic_first_experimental=True,
        sibling_guard_experimental=True,
        priority_focus_paths=[p for p in focus if p.endswith("/Complex.java")],
    )
    if not result["candidates"]:
        raise RuntimeError("no candidate")
    return [result["candidates"][0]]


def evaluator(relative, changed, original_sha):
    triggers = [
        line[4:].strip() for line in (BUGGY/"failing_tests").read_text().splitlines()
        if line.startswith("--- ")
    ]
    return validate(BUGGY,relative,changed,original_sha,triggers)


def run(phase):
    if RECEIPT.exists():
        raise RuntimeError("already evaluated development round")
    prior = previous_failure()
    candidates = propose()
    BASE.mkdir(parents=True,exist_ok=True)
    if phase=="freeze":
        frozen = freeze_training_search(
            root=BUGGY,candidates=candidates,previous_failure=prior,
            freeze_path=FREEZE,role="released_training",max_candidates=1,
        )
        payload={
            "schema":"genesis-g12-math53-development-manifest-v1",
            "previous_failure_digest":prior["report_digest"],
            "candidate_freeze_digest":frozen["freeze_digest"],
            "candidate_source":"G11 assistant-authored sibling-guard generic family",
            "planned_operator_names":list(candidates[0]["plan"]["component_operators"]),
            "candidate_source_sha256":frozen["candidate_order"][0]["new_sha256"],
            "case_is_already_exposed":True,
            "human_reference_patch_seen":False,
        }
        MANIFEST.write_text(json.dumps({
            **payload,"manifest_digest":digest_of(payload),
        },indent=2,sort_keys=True)+"\n")
        print("MATH53_G12_DEV_FROZEN",frozen["freeze_digest"],flush=True)
        return
    frozen=json.loads(FREEZE.read_text())
    summary=json.loads(MANIFEST.read_text())
    if summary["manifest_digest"] != digest_of({
        k:v for k,v in summary.items() if k!="manifest_digest"
    }):
        raise RuntimeError("provenance digest error")
    if summary["candidate_freeze_digest"] != frozen["freeze_digest"]:
        raise RuntimeError("invalid frozen candidate")
    result=validate_and_learn(
        root=BUGGY,candidates=candidates,frozen=frozen,
        freeze_path=FREEZE,previous_failure=prior,
        evaluator=evaluator,memory_path=MEMORY,result_path=RECEIPT,
        role="released_training",context_lines=1,
    )
    if not result["validated_operator_acquisition"]:
        raise RuntimeError("no validated candidate to learn")
    m=self_extension.validate_memory(json.loads(MEMORY.read_text()))
    print("MATH53_G12_DEV_VALIDATED",
        "generation",m["generation"],"operators",len(m["operators"]),
        "candidate_validation_count",result["attempt_count"],
        "result",RECEIPT,flush=True)


if __name__=="__main__":
    arg=argparse.ArgumentParser()
    arg.add_argument("phase",choices=("freeze","evaluate"))
    run(arg.parse_args().phase)
