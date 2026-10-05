"""One prospective V53 sustained scaffold assay."""
import argparse
import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v53 import bank, benchmark, freeze

DIRECTORY = ROOT / "results/rsi-v53/prospective-scaffold-20261005"
DEFAULT_OUTPUT = DIRECTORY / "REPORT.json"


def adjudicate(results):
    aggregate = benchmark.aggregate(results)
    all_windows_positive = all(
        len(row["v53_first_discoveries_by_window"]) == bank.WINDOWS
        and all(value > 0 for value in row["v53_first_discoveries_by_window"].values())
        for row in results
    )
    no_seed_below_cold = all(
        row["v53"]["solved"] >= row["cold"]["solved"] for row in results
    )
    scaffold_exercised = all(
        row["v53"]["scaffold_routes"] > 0
        and row["v53"]["scaffold_candidates_evaluated"] > 0
        for row in results
    )
    new_horizon_positive = all(
        row["v53_first_discoveries_by_window"].get(str(window), 0) > 0
        for row in results
        for window in (12, 13)
    )
    predicates = {
        "all_committed_tasks_retained": (
            aggregate["tasks"]
            == len(bank.FRESH_SEEDS) * bank.WINDOWS * bank.TASKS_PER_WINDOW
        ),
        "all_seed_windows_keep_positive_first_discovery": all_windows_positive,
        "v53_aggregate_solved_above_v52": (
            aggregate["v53_solved"] > aggregate["v52_solved"]
        ),
        "v53_aggregate_solved_above_cold": (
            aggregate["v53_solved"] > aggregate["cold_solved"]
        ),
        "v53_aggregate_cost_no_more_than_v52": (
            aggregate["v53_evaluations"] <= aggregate["v52_evaluations"]
        ),
        "no_seed_solved_regression_below_cold": no_seed_below_cold,
        "scaffold_routing_exercised_on_every_seed": scaffold_exercised,
        "new_horizon_windows_keep_positive_first_discovery": new_horizon_positive,
    }
    positive = all(predicates.values())
    return {
        "schema": "mira-genesis-v53-prospective-scaffold-adjudication-v1",
        "predicates": predicates,
        "scoped_sustained_scaffold_assay_passed": positive,
        "verdict": (
            "POSITIVE_SCOPED_SUSTAINED_SCAFFOLD_ASSAY"
            if positive
            else "VALID_NEGATIVE_SCOPED_SUSTAINED_SCAFFOLD_ASSAY"
        ),
        "aggregate": aggregate,
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
    }


def run(*, isolated=False):
    freeze.verify()
    with tempfile.TemporaryDirectory(prefix="v53-prospective-") as temporary:
        root = Path(temporary)
        results = [
            benchmark.run(
                seed,
                root / str(seed),
                tasks=bank.stream(seed),
                isolated=isolated,
                scope="PROSPECTIVE_V53_PROJECT_AUTHORED_SUSTAINED_SCAFFOLD",
            )
            for seed in bank.FRESH_SEEDS
        ]
    return {
        "schema": "mira-genesis-v53-prospective-scaffold-report-v1",
        "population_sha256": bank.population_sha256(),
        "results": results,
        "adjudication": adjudicate(results),
        "claim_boundary": (
            "FINITE_PROJECT_AUTHORED_PROSPECTIVE_ASSAY_NOT_GENERAL_OPEN_ENDED_L9"
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = run(isolated=args.isolated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps(report["adjudication"], sort_keys=True))


if __name__ == "__main__":
    main()
