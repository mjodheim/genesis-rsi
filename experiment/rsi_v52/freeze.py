"""Prospective V52 freeze verification."""
import json
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v52 import bank

PATH = ROOT / "experiment/rsi_v52/V52_SCIENTIFIC_FREEZE.json"
APPARATUS_FILES = (
    "experiment/rsi_v52/abstractions.py",
    "experiment/rsi_v52/engine.py",
    "experiment/rsi_v52/benchmark.py",
    "experiment/rsi_v52/bank.py",
    "experiment/rsi_v52/campaign.py",
    "experiment/rsi_v52/PROTOCOL.md",
)


def source_hashes():
    return {
        name: digest_bytes((ROOT / name).read_bytes())
        for name in APPARATUS_FILES
    }


def build():
    base = {
        "schema": "mira-genesis-v52-prospective-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_PROSPECTIVE_BEHAVIOR",
        "population_sha256": bank.population_sha256(),
        "seeds": list(bank.FRESH_SEEDS),
        "windows": bank.WINDOWS,
        "tasks_per_window": bank.TASKS_PER_WINDOW,
        "widths": list(range(3, 3 + bank.WINDOWS)),
        "configuration": {
            "abstract_top_k": 1,
            "abstract_only_without_exact": True,
            "allowed_modes": None,
            "recipe_failure_policy": "NO_QUALITY_GAIN_STRONG_NEGATIVE_UPDATE",
            "max_charged_evaluations_per_task": 14,
        },
        "acceptance_predicates": [
            "all_committed_tasks_retained",
            "all_seed_windows_keep_positive_first_discovery",
            "v52_aggregate_solved_at_least_v51",
            "v52_aggregate_solved_above_cold",
            "v52_aggregate_cost_no_more_than_v51",
            "no_seed_solved_regression_below_cold",
            "abstraction_reuse_and_feedback_exercised",
        ],
        "source_sha256": source_hashes(),
    }
    return {**base, "freeze_sha256": digest(base)}


def load():
    return json.loads(PATH.read_text())


def verify(value=None):
    value = load() if value is None else value
    expected = build()
    if value != expected:
        raise ValueError("V52 prospective freeze differs from committed apparatus or population")
    return True
