"""Prospective V53 freeze verification."""
import argparse
import json

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v53 import bank, engine

PATH = ROOT / "experiment/rsi_v53/V53_SCIENTIFIC_FREEZE.json"
APPARATUS_FILES = (
    "experiment/rsi_v53/engine.py",
    "experiment/rsi_v53/benchmark.py",
    "experiment/rsi_v53/bank.py",
    "experiment/rsi_v53/campaign.py",
    "experiment/rsi_v53/PROTOCOL.md",
)


def source_hashes():
    return {
        name: digest_bytes((ROOT / name).read_bytes())
        for name in APPARATUS_FILES
    }


def build():
    base = {
        "schema": "mira-genesis-v53-prospective-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_PROSPECTIVE_BEHAVIOR",
        "population_sha256": bank.population_sha256(),
        "seeds": list(bank.FRESH_SEEDS),
        "windows": bank.WINDOWS,
        "tasks_per_window": bank.TASKS_PER_WINDOW,
        "widths": list(range(3, 3 + bank.WINDOWS)),
        "configuration": {
            "scaffold_top_k": engine.SCAFFOLD_TOP_K,
            "scaffold_min_width": engine.SCAFFOLD_MIN_WIDTH,
            "scaffold_root_quality_max": engine.SCAFFOLD_ROOT_QUALITY_MAX,
            "scaffold_component_mode": "rotation",
            "scaffold_only_without_exact": True,
            "scaffold_replaces_whole_abstraction": True,
            "max_charged_evaluations_per_task": engine.MAX_EVALUATIONS,
        },
        "acceptance_predicates": [
            "all_committed_tasks_retained",
            "all_seed_windows_keep_positive_first_discovery",
            "v53_aggregate_solved_above_v52",
            "v53_aggregate_solved_above_cold",
            "v53_aggregate_cost_no_more_than_v52",
            "no_seed_solved_regression_below_cold",
            "scaffold_routing_exercised_on_every_seed",
            "new_horizon_windows_keep_positive_first_discovery",
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
        raise ValueError(
            "V53 prospective freeze differs from committed apparatus or population"
        )
    return True


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    value = build()
    if args.write:
        PATH.write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
        )
    else:
        verify(value)
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
