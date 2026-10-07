"""Freeze one prospective G10 stage after successor generation and before holdout reveal."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from genesis.evolution import recursive_chain
from genesis.trust_root import digest_of

SCHEMA="genesis-g10-stage-preregistration-v1"

APPARATUS_PATHS={
    "recursive_chain":"genesis/evolution/recursive_chain.py",
    "recursive_chain_executor":"genesis/runtime/recursive_chain_executor.py",
    "external_task_bank":"scripts/g10_task_bank.py",
    "external_evaluator":"scripts/g10_evaluator.py",
    "seed_builder":"scripts/build_g10_seed.py",
    "bank_builder":"scripts/build_g10_bank.py",
    "discovery_runner":"scripts/run_g10_discovery.py",
    "successor_builder":"scripts/build_g10_successor.py",
    "preregistration_builder":"scripts/build_g10_stage_preregistration.py",
    "stage_runner":"scripts/run_g10_stage.py",
    "chain_adjudicator":"scripts/run_g10_chain_adjudication.py",
}

STAGE_SHAPES={
    1:{"case_count":6,"new_group":"new_pair","new_count":4},
    2:{"case_count":8,"new_group":"new_scope_binding","new_count":4},
    3:{"case_count":10,"new_group":"new_iteration","new_count":4},
}

def _sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--repository-root",type=Path,required=True)
    p.add_argument("--successor-freeze",type=Path,required=True)
    p.add_argument("--discovery-run",type=Path,required=True)
    p.add_argument("--holdout-sha256",required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    root=a.repository_root.resolve()
    freeze=json.loads(a.successor_freeze.read_text())
    fp={k:v for k,v in freeze.items() if k!="freeze_digest"}
    if freeze.get("freeze_digest")!=digest_of(fp):
        raise SystemExit("G10 successor freeze digest does not reproduce")
    proposal=recursive_chain.validate_proposal(freeze["proposal"])
    stage=int(freeze["stage"])
    discovery=json.loads(a.discovery_run.read_text())
    if discovery["parent"]["discovery_evidence"]["discovery_digest"]!=proposal["discovery_digest"]:
        raise SystemExit("successor was not produced from supplied discovery")
    holdout_sha=a.holdout_sha256.strip().lower()
    if len(holdout_sha)!=64 or any(ch not in "0123456789abcdef" for ch in holdout_sha):
        raise SystemExit("invalid holdout SHA-256")
    shape=STAGE_SHAPES[stage]
    apparatus={name:{"path":rel,"source_sha256":_sha(root/rel)} for name,rel in APPARATUS_PATHS.items()}
    required=[
        "holdout_sha256_matches_preregistered_identity",
        "all_raw_tasks_fail_before_repair",
        "holdout_shape_matches_preregistration",
        "successor_proposal_is_content_addressed_and_valid",
        "successor_is_lineage_produced",
        "successor_was_generated_without_holdout_visibility",
        "successor_generation_is_exactly_parent_plus_one",
        "successor_strictly_improves_fresh_success",
        "successor_solves_every_fresh_case",
        "successor_preserves_every_parent_success",
        "parent_cannot_solve_new_capability_block",
        "successor_solves_entire_new_capability_block",
        "matched_candidate_budgets_are_identical",
        "all_profiles_use_zero_external_model_calls",
        "all_profiles_stay_within_matched_candidate_budget",
        "new_capability_ablation_reduces_to_parent",
        "current_generation_has_recursive_production_advantage_over_ancestor",
        "successor_was_induced_from_current_generation_discovery",
        "mutable_lineage_does_not_own_evaluator_or_verdict",
        "resource_accounting_records_candidate_cpu_and_wall_axes",
    ]
    payload={
        "schema":SCHEMA,
        "stage":stage,
        "preregistration_commit_parent":subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,check=True).stdout.strip(),
        "apparatus":apparatus,
        "successor":{
            "freeze_digest":freeze["freeze_digest"],
            "proposal_digest":proposal["proposal_digest"],
            "parent_profile_digest":proposal["parent_profile"]["profile_digest"],
            "successor_profile_digest":proposal["successor_profile"]["profile_digest"],
            "from_campaign_generation":proposal["parent_profile"]["campaign_generation"],
            "to_campaign_generation":proposal["successor_profile"]["campaign_generation"],
        },
        "discovery":{
            "run_digest":discovery["run_digest"],
            "bank_digest":discovery["bank_digest"],
            "parent_discovery_digest":discovery["parent"]["discovery_evidence"]["discovery_digest"],
            "ancestor_discovery_digest":(
                discovery["ancestor"]["discovery_evidence"]["discovery_digest"] if discovery.get("ancestor") else None
            ),
        },
        "recursive_advantage":{"required":stage>=2,"ancestor_present":discovery.get("ancestor") is not None},
        "holdout":{
            "sha256":holdout_sha,
            "case_count":shape["case_count"],
            "new_capability_group":shape["new_group"],
            "new_capability_case_count":shape["new_count"],
            "generated_after_successor_freeze":True,
            "contents_visible_to_lineage_at_freeze":False,
            "location_at_freeze":"external_to_repository",
        },
        "resource_budget":{
            "candidate_executions_per_case":6,
            "external_model_calls_per_case":0,
            "same_budget_for_parent_successor_and_discovery_comparison":True,
        },
        "authority":{
            "mutable_lineage_owns_evaluator_or_verdict":False,
            "same_frozen_evaluator_for_parent_and_successor":True,
            "promotion_authority":"external_trust_root",
        },
        "qualification_rule":{
            "required":required,
            "pass_label":f"G10_STAGE_{stage}_PASSED",
            "fail_label":f"G10_STAGE_{stage}_OPEN",
        },
        "claim_boundary":(
            f"Bounded project-defined G10 stage {stage} only. A pass establishes one additional "
            "causal successor transition inside the frozen synthetic software-repair composition assay. "
            "Stages 2 and 3 additionally require the current generation to outperform its direct ancestor "
            "at producing the discovery evidence needed for the next successor under the same budget. "
            "No single stage establishes G10, general RSI, AGI, ASI or independent third-party validation."
        ),
    }
    payload["preregistration_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
