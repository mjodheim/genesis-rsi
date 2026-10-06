"""Scientific freeze verifier for the materialized L9-OE1 v2 qualification."""
from __future__ import annotations
import json
from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.l9_oe1_v2 import bank

PATH=ROOT/"experiment/l9_oe1_v2/L9_V2_FREEZE.json"
APPARATUS_FILES=(
 "experiment/l9_oe1_v2/POPULATION.json",
 "experiment/l9_oe1_v2/bank.py",
 "experiment/l9_oe1_v2/epoch.py",
 "experiment/l9_oe1_v2/campaign.py",
 "experiment/l9_oe1_v2/PROTOCOL.md",
 "experiment/l9_oe1/coded_native.py",
 "experiment/rsi_v35/native.py",
 "experiment/rsi_v36/engine.py",
 "experiment/rsi_v36/bank.py",
)

def source_hashes():
    return {name:digest_bytes((ROOT/name).read_bytes()) for name in APPARATUS_FILES}

def build():
    base={
      "schema":"mira-genesis-l9-oe1-v2-freeze-v1",
      "status":"FROZEN_BEFORE_FIRST_V2_BEHAVIOR",
      "seed":bank.QUALIFICATION_SEED,
      "population_file_sha256":bank.population_file_sha256(),
      "domains":["relational-sql","regular-expressions","structured-json","binary-compression"],
      "epochs":bank.EPOCHS,"tasks_per_epoch":bank.TASKS_PER_EPOCH,
      "max_charged_evaluations_per_task":14,
      "transfer_blocks":list(range(2,11)),
      "arms":["coded-archive","archive-g7","greedy-g7","cold-g7"],
      "source_sha256":source_hashes(),
    }
    return {**base,"freeze_sha256":digest(base)}

def load(): return json.loads(PATH.read_text())
def verify():
    if load()!=build(): raise ValueError("L9-OE1 v2 freeze differs from committed apparatus")
    return True
