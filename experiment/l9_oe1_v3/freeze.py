"""Scientific freeze verifier for the L9-OE1 v3 qualification."""
from __future__ import annotations

import json

from experiment.l9_oe1_v3 import bank
from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes

PATH = ROOT / "experiment/l9_oe1_v3/L9_V3_FREEZE.json"

# Closed executable/source manifest. It intentionally binds transitive policy,
# sandbox, native-worker and evaluator dependencies, not only direct imports.
APPARATUS_FILES = (
    "experiment/l9_oe1_v3/__init__.py",
    "experiment/l9_oe1_v3/POPULATION.json",
    "experiment/l9_oe1_v3/PROTOCOL.md",
    "experiment/l9_oe1_v3/bank.py",
    "experiment/l9_oe1_v3/epoch.py",
    "experiment/l9_oe1_v3/campaign.py",
    "experiment/l9_oe1_v3/audit.py",
    "experiment/l9_oe1/coded_native.py",
    "experiment/rsi_v35/native.py",
    "experiment/rsi_v29/native_worker.py",
    "experiment/rsi_v36/engine.py",
    "experiment/rsi_v36/bank.py",
    "experiment/rsi_v27/engine.py",
    "experiment/rsi_v27/worker.py",
    "experiment/rsi_v31/programs.py",
    "experiment/rsi_v25/commitments.py",
    "experiment/rsi_v25/search_engine.py",
    "experiment/rsi_v23/sandbox_policy.py",
    "experiment/rsi_v23/policy_guard.py",
    "results/rsi-v30/target-20261001/G7_SELECTED_POLICY.py",
)


def source_hashes():
    missing = [name for name in APPARATUS_FILES if not (ROOT / name).is_file()]
    if missing:
        raise ValueError("V3 closed manifest missing files: " + ", ".join(missing))
    return {name: digest_bytes((ROOT / name).read_bytes()) for name in APPARATUS_FILES}


def build():
    base = {
        "schema": "mira-genesis-l9-oe1-v3-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_V3_BEHAVIOR",
        "seed": bank.QUALIFICATION_SEED,
        "population_file_sha256": bank.population_file_sha256(),
        "domains": list(("relational-sql", "regular-expressions", "structured-json", "binary-compression")),
        "epochs": bank.EPOCHS,
        "tasks_per_epoch": bank.TASKS_PER_EPOCH,
        "max_charged_evaluations_per_task": 14,
        "transfer_blocks": list(range(2, 11)),
        "arms": ["coded-archive", "archive-g7", "greedy-g7", "cold-g7"],
        "audit_policy": {
            "exact_ordered_task_hashes_required": True,
            "outcomes_recomputed_from_candidate_receipts": True,
            "every_retained_candidate_reexecuted": True,
            "terminal_coded_state_reverified": True,
            "complete_16_stream_set_required": True,
        },
        "source_sha256": source_hashes(),
    }
    return {**base, "freeze_sha256": digest(base)}


def load():
    return json.loads(PATH.read_text(encoding="utf-8"))


def verify():
    if load() != build():
        raise ValueError("L9-OE1 v3 freeze differs from committed closed apparatus")
    return True
