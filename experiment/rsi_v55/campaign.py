"""Prospective V55 feedback-diagnostic sustained assay."""
import argparse
import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v55 import bank, benchmark, freeze

DIRECTORY = ROOT / "results/rsi-v55/prospective-feedback-diagnostic-20261005"
DEFAULT_OUTPUT = DIRECTORY / "REPORT.json"


def adjudicate(results):
    aggregate = benchmark.aggregate(results)
    all_windows_positive = all(
        len(row["v55_first_discoveries_by_window"]) == bank.WINDOWS
        and all(
            value > 0
            for value in row["v55_first_discoveries_by_window"].values()
        )
        for row in results
    )
    no_seed_below_cold = all(
        row["v55"]["solved"] >= row["cold"]["solved"]
        for row in results
    )
    diagnostics_every_seed = all(
        row["v55"]["diagnostic_routes"] > 0
        for row in results
    )
    no_aborts = all(
        row["v55"]["diagnostic_aborts"] == 0
        for row in results
    )
    every_diagnostic_solves = all(
        row["v55"]["diagnostic_tasks_solved"]
        == row["v55"]["diagnostic_routes"]
        for row in results
    )
    no_diagnostic_regressions = all(
        row["diagnostic_contribution"][
            "solve_regressions_vs_v53"
        ] == 0
        for row in results
    )
    new_horizon_positive = all(
        row["v55_first_discoveries_by_window"].get(
            str(window), 0
        ) > 0
        for row in results
        for window in (14, 15, 16, 17)
    )

    predicates = {
        "all_committed_tasks_retained": (
            aggregate["tasks"]
            == len(bank.FRESH_SEEDS)
            * bank.WINDOWS
            * bank.TASKS_PER_WINDOW
        ),
        "all_seed_windows_keep_positive_first_discovery": (
            all_windows_positive
        ),
        "v55_aggregate_solved_above_v53": (
            aggregate["v55_solved"]
            > aggregate["v53_solved"]
        ),
        "v55_aggregate_solved_above_cold": (
            aggregate["v55_solved"]
            > aggregate["cold_solved"]
        ),
        "v55_aggregate_cost_no_more_than_v53": (
            aggregate["v55_evaluations"]
            <= aggregate["v53_evaluations"]
        ),
        "no_seed_solved_regression_below_cold": (
            no_seed_below_cold
        ),
        "diagnostic_routing_exercised_on_every_seed": (
            diagnostics_every_seed
        ),
        "diagnostic_aborts_zero": no_aborts,
        "every_diagnostic_route_solves": (
            every_diagnostic_solves
        ),
        "no_direct_diagnostic_solve_regression_vs_v53": (
            no_diagnostic_regressions
        ),
        "new_horizon_windows_keep_positive_first_discovery": (
            new_horizon_positive
        ),
    }
    positive = all(predicates.values())
    return {
        "schema": "mira-genesis-v55-prospective-adjudication-v1",
        "predicates": predicates,
        "scoped_sustained_feedback_diagnostic_assay_passed": positive,
        "verdict": (
            "POSITIVE_SCOPED_SUSTAINED_FEEDBACK_DIAGNOSTIC_ASSAY"
            if positive
            else "VALID_NEGATIVE_SCOPED_SUSTAINED_FEEDBACK_DIAGNOSTIC_ASSAY"
        ),
        "aggregate": aggregate,
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
    }


def run_seed(seed, *, isolated=False):
    freeze.verify()
    if seed not in bank.FRESH_SEEDS:
        raise ValueError("Uncommitted V55 prospective seed")
    with tempfile.TemporaryDirectory(
        prefix=f"v55-prospective-{seed}-"
    ) as temporary:
        return benchmark.run(
            seed,
            Path(temporary),
            tasks=bank.stream(seed),
            isolated=isolated,
            scope="PROSPECTIVE_V55_PROJECT_AUTHORED_FEEDBACK_DIAGNOSTIC",
        )


def build_report(results, *, isolated):
    ordered = sorted(results, key=lambda row: row["seed"])
    if [row["seed"] for row in ordered] != list(bank.FRESH_SEEDS):
        raise ValueError("V55 report does not contain every committed seed")
    return {
        "schema": "mira-genesis-v55-prospective-report-v1",
        "population_sha256": bank.population_sha256(),
        "fresh_population": True,
        "project_authored": True,
        "isolated": isolated,
        "results": ordered,
        "adjudication": adjudicate(ordered),
        "claim_boundary": (
            "FINITE_PROJECT_AUTHORED_PROSPECTIVE_ASSAY_NOT_GENERAL_OPEN_ENDED_L9"
        ),
    }


def run(*, isolated=False):
    return build_report(
        [
            run_seed(seed, isolated=isolated)
            for seed in bank.FRESH_SEEDS
        ],
        isolated=isolated,
    )


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--assemble", nargs="*", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    if args.seed is not None and args.assemble:
        raise ValueError("--seed and --assemble are mutually exclusive")

    if args.seed is not None:
        payload = {
            "schema": "mira-genesis-v55-prospective-seed-result-v1",
            "population_sha256": bank.population_sha256(),
            "isolated": args.isolated,
            "result": run_seed(args.seed, isolated=args.isolated),
        }
    elif args.assemble:
        seed_payloads = [
            json.loads(path.read_text())
            for path in args.assemble
        ]
        if not all(
            row.get("population_sha256") == bank.population_sha256()
            for row in seed_payloads
        ):
            raise ValueError("Seed report population mismatch")
        isolated = all(
            bool(row.get("isolated")) for row in seed_payloads
        )
        payload = build_report(
            [row["result"] for row in seed_payloads],
            isolated=isolated,
        )
    else:
        payload = run(isolated=args.isolated)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    )
    if "adjudication" in payload:
        print(json.dumps(payload["adjudication"], sort_keys=True))
    else:
        print(json.dumps({
            "seed": payload["result"]["seed"],
            "v55": payload["result"]["v55"],
            "v53": payload["result"]["v53"],
        }, sort_keys=True))


if __name__ == "__main__":
    main()
