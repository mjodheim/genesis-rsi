"""Prospective L9-OE1 v3 campaign with fail-closed evidence adjudication."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from experiment.l9_oe1_v3 import bank, epoch as epoch_runner
from experiment.rsi_v25.commitments import ROOT, digest
from experiment.rsi_v35 import native

ARMS = epoch_runner.ARMS
TRANSFER_EPOCHS = tuple(range(3, bank.EPOCHS))
PREDICATE_NAMES = (
    "complete_frozen_stream_set",
    "exact_ordered_materialized_tasks_retained",
    "epoch_zero_exact_default_and_recovery_chain_exact",
    "all_task_caps_respected",
    "every_charged_candidate_receipt_consistent_and_retained",
    "coded_transfer_solve_rate_at_least_95pct",
    "coded_each_transfer_epoch_domain_at_least_90pct_and_four_discoveries",
    "coded_beats_archive_g7_by_15pp_aggregate",
    "coded_beats_archive_g7_by_5pp_each_domain",
    "coded_beats_greedy_by_20pp_aggregate",
    "coded_beats_cold_by_20pp_aggregate",
    "coded_cost_no_more_than_archive_g7",
    "four_branch_motif_archive_and_nine_codebook_descendants",
    "rediscovery_in_every_transfer_epoch_domain",
    "failures_zero_windows_and_negative_candidates_retained",
    "terminal_coded_state_and_codebook_verified",
)


def _negative(reason):
    return {
        "schema": "mira-genesis-l9-oe1-v3-adjudication-v1",
        "predicates": {name: False for name in PREDICATE_NAMES},
        "metrics": {},
        "operational_l9_passed": False,
        "verdict": "VALID_NEGATIVE_L9_OPERATIONAL_QUALIFICATION_V3",
        "reason": reason,
        "l10_independent_passed": False,
        "claim_boundary": "FINITE_PROSPECTIVE_L9_EVIDENCE_NOT_ASYMPTOTIC_THEOREM_NOT_L10",
    }


def run_stream(arm, domain, directory):
    stream_dir = directory / arm / domain
    if stream_dir.exists():
        raise ValueError("V3 stream directory must not pre-exist")
    stream_dir.mkdir(parents=True)
    state_path = stream_dir / "state.json"
    records = []
    previous = None

    for epoch in range(bank.EPOCHS):
        output = stream_dir / f"epoch-{epoch:02d}.json"
        cmd = [
            sys.executable,
            "-m",
            "experiment.l9_oe1_v3.epoch",
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
        env = {**os.environ, "PYTHONHASHSEED": "0", "LC_ALL": "C"}
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            timeout=900,
        )
        if result.returncode:
            raise RuntimeError(
                f"V3 epoch failed {arm}/{domain}/{epoch}: " + result.stderr[-1500:]
            )
        row = json.loads(output.read_text(encoding="utf-8"))
        if epoch == 0 and row["state_before_sha256"] != epoch_runner.default_state_sha256(arm):
            raise ValueError("V3 epoch zero did not start from default state")
        if previous is not None and row["state_before_sha256"] != previous:
            raise ValueError("V3 state digest chain mismatch")
        previous = row["state_after_sha256"]
        records.append(row)

    terminal = json.loads(state_path.read_text(encoding="utf-8"))
    if digest(terminal) != previous:
        raise ValueError("V3 terminal state digest mismatch")
    if arm == "coded-archive":
        epoch_runner.verify_coded_state(terminal)

    return {
        "arm": arm,
        "domain": domain,
        "epochs": records,
        "terminal_state": terminal,
        "terminal_state_sha256": digest(terminal),
    }


def transfer_rows(stream):
    return [r for r in stream["epochs"] if r["epoch"] in TRANSFER_EPOCHS]


def solve_rate(rows):
    n = sum(r["tasks"] for r in rows)
    return sum(r["solved"] for r in rows) / n if n else 0.0


def evals(rows):
    return sum(r["evaluations"] for r in rows)


def _expected_stream_keys():
    return {(arm, domain) for arm in ARMS for domain in native.DOMAINS}


def _receipt_consistency(stream):
    """Validate summaries from candidate-level evidence, without fresh execution."""
    domain = stream["domain"]
    expected_tasks = bank.stream(domain)
    expected_by_epoch = {
        epoch: [t for t in expected_tasks if t["epoch"] == epoch]
        for epoch in range(bank.EPOCHS)
    }
    task_exact = True
    receipt_exact = True
    failures_retained = True
    zero_windows_retained = True
    negative_total = 0
    seen_semantics = {}
    position = 0

    if len(stream["epochs"]) != bank.EPOCHS:
        return {
            "task_exact": False,
            "receipt_exact": False,
            "failures_retained": False,
            "zero_windows_retained": False,
            "negative_total": 0,
        }

    for epoch_index, row in enumerate(stream["epochs"]):
        expected = expected_by_epoch[epoch_index]
        records = row.get("records", [])
        if row.get("epoch") != epoch_index or len(records) != len(expected):
            task_exact = False

        recomputed_solved = 0
        recomputed_evals = 0
        recomputed_negative = 0
        recomputed_failures = []
        recomputed_new = 0
        recomputed_rediscovery = 0
        max_task_evals = 0

        for i, task in enumerate(expected):
            if i >= len(records):
                task_exact = False
                break
            record = records[i]
            task_sha = digest(task)
            if record.get("task_id") != task["task_id"] or record.get("task_sha256") != task_sha:
                task_exact = False

            candidates = record.get("candidates", [])
            recomputed_evals += len(candidates)
            max_task_evals = max(max_task_evals, len(candidates))
            solving_semantics = set()
            candidate_negative = 0

            if [c.get("index") for c in candidates] != list(range(len(candidates))):
                receipt_exact = False

            for candidate in candidates:
                try:
                    genome = candidate["genome"]
                    desc = native.descriptor(genome)
                    evaluation = candidate["evaluation"]
                    passed = evaluation["passed_slots"]
                    matched = evaluation["matched_slots"]
                    internally_valid = (
                        candidate["source_sha256"] == desc["source_sha256"]
                        and evaluation["source_sha256"] == desc["source_sha256"]
                        and evaluation["evaluator_task_sha256"] == task_sha
                        and evaluation["accepted"] is True
                        and evaluation["native_source_executed"] is True
                        and evaluation["isolated"] is True
                        and type(passed) is list
                        and len(passed) == task["slots"]
                        and all(type(flag) is bool for flag in passed)
                        and matched == sum(passed)
                        and evaluation["quality_milli"] == matched * 1000 // task["slots"]
                        and evaluation["output_sha256"] == digest(evaluation["outputs"])
                    )
                    is_solving = matched == task["slots"]
                    is_negative = matched < task["slots"]
                    internally_valid = internally_valid and (
                        candidate["solving_candidate"] is is_solving
                        and candidate["negative_candidate"] is is_negative
                    )
                    if not internally_valid:
                        receipt_exact = False
                    if is_solving:
                        solving_semantics.add(desc["semantic_sha256"])
                    if is_negative:
                        candidate_negative += 1
                except Exception:
                    receipt_exact = False

            recomputed_negative += candidate_negative
            expected_semantics = sorted(solving_semantics)
            solved = bool(expected_semantics)
            if record.get("semantics") != expected_semantics:
                receipt_exact = False
            if bool(record.get("solved")) is not solved:
                receipt_exact = False
            if record.get("charged_evaluations") != len(candidates):
                receipt_exact = False

            new = rediscovery = 0
            for semantic in expected_semantics:
                previous = seen_semantics.get(semantic)
                if previous is None:
                    new += 1
                elif previous < position - 1:
                    rediscovery += 1
                seen_semantics[semantic] = position
            if record.get("new_semantics") != new or record.get("rediscoveries") != rediscovery:
                receipt_exact = False

            recomputed_new += new
            recomputed_rediscovery += rediscovery
            if solved:
                recomputed_solved += 1
            else:
                recomputed_failures.append(task["task_id"])
            position += 1

        if row.get("tasks") != len(expected):
            task_exact = False
        if row.get("solved") != recomputed_solved:
            receipt_exact = False
        if row.get("evaluations") != recomputed_evals:
            receipt_exact = False
        if row.get("candidate_receipts") != recomputed_evals:
            receipt_exact = False
        if row.get("negative_candidate_receipts") != recomputed_negative:
            receipt_exact = False
        if row.get("max_task_evaluations") != max_task_evals:
            receipt_exact = False
        if row.get("first_solving_semantics") != recomputed_new:
            receipt_exact = False
        if row.get("rediscoveries") != recomputed_rediscovery:
            receipt_exact = False
        if row.get("failures") != recomputed_failures:
            failures_retained = False
        if "first_solving_semantics" not in row:
            zero_windows_retained = False
        negative_total += recomputed_negative

    return {
        "task_exact": task_exact,
        "receipt_exact": receipt_exact,
        "failures_retained": failures_retained,
        "zero_windows_retained": zero_windows_retained,
        "negative_total": negative_total,
    }


def adjudicate(streams):
    by = {}
    for stream in streams:
        key = (stream.get("arm"), stream.get("domain"))
        if key in by:
            return _negative("duplicate_stream")
        by[key] = stream

    expected_keys = _expected_stream_keys()
    if set(by) != expected_keys:
        result = _negative("incomplete_or_substituted_frozen_stream_set")
        result["predicates"]["complete_frozen_stream_set"] = False
        return result

    consistency = {key: _receipt_consistency(stream) for key, stream in by.items()}
    exact_tasks = all(value["task_exact"] for value in consistency.values())
    receipts_exact = all(value["receipt_exact"] for value in consistency.values())
    failures_retained = all(value["failures_retained"] for value in consistency.values())
    zero_windows_retained = all(value["zero_windows_retained"] for value in consistency.values())
    negative_total = sum(value["negative_total"] for value in consistency.values())

    def rows(arm, domain, transfer=False):
        stream = by[(arm, domain)]
        return transfer_rows(stream) if transfer else stream["epochs"]

    coded = [r for d in native.DOMAINS for r in rows("coded-archive", d, True)]
    archive = [r for d in native.DOMAINS for r in rows("archive-g7", d, True)]
    greedy = [r for d in native.DOMAINS for r in rows("greedy-g7", d, True)]
    cold = [r for d in native.DOMAINS for r in rows("cold-g7", d, True)]

    initial_exact = all(
        s["epochs"][0]["state_before_sha256"] == epoch_runner.default_state_sha256(s["arm"])
        for s in streams
    )
    recovery = all(
        all(
            s["epochs"][i]["state_before_sha256"] == s["epochs"][i - 1]["state_after_sha256"]
            for i in range(1, len(s["epochs"]))
        )
        for s in streams
    )
    terminal_links = all(
        s.get("terminal_state_sha256") == digest(s.get("terminal_state"))
        and s.get("terminal_state_sha256") == s["epochs"][-1]["state_after_sha256"]
        for s in streams
    )

    terminal_coded = terminal_links
    if terminal_coded:
        try:
            for domain in native.DOMAINS:
                epoch_runner.verify_coded_state(by[("coded-archive", domain)]["terminal_state"])
        except Exception:
            terminal_coded = False

    caps = all(
        r["max_task_evaluations"] <= 14
        and all(rec["charged_evaluations"] <= 14 for rec in r["records"])
        for s in streams
        for r in s["epochs"]
    )

    coded_epoch = all(
        r["solved"] / r["tasks"] >= 0.90 and r["first_solving_semantics"] >= 4
        for d in native.DOMAINS
        for r in rows("coded-archive", d, True)
    )
    cr, ar, gr, xr = map(solve_rate, (coded, archive, greedy, cold))
    domain_margin = all(
        solve_rate(rows("coded-archive", d, True))
        - solve_rate(rows("archive-g7", d, True))
        >= 0.05
        for d in native.DOMAINS
    )
    branch = all(
        len(by[("coded-archive", d)]["terminal_state"].get("motifs", [])) == 4
        and len(by[("coded-archive", d)]["terminal_state"].get("code_hashes", {})) == 9
        and set(by[("coded-archive", d)]["terminal_state"].get("code_hashes", {}))
        == {str(b) for b in range(2, 11)}
        for d in native.DOMAINS
    )
    rediscovery = all(
        r["rediscoveries"] >= 1
        for d in native.DOMAINS
        for r in rows("coded-archive", d, True)
    )

    predicates = {
        "complete_frozen_stream_set": True,
        "exact_ordered_materialized_tasks_retained": exact_tasks,
        "epoch_zero_exact_default_and_recovery_chain_exact": initial_exact and recovery and terminal_links,
        "all_task_caps_respected": caps,
        "every_charged_candidate_receipt_consistent_and_retained": receipts_exact,
        "coded_transfer_solve_rate_at_least_95pct": cr >= 0.95,
        "coded_each_transfer_epoch_domain_at_least_90pct_and_four_discoveries": coded_epoch,
        "coded_beats_archive_g7_by_15pp_aggregate": cr - ar >= 0.15,
        "coded_beats_archive_g7_by_5pp_each_domain": domain_margin,
        "coded_beats_greedy_by_20pp_aggregate": cr - gr >= 0.20,
        "coded_beats_cold_by_20pp_aggregate": cr - xr >= 0.20,
        "coded_cost_no_more_than_archive_g7": sum(
            evals(rows("coded-archive", d)) for d in native.DOMAINS
        )
        <= sum(evals(rows("archive-g7", d)) for d in native.DOMAINS),
        "four_branch_motif_archive_and_nine_codebook_descendants": branch,
        "rediscovery_in_every_transfer_epoch_domain": rediscovery,
        "failures_zero_windows_and_negative_candidates_retained": (
            failures_retained and zero_windows_retained and negative_total > 0
        ),
        "terminal_coded_state_and_codebook_verified": terminal_coded,
    }

    metrics = {
        "coded_transfer_solve_rate": cr,
        "archive_g7_transfer_solve_rate": ar,
        "greedy_g7_transfer_solve_rate": gr,
        "cold_g7_transfer_solve_rate": xr,
        "coded_transfer_evaluations": evals(coded),
        "archive_g7_transfer_evaluations": evals(archive),
        "greedy_g7_transfer_evaluations": evals(greedy),
        "cold_g7_transfer_evaluations": evals(cold),
        "coded_first_solving_semantics": sum(r["first_solving_semantics"] for r in coded),
        "coded_rediscoveries": sum(r["rediscoveries"] for r in coded),
        "negative_candidate_receipts_retained": negative_total,
    }
    passed = all(predicates.values())
    return {
        "schema": "mira-genesis-l9-oe1-v3-adjudication-v1",
        "predicates": predicates,
        "metrics": metrics,
        "operational_l9_passed": passed,
        "verdict": (
            "L9_OPERATIONAL_GATE_PASSED"
            if passed
            else "VALID_NEGATIVE_L9_OPERATIONAL_QUALIFICATION_V3"
        ),
        "l10_independent_passed": False,
        "claim_boundary": "FINITE_PROSPECTIVE_L9_EVIDENCE_NOT_ASYMPTOTIC_THEOREM_NOT_L10",
    }


def run(directory, workers=4):
    from experiment.l9_oe1_v3 import freeze

    freeze.verify()
    if directory.exists():
        raise ValueError("V3 qualification output directory must not pre-exist")
    directory.mkdir(parents=True)
    jobs = [(a, d) for a in ARMS for d in native.DOMAINS]
    streams = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(run_stream, a, d, directory): (a, d) for a, d in jobs}
        for future in as_completed(futures):
            streams.append(future.result())
    streams.sort(key=lambda x: (x["arm"], x["domain"]))
    return {
        "schema": "mira-genesis-l9-oe1-v3-report-v1",
        "population_file_sha256": bank.population_file_sha256(),
        "streams": streams,
        "adjudication": adjudicate(streams),
    }


def _archive(output, report):
    raw = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output.write_bytes(raw)
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    archive = Path(str(output) + ".gz")
    archive.write_bytes(compressed)
    summary = {
        "schema": "mira-genesis-l9-oe1-v3-summary-v1",
        "population_file_sha256": bank.population_file_sha256(),
        "raw_report_bytes": len(raw),
        "raw_report_sha256": hashlib.sha256(raw).hexdigest(),
        "gzip_sha256": hashlib.sha256(compressed).hexdigest(),
        "adjudication": report["adjudication"],
    }
    (output.parent / "SUMMARY.json").write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    output.unlink()
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    report = run(args.output.parent, args.workers)
    summary = _archive(args.output, report)
    print(json.dumps(summary["adjudication"], sort_keys=True))


if __name__ == "__main__":
    main()
