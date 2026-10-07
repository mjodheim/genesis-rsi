"""Build the G10 campaign seed from the qualified G9 successor."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from genesis.evolution import recursive_chain

def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--g9-successor-freeze",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    seed=recursive_chain.build_seed_profile(json.loads(a.g9_successor_freeze.read_text()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(seed,indent=2,sort_keys=True)+"\n")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
