"""Run one prospectively frozen G10 recursive-successor qualification stage."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from genesis.evolution import recursive_chain
from genesis.trust_root import digest_of
import g10_evaluator

RESULT_SCHEMA="genesis-g10-stage-result-v1"

def _sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--repository-root",type=Path,required=True)
    p.add_argument("--preregistration",type=Path,required=True)
    p.add_argument("--successor-freeze",type=Path,required=True)
    p.add_argument("--discovery-run",type=Path,required=True)
    p.add_argument("--holdout",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    root=a.repository_root.resolve()
    prereg=json.loads(a.preregistration.read_text())
    pp={k:v for k,v in prereg.items() if k!="preregistration_digest"}
    if prereg.get("preregistration_digest")!=digest_of(pp):
        raise SystemExit("G10 preregistration digest does not reproduce")
    freeze=json.loads(a.successor_freeze.read_text())
    fp={k:v for k,v in freeze.items() if k!="freeze_digest"}
    if freeze.get("freeze_digest")!=digest_of(fp):
        raise SystemExit("G10 successor freeze digest does not reproduce")
    proposal=recursive_chain.validate_proposal(freeze["proposal"])
    if proposal["proposal_digest"]!=prereg["successor"]["proposal_digest"]:
        raise SystemExit("G10 proposal differs from preregistration")
    discovery=json.loads(a.discovery_run.read_text())
    if discovery.get("run_digest")!=prereg["discovery"]["run_digest"]:
        raise SystemExit("G10 discovery run differs from preregistration")

    for label,record in prereg["apparatus"].items():
        if _sha(root/record["path"])!=record["source_sha256"]:
            raise SystemExit(f"G10 frozen apparatus changed: {label}")

    holdout_bytes=a.holdout.read_bytes()
    holdout_sha=hashlib.sha256(holdout_bytes).hexdigest()
    if holdout_sha!=prereg["holdout"]["sha256"]:
        raise SystemExit("G10 holdout SHA-256 differs from preregistration")
    holdout=json.loads(holdout_bytes)
    stage=int(prereg["stage"])
    budget=int(prereg["resource_budget"]["candidate_executions_per_case"])
    parent_profile=proposal["parent_profile"]
    successor_profile=proposal["successor_profile"]

    raw=g10_evaluator.raw_failures(holdout)
    parent=g10_evaluator.evaluate_profile(root,parent_profile,holdout,max_candidates_per_case=budget)
    successor=g10_evaluator.evaluate_profile(root,successor_profile,holdout,max_candidates_per_case=budget)
    parent_ids=g10_evaluator.pass_ids(parent)
    successor_ids=g10_evaluator.pass_ids(successor)
    new_group=prereg["holdout"]["new_capability_group"]

    parent_discovery=discovery["parent"]["measurement"]
    ancestor_discovery=(discovery.get("ancestor") or {}).get("measurement")
    recursive_required=bool(prereg["recursive_advantage"]["required"])
    recursive_advantage=(
        not recursive_required
        or (
            ancestor_discovery is not None
            and parent_discovery["bank_digest"]==ancestor_discovery["bank_digest"]
            and parent_discovery["candidate_budget_per_case"]==ancestor_discovery["candidate_budget_per_case"]
            and parent_discovery["solved"]>ancestor_discovery["solved"]
            and ancestor_discovery["solved"]==0
            and parent_discovery["candidate_executions"]<ancestor_discovery["candidate_executions"]
        )
    )

    requirements={
        "holdout_sha256_matches_preregistered_identity":holdout_sha==prereg["holdout"]["sha256"],
        "all_raw_tasks_fail_before_repair":all(not item["passed"] for item in raw),
        "holdout_shape_matches_preregistration":(
            holdout["stage"]==stage
            and holdout["purpose"]=="holdout"
            and holdout["case_count"]==prereg["holdout"]["case_count"]
        ),
        "successor_proposal_is_content_addressed_and_valid":freeze["proposal_digest"]==proposal["proposal_digest"],
        "successor_is_lineage_produced":proposal["lineage_produced"] is True,
        "successor_was_generated_without_holdout_visibility":freeze["prospective_holdout_visible"] is False,
        "successor_generation_is_exactly_parent_plus_one":(
            successor_profile["campaign_generation"]==parent_profile["campaign_generation"]+1
            and successor_profile["lineage_generation"]==parent_profile["lineage_generation"]+1
        ),
        "successor_strictly_improves_fresh_success":successor["solved"]>parent["solved"],
        "successor_solves_every_fresh_case":successor["solved"]==holdout["case_count"],
        "successor_preserves_every_parent_success":parent_ids<=successor_ids,
        "parent_cannot_solve_new_capability_block":parent["group_solved"].get(new_group,0)==0,
        "successor_solves_entire_new_capability_block":successor["group_solved"].get(new_group,0)==prereg["holdout"]["new_capability_case_count"],
        "matched_candidate_budgets_are_identical":parent["candidate_budget_per_case"]==successor["candidate_budget_per_case"]==budget,
        "all_profiles_use_zero_external_model_calls":parent["external_model_calls"]==successor["external_model_calls"]==0,
        "all_profiles_stay_within_matched_candidate_budget":parent["within_candidate_budget"] and successor["within_candidate_budget"],
        "new_capability_ablation_reduces_to_parent":(
            successor_profile["base_system_profile"]==parent_profile["base_system_profile"]
            and proposal["material_change"]["from_capability_digest"]==parent_profile["recursive_capability"]["capability_digest"]
            and proposal["material_change"]["to_capability_digest"]==successor_profile["recursive_capability"]["capability_digest"]
        ),
        "current_generation_has_recursive_production_advantage_over_ancestor":recursive_advantage,
        "successor_was_induced_from_current_generation_discovery":(
            proposal["discovery_digest"]==discovery["parent"]["discovery_evidence"]["discovery_digest"]
        ),
        "mutable_lineage_does_not_own_evaluator_or_verdict":prereg["authority"]["mutable_lineage_owns_evaluator_or_verdict"] is False,
        "resource_accounting_records_candidate_cpu_and_wall_axes":all(
            all(key in item for key in ("candidate_executions","controller_cpu_process_time_ns","wall_time_seconds"))
            for item in (parent,successor)
        ),
    }
    gate=all(requirements.values())
    payload={
        "schema":RESULT_SCHEMA,
        "stage":stage,
        "preregistration_digest":prereg["preregistration_digest"],
        "successor_freeze_digest":freeze["freeze_digest"],
        "proposal_digest":proposal["proposal_digest"],
        "parent_profile_digest":parent_profile["profile_digest"],
        "successor_profile_digest":successor_profile["profile_digest"],
        "holdout":{"sha256":holdout_sha,"bank_digest":holdout["bank_digest"],"case_count":holdout["case_count"],"raw_cases":raw},
        "discovery":{"run_digest":discovery["run_digest"],"parent":parent_discovery,"ancestor":ancestor_discovery},
        "parent":parent,
        "successor":successor,
        "requirements":requirements,
        "gate_passed":gate,
        "verdict":prereg["qualification_rule"]["pass_label"] if gate else prereg["qualification_rule"]["fail_label"],
        "external_model_calls":0,
        "claim_boundary":prereg["claim_boundary"],
    }
    payload["result_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0 if gate else 2

if __name__=="__main__":
    raise SystemExit(main())
