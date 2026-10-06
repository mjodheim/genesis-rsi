"""Frozen post-run verifier for the archived L9-OE1 v3 qualification."""
from __future__ import annotations

import gzip
import hashlib
import json

from experiment.l9_oe1_v3 import bank, campaign, epoch as epoch_runner, freeze
from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v35 import native

DIRECTORY = ROOT / "results/l9-oe1/v3-qualification-20261006"
ARCHIVE = DIRECTORY / "REPORT.json.gz"
SUMMARY = DIRECTORY / "SUMMARY.json"
AUDIT_RECEIPT = DIRECTORY / "AUDIT.json"


def _task_lookup():
    result = {}
    for domain in native.DOMAINS:
        rows = bank.stream(domain)
        for task in rows:
            result[(domain, task["epoch"], task["task_id"])] = task
    return result


def _reexecute_candidate(task, candidate):
    genome = candidate["genome"]
    # Re-execute the frozen native program independently in-process. The original
    # qualification used the isolated worker; both paths normalize through the
    # same JSON wire representation. The rebuilt receipt deliberately records
    # isolated=True so it must match the retained scientific receipt byte-for-byte.
    outputs = native.execute(genome, task["inputs"], task["slots"], isolated=False)
    rebuilt = native.receipt(task, genome, outputs, isolated=True)
    if rebuilt != candidate["evaluation"]:
        raise ValueError(
            "V3 retained candidate receipt failed independent native re-execution: "
            + task["task_id"]
        )
    return 1


def verify(*, write_receipt=True):
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    compressed = ARCHIVE.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != summary["gzip_sha256"]:
        raise ValueError("V3 gzip hash mismatch")
    raw = gzip.decompress(compressed)
    if hashlib.sha256(raw).hexdigest() != summary["raw_report_sha256"]:
        raise ValueError("V3 raw report hash mismatch")
    if len(raw) != summary["raw_report_bytes"]:
        raise ValueError("V3 raw report size mismatch")

    report = json.loads(raw)
    if not freeze.verify():
        raise ValueError("V3 closed freeze verification failed")
    if report["population_file_sha256"] != bank.population_file_sha256():
        raise ValueError("V3 population mismatch")

    rebuilt = campaign.adjudicate(report["streams"])
    if rebuilt != report["adjudication"]:
        raise ValueError("V3 adjudication does not replay")
    if rebuilt != summary["adjudication"]:
        raise ValueError("V3 summary differs from report")
    if not rebuilt["operational_l9_passed"]:
        raise ValueError("V3 archived verdict is not positive")

    tasks = _task_lookup()
    reexecuted = 0
    expected_streams = {(arm, domain) for arm in epoch_runner.ARMS for domain in native.DOMAINS}
    seen_streams = set()

    for stream in report["streams"]:
        key = (stream["arm"], stream["domain"])
        if key in seen_streams or key not in expected_streams:
            raise ValueError("V3 duplicate/substituted stream during audit")
        seen_streams.add(key)

        if stream["arm"] == "coded-archive":
            epoch_runner.verify_coded_state(stream["terminal_state"])

        expected_domain_rows = bank.stream(stream["domain"])
        by_epoch = {
            epoch: [task for task in expected_domain_rows if task["epoch"] == epoch]
            for epoch in range(bank.EPOCHS)
        }
        for epoch_index, epoch in enumerate(stream["epochs"]):
            expected = by_epoch[epoch_index]
            records = epoch["records"]
            if len(records) != len(expected):
                raise ValueError("V3 audit task count mismatch")
            for record, task in zip(records, expected):
                if record["task_id"] != task["task_id"]:
                    raise ValueError("V3 audit task order mismatch")
                if tasks[(task["domain"], task["epoch"], task["task_id"])] != task:
                    raise ValueError("V3 audit frozen task lookup mismatch")
                for candidate in record["candidates"]:
                    reexecuted += _reexecute_candidate(task, candidate)

    if seen_streams != expected_streams:
        raise ValueError("V3 audit did not receive all 16 frozen streams")

    retained = sum(
        len(candidate_list)
        for stream in report["streams"]
        for epoch in stream["epochs"]
        for candidate_list in (record["candidates"] for record in epoch["records"])
    )
    if reexecuted != retained:
        raise ValueError("V3 audit did not re-execute every retained candidate")

    receipt = {
        "schema": "mira-genesis-l9-oe1-v3-audit-v1",
        "verdict": "L9_OE1_V3_ARCHIVE_OK",
        "reexecuted_candidate_receipts": reexecuted,
        "population_file_sha256": bank.population_file_sha256(),
        "freeze_sha256": freeze.load()["freeze_sha256"],
        "raw_report_sha256": summary["raw_report_sha256"],
        "gzip_sha256": summary["gzip_sha256"],
        "operational_l9_passed": True,
        "l10_independent_passed": False,
    }
    if write_receipt:
        AUDIT_RECEIPT.write_text(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    return receipt


if __name__ == "__main__":
    result = verify()
    print(result["verdict"] + " candidates=" + str(result["reexecuted_candidate_receipts"]))
