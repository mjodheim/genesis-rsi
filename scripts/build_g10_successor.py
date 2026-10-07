"""Freeze one evidence-driven G10 successor before its fresh qualification holdout."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from genesis.evolution import recursive_chain
from genesis.trust_root import digest_of

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--parent-profile",type=Path,required=True)
    p.add_argument("--discovery-run",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    parent=json.loads(a.parent_profile.read_text())
    run=json.loads(a.discovery_run.read_text())
    evidence=run["parent"]["discovery_evidence"]
    proposal=recursive_chain.induce_successor(parent,evidence)
    payload={
        "schema":"genesis-g10-successor-freeze-v1",
        "stage":proposal["successor_profile"]["campaign_generation"],
        "parent_profile_digest":proposal["parent_profile"]["profile_digest"],
        "successor_profile_digest":proposal["successor_profile"]["profile_digest"],
        "proposal_digest":proposal["proposal_digest"],
        "discovery_digest":evidence["discovery_digest"],
        "proposal":proposal,
        "prospective_holdout_visible":False,
        "external_model_calls":0,
    }
    payload["freeze_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
