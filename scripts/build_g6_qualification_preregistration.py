"""Freeze G6 qualification before descendant generation and holdout reveal."""
from __future__ import annotations
import argparse, hashlib, json, subprocess
from pathlib import Path
from genesis.trust_root import digest_of

SCHEMA="genesis-g6-qualification-preregistration-v1"

def sha(path: Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--repository-root",type=Path,required=True)
    p.add_argument("--holdout-sha256",required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    root=a.repository_root.resolve()
    hold=a.holdout_sha256.strip().lower()
    g5=json.loads((root/"experiment/g5_qualification/RESULT.json").read_text())
    if g5["verdict"]!="G5_SCIENTIFIC_GATE_PASSED":
        raise SystemExit("G5 prerequisite not passed")
    parent=root/"genesis/operators/universal.py"
    evo=root/"genesis/evolution/component_evolution.py"
    payload={
      "schema":SCHEMA,
      "apparatus_commit":subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,check=True).stdout.strip(),
      "parent_component":{"component_id":"universal_operator_ir","path":"genesis/operators/universal.py","source_sha256":sha(parent)},
      "evolution_apparatus":{"path":"genesis/evolution/component_evolution.py","source_sha256":sha(evo),"external_model_calls":0},
      "prior_training_evidence":{"g5_result_digest":g5["result_digest"],"g5_result_commit":"e0a7e07c","allowed_source":"revealed G5 evidence plus deterministic safety decoys only"},
      "holdout":{"sha256":hold,"case_count":8,"contents_visible_to_lineage_before_descendant_freeze":False,"location_at_freeze":"external_to_repository"},
      "qualification_rule":{"required":[
        "holdout_sha256_matches_preregistered_identity",
        "descendant_source_differs_from_parent",
        "descendant_generated_by_frozen_evolution_apparatus",
        "descendant_frozen_before_holdout_reveal",
        "descendant_success_rate_exceeds_parent",
        "descendant_preserves_every_parent_success",
        "descendant_solves_at_least_7_of_8_hidden_cases",
        "descendant_uses_zero_external_model_calls",
        "descendant_stays_within_equal_candidate_budget",
        "reverting_winning_mutation_removes_gain"
      ],"pass_label":"G6_SCIENTIFIC_GATE_PASSED","fail_label":"G6_SCIENTIFIC_GATE_OPEN"},
      "claim_boundary":"Bounded project-defined G6 component-evolution qualification only; not G7, general RSI, AGI, ASI, or independent third-party validation."
    }
    payload["preregistration_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
