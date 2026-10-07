"""Adjudicate the complete prospectively qualified G0->G1->G2->G3 G10 chain."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from genesis.trust_root import digest_of

SCHEMA="genesis-g10-chain-result-v1"

def _load(path:Path)->dict:
    value=json.loads(path.read_text())
    payload={k:v for k,v in value.items() if k!="result_digest"}
    if value.get("result_digest")!=digest_of(payload):
        raise SystemExit(f"stage result digest does not reproduce: {path}")
    return value

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--stage1",type=Path,required=True)
    p.add_argument("--stage2",type=Path,required=True)
    p.add_argument("--stage3",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    stages=[_load(a.stage1),_load(a.stage2),_load(a.stage3)]
    chain_contiguous=all(
        stages[i]["successor_profile_digest"]==stages[i+1]["parent_profile_digest"]
        for i in range(2)
    )
    campaign_generations=[
        stages[0]["parent"]["campaign_generation"],
        stages[0]["successor"]["campaign_generation"],
        stages[1]["successor"]["campaign_generation"],
        stages[2]["successor"]["campaign_generation"],
    ]
    recursive_advantage=all(
        stages[i]["requirements"]["current_generation_has_recursive_production_advantage_over_ancestor"]
        for i in (1,2)
    )
    discovery_yield_advantage=all(
        stages[i]["discovery"]["ancestor"] is not None
        and stages[i]["discovery"]["parent"]["solved"]>stages[i]["discovery"]["ancestor"]["solved"]
        and stages[i]["discovery"]["parent"]["candidate_executions"]<stages[i]["discovery"]["ancestor"]["candidate_executions"]
        for i in (1,2)
    )
    requirements={
        "all_three_prospective_stage_gates_pass":all(item["gate_passed"] for item in stages),
        "chain_is_content_addressed_and_contiguous":chain_contiguous,
        "campaign_generations_are_exactly_0_1_2_3":campaign_generations==[0,1,2,3],
        "every_child_strictly_improves_on_fresh_evidence":all(
            item["successor"]["solved"]>item["parent"]["solved"] for item in stages
        ),
        "every_child_preserves_every_parent_success":all(
            item["requirements"]["successor_preserves_every_parent_success"] for item in stages
        ),
        "recursive_production_advantage_is_causal_at_transitions_2_and_3":recursive_advantage,
        "recursive_production_advantage_improves_yield_and_candidate_cost":discovery_yield_advantage,
        "all_runtime_and_generation_external_model_calls_are_zero":all(
            item["external_model_calls"]==0
            and item["parent"]["external_model_calls"]==0
            and item["successor"]["external_model_calls"]==0
            for item in stages
        ),
        "mutable_lineage_never_owns_evaluator_or_verdict":all(
            item["requirements"]["mutable_lineage_does_not_own_evaluator_or_verdict"] for item in stages
        ),
    }
    gate=all(requirements.values())
    payload={
        "schema":SCHEMA,
        "stage_result_digests":[item["result_digest"] for item in stages],
        "profile_chain":[
            stages[0]["parent_profile_digest"],
            stages[0]["successor_profile_digest"],
            stages[1]["successor_profile_digest"],
            stages[2]["successor_profile_digest"],
        ],
        "campaign_generations":campaign_generations,
        "stage_scores":[
            {
                "stage":item["stage"],
                "parent_solved":item["parent"]["solved"],
                "successor_solved":item["successor"]["solved"],
                "case_count":item["successor"]["case_count"],
            }
            for item in stages
        ],
        "recursive_production_comparisons":[
            {
                "stage":item["stage"],
                "current_generation_solved":item["discovery"]["parent"]["solved"],
                "ancestor_solved":item["discovery"]["ancestor"]["solved"],
                "current_generation_candidate_executions":item["discovery"]["parent"]["candidate_executions"],
                "ancestor_candidate_executions":item["discovery"]["ancestor"]["candidate_executions"],
            }
            for item in stages[1:]
        ],
        "requirements":requirements,
        "gate_passed":gate,
        "verdict":"G10_SCIENTIFIC_GATE_PASSED" if gate else "G10_SCIENTIFIC_GATE_OPEN",
        "claim_boundary":(
            "A pass establishes a bounded project-defined recursive self-improvement chain in the "
            "frozen synthetic software-repair composition assay: three successive causal improvements, "
            "with the inherited machinery of generations 1 and 2 required to produce the evidence for "
            "their next successors under matched budgets. This supports a domain-bounded RSI claim for "
            "this assay only. It does not establish general RSI, AGI, ASI, open-world autonomy, or "
            "independent third-party validation."
        ),
    }
    payload["result_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0 if gate else 2

if __name__=="__main__":
    raise SystemExit(main())
