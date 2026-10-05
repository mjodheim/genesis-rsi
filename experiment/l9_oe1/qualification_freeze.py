"""Scientific freeze verification for the prospective L9-OE1 qualification."""
from __future__ import annotations

import json

from experiment.l9_oe1 import qualification_bank
from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes

PATH = ROOT / "experiment/l9_oe1/L9_QUALIFICATION_FREEZE.json"

APPARATUS_FILES = (
    "experiment/l9_oe1/coded_native.py",
    "experiment/l9_oe1/qualification_bank.py",
    "experiment/l9_oe1/qualification_epoch.py",
    "experiment/l9_oe1/qualification_campaign.py",
    "experiment/l9_oe1/L9_QUALIFICATION_PROTOCOL.md",
    "experiment/rsi_v35/native.py",
    "experiment/rsi_v36/engine.py",
    "experiment/rsi_v36/bank.py",
)


def source_hashes():
    return {
        name: digest_bytes((ROOT / name).read_bytes())
        for name in APPARATUS_FILES
    }


def build():
    base = {
        "schema": "mira-genesis-l9-oe1-qualification-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_QUALIFICATION_BEHAVIOR",
        "population_sha256": qualification_bank.population_sha256(),
        "seed": qualification_bank.QUALIFICATION_SEED,
        "domains": [
            "relational-sql",
            "regular-expressions",
            "structured-json",
            "binary-compression",
        ],
        "epochs": qualification_bank.EPOCHS,
        "tasks_per_epoch": qualification_bank.TASKS_PER_EPOCH,
        "max_charged_evaluations_per_task": 14,
        "transfer_blocks": list(range(2, 11)),
        "arms": [
            "coded-archive",
            "archive-g7",
            "greedy-g7",
            "cold-g7",
        ],
        "source_sha256": source_hashes(),
    }
    return {**base, "freeze_sha256": digest(base)}


def load():
    return json.loads(PATH.read_text())


def verify():
    expected = build()
    actual = load()
    if actual != expected:
        raise ValueError("L9-OE1 qualification freeze differs from apparatus")
    return True
