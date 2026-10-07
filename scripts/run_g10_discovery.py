"""Execute a visible G10 discovery bank and preserve lineage-side evidence."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import g10_evaluator

def _run(root:Path,profile_path:Path,bank:dict,budget:int)->dict:
    profile=json.loads(profile_path.read_text())
    measurement=g10_evaluator.evaluate_profile(root,profile,bank,max_candidates_per_case=budget)
    evidence=g10_evaluator.build_discovery_evidence(measurement)
    return {"measurement":measurement,"discovery_evidence":evidence}

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--repository-root",type=Path,required=True)
    p.add_argument("--profile",type=Path,required=True)
    p.add_argument("--bank",type=Path,required=True)
    p.add_argument("--ancestor-profile",type=Path)
    p.add_argument("--budget",type=int,default=6)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    bank=json.loads(a.bank.read_text())
    payload={
        "schema":"genesis-g10-discovery-run-v1",
        "stage":bank["stage"],
        "bank_digest":bank["bank_digest"],
        "candidate_budget_per_case":a.budget,
        "parent":_run(a.repository_root,a.profile,bank,a.budget),
        "ancestor":None,
    }
    if a.ancestor_profile:
        payload["ancestor"]=_run(a.repository_root,a.ancestor_profile,bank,a.budget)
    from genesis.trust_root import digest_of
    payload["run_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
