"""Reproduce the V51 finite development comparison and write its report."""
import argparse
import json
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v51 import bank, benchmark

DEFAULT_OUTPUT = ROOT / "results/rsi-v51/structured-memory-development-20261005/REPORT.json"


def run(*, isolated=False):
    with tempfile.TemporaryDirectory(prefix="v51-memory-development-") as temporary:
        base = Path(temporary)
        rows = [
            benchmark.run(seed, base / f"{seed}.db", isolated=isolated)
            for seed in bank.DEVELOPMENT_SEEDS
        ]
    return {
        "schema": "mira-genesis-v51-structured-memory-development-report-v1",
        "population_sha256": bank.population_sha256(),
        "isolated": isolated,
        "results": rows,
        "aggregate": benchmark.aggregate(rows),
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
        "claim_boundary": "FINITE_PROJECT_AUTHORED_DEVELOPMENT_NOT_L9_QUALIFICATION",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--isolated", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    report = run(isolated=args.isolated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps(report["aggregate"], sort_keys=True))


if __name__ == "__main__":
    main()
