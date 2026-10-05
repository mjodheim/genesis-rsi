"""Prospective L9-OE1 qualification campaign and frozen adjudication."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys

from experiment.l9_oe1 import qualification_bank
from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v35 import native

ARMS = ("coded-archive", "archive-g7", "greedy-g7", "cold-g7")
TRANSFER_EPOCHS = tuple(range(3, qualification_bank.EPOCHS))


def _run_stream(arm, domain, directory):
    stream_dir = directory / arm / domain
    stream_dir.mkdir(parents=True, exist_ok=True)
    state_path = stream_dir / "state.json"
    records = []
    previous_after = None

    for epoch in range(qualification_bank.EPOCHS):
        output = stream_dir / f"epoch-{epoch:02d}.json"
        command = [
            sys.executable,
            "-m",
            "experiment.l9_oe1.qualification_epoch",
            "--arm",
            arm,
            "--domain",
            domain,
            "--epoch",
            str(epoch),
            "--state",
            str(state_path),
            "--output",
            str(output),
        ]

        environment = {
            **os.environ,
            "PYTHONHASHSEED": "0",
            "LC_ALL": "C",
        }
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=900,
        )
        if result.returncode:
            raise RuntimeError(
                f"qualification epoch failed {arm}/{domain}/{epoch}: "
                + result.stderr[-1000:]
            )

        row = json.loads(output.read_text())
        if previous_after is not None and row["state_before_sha256"] != previous_after:
            raise ValueError("Fresh-process state digest mismatch")
        previous_after = row["state_after_sha256"]
        records.append(row)

    return {
        "arm": arm,
        "domain": domain,
        "epochs": records,
    }


def _transfer_rows(stream):
    return [
        row for row in stream["epochs"]
        if row["epoch"] in TRANSFER_EPOCHS
    ]


def _solve_rate(rows):
    tasks = sum(row["tasks"] for row in rows)
    return sum(row["solved"] for row in rows) / tasks if tasks else 0.0


def _evals(rows):
    return sum(row["evaluations"] for row in rows)


def adjudicate(streams):
    by_key = {
        (stream["arm"], stream["domain"]): stream
        for stream in streams
    }

    def rows(arm, domain, transfer=False):
        stream = by_key[(arm, domain)]
        return _transfer_rows(stream) if transfer else stream["epochs"]

    coded_transfer = [
        row
        for domain in native.DOMAINS
        for row in rows("coded-archive", domain, transfer=True)
    ]
    archive_transfer = [
        row
        for domain in native.DOMAINS
        for row in rows("archive-g7", domain, transfer=True)
    ]
    greedy_transfer = [
        row
        for domain in native.DOMAINS
        for row in rows("greedy-g7", domain, transfer=True)
    ]
    cold_transfer = [
        row
        for domain in native.DOMAINS
        for row in rows("cold-g7", domain, transfer=True)
    ]

    expected_stream_tasks = (
        qualification_bank.EPOCHS * qualification_bank.TASKS_PER_EPOCH
    )
    all_records = all(
        len(stream["epochs"]) == qualification_bank.EPOCHS
        and sum(row["tasks"] for row in stream["epochs"]) == expected_stream_tasks
        for stream in streams
    )

    all_caps = all(
        row["max_task_evaluations"] <= 14
        for stream in streams
        for row in stream["epochs"]
    )

    coded_epoch_domain = all(
        row["solved"] / row["tasks"] >= 0.90
        and row["first_solving_semantics"] >= 4
        for domain in native.DOMAINS
        for row in rows("coded-archive", domain, transfer=True)
    )

    coded_rate = _solve_rate(coded_transfer)
    archive_rate = _solve_rate(archive_transfer)
    greedy_rate = _solve_rate(greedy_transfer)
    cold_rate = _solve_rate(cold_transfer)

    coded_vs_archive_domains = all(
        _solve_rate(rows("coded-archive", domain, transfer=True))
        - _solve_rate(rows("archive-g7", domain, transfer=True))
        >= 0.05
        for domain in native.DOMAINS
    )

    branch_archive = all(
        rows("coded-archive", domain)[-1]["motif_parents"] == 4
        and rows("coded-archive", domain)[-1]["codebook_descendants"] == 9
        and set(rows("coded-archive", domain)[-1]["code_hashes"])
        == {str(blocks) for blocks in range(2, 11)}
        for domain in native.DOMAINS
    )

    rediscovery = all(
        row["rediscoveries"] >= 1
        for domain in native.DOMAINS
        for row in rows("coded-archive", domain, transfer=True)
    )

    predicates = {
        "all_committed_tasks_retained": all_records,
        "all_task_caps_respected": all_caps,
        "coded_transfer_solve_rate_at_least_95pct": coded_rate >= 0.95,
        "coded_each_transfer_epoch_domain_at_least_90pct_and_four_discoveries": coded_epoch_domain,
        "coded_beats_archive_g7_by_15pp_aggregate": coded_rate - archive_rate >= 0.15,
        "coded_beats_archive_g7_by_5pp_each_domain": coded_vs_archive_domains,
        "coded_beats_greedy_by_20pp_aggregate": coded_rate - greedy_rate >= 0.20,
        "coded_beats_cold_by_20pp_aggregate": coded_rate - cold_rate >= 0.20,
        "coded_cost_no_more_than_archive_g7": (
            sum(
                _evals(rows("coded-archive", domain))
                for domain in native.DOMAINS
            )
            <= sum(
                _evals(rows("archive-g7", domain))
                for domain in native.DOMAINS
            )
        ),
        "four_branch_motif_archive_and_nine_codebook_descendants": branch_archive,
        "rediscovery_in_every_transfer_epoch_domain": rediscovery,
        "all_failures_and_zero_windows_retained": all_records,
    }

    recovery = all(
        all(
            stream["epochs"][index]["state_before_sha256"]
            == stream["epochs"][index - 1]["state_after_sha256"]
            for index in range(1, len(stream["epochs"]))
        )
        for stream in streams
    )
    predicates["fresh_process_recovery_state_chain_exact"] = recovery

    metrics = {
        "coded_transfer_solve_rate": coded_rate,
        "archive_g7_transfer_solve_rate": archive_rate,
        "greedy_g7_transfer_solve_rate": greedy_rate,
        "cold_g7_transfer_solve_rate": cold_rate,
        "coded_transfer_evaluations": _evals(coded_transfer),
        "archive_g7_transfer_evaluations": _evals(archive_transfer),
        "greedy_g7_transfer_evaluations": _evals(greedy_transfer),
        "cold_g7_transfer_evaluations": _evals(cold_transfer),
        "coded_first_solving_semantics": sum(
            row["first_solving_semantics"] for row in coded_transfer
        ),
        "coded_rediscoveries": sum(
            row["rediscoveries"] for row in coded_transfer
        ),
    }
    passed = all(predicates.values())
    return {
        "schema": "mira-genesis-l9-oe1-qualification-adjudication-v1",
        "predicates": predicates,
        "metrics": metrics,
        "operational_l9_passed": passed,
        "verdict": (
            "L9_OPERATIONAL_GATE_PASSED"
            if passed
            else "VALID_NEGATIVE_L9_OPERATIONAL_QUALIFICATION"
        ),
        "l10_independent_passed": False,
        "claim_boundary": (
            "FINITE_PROSPECTIVE_L9_EVIDENCE_NOT_ASYMPTOTIC_THEOREM_NOT_L10"
        ),
    }


def run(directory, *, workers=4):
    from experiment.l9_oe1 import qualification_freeze

    qualification_freeze.verify()
    directory.mkdir(parents=True, exist_ok=True)

    jobs = [
        (arm, domain)
        for arm in ARMS
        for domain in native.DOMAINS
    ]
    streams = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_run_stream, arm, domain, directory): (arm, domain)
            for arm, domain in jobs
        }
        for future in as_completed(futures):
            streams.append(future.result())

    streams.sort(key=lambda row: (row["arm"], row["domain"]))
    adjudication = adjudicate(streams)
    report = {
        "schema": "mira-genesis-l9-oe1-qualification-report-v1",
        "population_sha256": qualification_bank.population_sha256(),
        "streams": streams,
        "adjudication": adjudication,
    }
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)

    report = run(args.output.parent, workers=args.workers)
    args.output.write_text(
        json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps(report["adjudication"], sort_keys=True))


if __name__ == "__main__":
    main()
