"""Build a deterministic G10 discovery or hidden qualification bank."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import g10_task_bank

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--specialist-freeze",type=Path,required=True)
    p.add_argument("--stage",type=int,choices=(1,2,3),required=True)
    p.add_argument("--purpose",choices=("discovery","holdout"),required=True)
    p.add_argument("--seed",type=int,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    freeze=json.loads(a.specialist_freeze.read_text())
    bank=g10_task_bank.build_bank(
        freeze["specialist"],stage=a.stage,purpose=a.purpose,seed=a.seed
    )
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(bank,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
