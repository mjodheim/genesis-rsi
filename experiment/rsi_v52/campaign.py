[Reading 111 lines from start (total: 111 lines, 0 remaining)]

"""One prospective V52 sustained abstraction-memory development assay."""
import argparse
import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v52 import bank, benchmark, freeze

DIRECTORY = ROOT / "results/rsi-v52/prospective-abstraction-20261005"
DEFAULT_OUTPUT = DIRECTORY / "REPORT.json"

ABSTRACT_TOP_K = 1
ABSTRACT_ONLY_WITHOUT_EXACT = True
ALLOWED_MODES = None


def adjudicate(results):
    aggregate = benchmark.aggregate(results)
    all_windows_positive = all(
        len(row["v52_first_discoveries_by_window"]) == bank.WINDOWS
        and all(value > 0 for value in row["v52_first_discoveries_by_window"].values())
        for row in results
    )
    per_seed_not_below_cold = all(
        row["v52"]["solved"] >= row["cold"]["solved"] for row in results
    )
    abstraction_exercised = all(
        row["v52"]["abstract_candidates_evaluated"] > 0
        and row["abstraction_contribution"]["uses"] > 0
        for row in results
    )
    predicates = {
        "all_committed_tasks_retained": (
            aggregate["tasks"] == len(bank.FRESH_SEEDS) * bank.WINDOWS * bank.TASKS_PER_WINDOW
        ),
        "all_seed_windows_keep_positive_first_discovery": all_windows_positive,
        "v52_aggregate_solved_at_least_v51": aggregate["v52_solved"] >= aggregate["v51_solved"],
        "v52_aggregate_solved_above_cold": aggregate["v52_solved"] > aggregate["cold_solved"],
        "v52_aggregate_cost_no_more_than_v51": (
            aggregate["v52_evaluations"] <= aggregate["v51_evaluations"]
        ),
        "no_seed_solved_regression_below_cold": per_seed_not_below_cold,
        "abstraction_reuse_and_feedback_exercised": abstraction_exercised,
    }
    positive = all(predicates.values())
    return {
        "schema": "mira-genesis-v52-prospective-abstraction-adjudication-v1",
        "predicates": predicates,
        "scoped_sustained_abstraction_assay_passed": positive,
        "verdict": (
            "POSITIVE_SCOPED_SUSTAINED_ABSTRACTION_ASSAY"
            if positive else "VALID_NEGATIVE_SCOPED_SUSTAINED_ABSTRACTION_ASSAY"
        ),
        "aggregate": aggregate,
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
    }


def run(*, isolated=False):
    freeze.verify()
    with tempfile.TemporaryDirectory(prefix="v52-prospective-") as temporary:
        root = Path(temporary)
        results = [
            benchmark.run(
                seed,
                root / str(seed),
                isolated=isolated,
                abstract_top_k=ABSTRACT_TOP_K,
                abstract_only_without_exact=ABSTRACT_ONLY_WITHOUT_EXACT,
                allowed_modes=ALLOWED_MODES,
                tasks=bank.stream(seed),
                scope="PROSPECTIVE_V52_PROJECT_AUTHORED_SUSTAINED_DEVELOPMENT",
            )
            for seed in bank.FRESH_SEEDS
        ]
    return {
        "schema": "mira-genesis-v52-prospective-abstraction-report-v1",
        "population_sha256": bank.population_sha256(),
        "fresh_population": True,
        "project_authored": True,
        "isolated": isolated,
        "configuration": {
            "abstract_top_k": ABSTRACT_TOP_K,
            "abstract_only_without_exact": ABSTRACT_ONLY_WITHOUT_EXACT,
            "allowed_modes": ALLOWED_MODES,
            "negative_recipe_feedback": "NO_QUALITY_GAIN_RETIRES_RECIPE_BELOW_RETRIEVAL_THRESHOLD",
            "inherited_max_evaluations_per_task": 14,
        },
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
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(report["adjudication"], sort_keys=True))


if __name__ == "__main__":
    main()

[executed on device: Mjodheim-Ubuntu-cx33 (915d6eb6-54f1-400c-8c12-a1e043b0a356)]