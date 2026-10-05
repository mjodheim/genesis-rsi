"""Prospective V55 freeze verification."""
import argparse
import json

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v55 import bank, engine

PATH = ROOT / "experiment/rsi_v55/V55_SCIENTIFIC_FREEZE.json"
APPARATUS_FILES = (
    "experiment/rsi_v55/diagnostics.py",
    "experiment/rsi_v55/engine.py",
    "experiment/rsi_v55/benchmark.py",
    "experiment/rsi_v55/bank.py",
    "experiment/rsi_v55/campaign.py",
    "experiment/rsi_v55/PROTOCOL.md",
)


def source_hashes():
    return {
        name: digest_bytes((ROOT / name).read_bytes())
        for name in APPARATUS_FILES
    }


def build():
    base = {
        "schema": "mira-genesis-v55-prospective-freeze-v1",
        "status": "FROZEN_BEFORE_FIRST_PROSPECTIVE_BEHAVIOR",
        "population_sha256": bank.population_sha256(),
        "seeds": list(bank.FRESH_SEEDS),
        "windows": bank.WINDOWS,
        "tasks_per_window": bank.TASKS_PER_WINDOW,
        "widths": list(range(3, 3 + bank.WINDOWS)),
        "configuration": {
            "diagnostic_min_width": engine.DIAGNOSTIC_MIN_WIDTH,
            "diagnostic_sparse_mask_max_bits": 2,
            "max_charged_evaluations_per_task": (
                engine.MAX_EVALUATIONS
            ),
            "g7_requests": engine.CAPS.requests,
            "g7_rounds": engine.CAPS.rounds,
            "g7_parallelism": engine.CAPS.parallelism,
            "g7_mutation_depth": engine.CAPS.mutation_depth,
        },
        "acceptance_predicates": [
            "all_committed_tasks_retained",
            "all_seed_windows_keep_positive_first_discovery",
            "v55_aggregate_solved_above_v53",
            "v55_aggregate_solved_above_cold",
            "v55_aggregate_cost_no_more_than_v53",
            "no_seed_solved_regression_below_cold",
            "diagnostic_routing_exercised_on_every_seed",
            "diagnostic_aborts_zero",
            "every_diagnostic_route_solves",
            "no_direct_diagnostic_solve_regression_vs_v53",
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
            "V55 prospective freeze differs from committed apparatus or population"
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
