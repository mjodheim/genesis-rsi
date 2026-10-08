#!/usr/bin/env python3
"""Reproduce the G12 training-only bank from two sealed real development runs."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis.g12_training_bank import create_training_bank,validate_training_bank
from genesis import repair_strategist
from genesis.trust_root import digest_of

RUNS=[
    ("COMPRESS6",Path("/home/anthony/benchmarks/g12-development-compress6")),
    ("MATH53",Path("/home/anthony/benchmarks/g12-development-math53")),
]
BANK=ROOT/"experiment/g12/G12_TRAINING_OPERATOR_BANK_20261008.json"

def main():
    rounds=[]
    for key,folder in RUNS:
        receipt=json.loads((ROOT/f"experiment/g12/G12_{key}_DEVELOPMENT_RESULT_20261008.json").read_text())
        memory=json.loads((folder/"acquired_operator_memory.json").read_text())
        rounds.append((receipt,memory))
    bank=validate_training_bank(create_training_bank(rounds))
    if BANK.exists() and json.loads(BANK.read_text())!=bank:
        raise RuntimeError("immutable training bank would change")
    BANK.write_text(json.dumps(bank,indent=2,sort_keys=True)+"\n")
    print("BANK_CREATED",BANK,"source_rounds",bank["released_training_rounds"],
          "machine_distilled_operators",bank["learned_operator_count"],
          "digest",bank["bank_digest"],flush=True)

if __name__=="__main__":
    main()
