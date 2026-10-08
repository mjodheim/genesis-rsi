#!/usr/bin/env python3
"""V2.1 phase-separated experiment on EXPOSED Math-53, not a blind repair.

The proposal is synthesized and persisted BEFORE the independent Defects4J
compiler/full-suite evaluator runs. No human fix or fixed checkout is read.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis.trust_root import digest_of
from genesis.v2.semantic_dsl import propose, compile_hypothesis
from scripts.g11_three_repo_repair_eval import validate

BUGGY=Path("/home/anthony/benchmarks/g11-fresh-three-20261008/Math-53-buggy")
RELATIVE="src/main/java/org/apache/commons/math/complex/Complex.java"
FREEZE=ROOT/"experiment/v2/V21_MATH53_PROPOSAL_FREEZE_20261008.json"
RESULT=ROOT/"experiment/v2/V21_MATH53_DEVELOPMENT_VALIDATION_20261008.json"


def proposal():
    found=propose(BUGGY,RELATIVE,max_hypotheses=8)
    if found["hypothesis_count"]!=1:
        raise RuntimeError("unexpected number of source-derived hypotheses")
    plan=compile_hypothesis(BUGGY,found["proposals"][0])
    meta={
        "schema":"genesis-v21-real-development-freeze-v1",
        "project":"Math",
        "bug_id":53,
        "already_exposed_training_case":True,
        "source_relative_path":RELATIVE,
        "source_sha256":plan["source_sha256"],
        "proposal_index_digest":found["proposal_digest"],
        "hypothesis":found["proposals"][0],
        "compiled_candidate_digest":plan["compiled_candidate_digest"],
        "candidate_sha256":plan["candidate_sha256"],
        "generator_source":"bounded_source_peer_contract_grammar",
        "candidate_generated_before_evaluator":True,
        "human_reference_patch_seen":False,
        "independent_unseen_holdout":False,
        "language":"java",
    }
    return {**meta,"freeze_digest":digest_of(meta)},plan


def execute(mode:str):
    frozen,plan=proposal()
    if mode=="freeze":
        if RESULT.exists():
            raise RuntimeError("evaluation already completed")
        if FREEZE.exists() and json.loads(FREEZE.read_text())!=frozen:
            raise RuntimeError("cannot overwrite another development hypothesis")
        FREEZE.write_text(json.dumps(frozen,sort_keys=True,indent=2)+"\n")
        print("V21_HYPOTHESIS_FROZEN",frozen["freeze_digest"],flush=True)
        return
    if not FREEZE.is_file() or json.loads(FREEZE.read_text())!=frozen:
        raise RuntimeError("candidate must match the previously frozen plan")
    if RESULT.exists():
        raise RuntimeError("result cannot be overwritten")
    public_failures=[
        line[4:].strip() for line in (BUGGY/"failing_tests").read_text().splitlines()
        if line.startswith("--- ")
    ]
    outcome=validate(BUGGY,RELATIVE,plan["content_utf8"],plan["source_sha256"],public_failures)
    body={
        "schema":"genesis-v21-real-development-outcome-v1",
        "candidate_freeze_digest":frozen["freeze_digest"],
        "reported_project":"Math",
        "reported_bug_id":53,
        "validator_result":outcome,
        "compiled":outcome.get("compiled") is True,
        "full_suite_pass":outcome.get("full_suite_pass") is True,
        "source_role":"already_exposed_development",
        "independent_unseen_repairs":0,
        "semantic_grammar_human_engineered":True,
        "proposal_derived_before_evaluator_run":True,
    }
    result={**body,"result_digest":digest_of(body)}
    RESULT.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("V21_EXPOSED_MATH53_FULL_SUITE",result["full_suite_pass"],
          "compiled",result["compiled"],"failures",outcome.get("full_suite_failures"),
          "result_digest",result["result_digest"],flush=True)

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("freeze","evaluate"))
    execute(parser.parse_args().phase)
