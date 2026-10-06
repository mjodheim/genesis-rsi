"""Post-run verifier for the archived L9-OE1 v2 qualification."""
from __future__ import annotations
import gzip, hashlib, json
from pathlib import Path

from experiment.l9_oe1_v2 import bank, campaign, freeze
from experiment.rsi_v25.commitments import ROOT

DIRECTORY=ROOT/"results/l9-oe1/v2-qualification-20261006"
ARCHIVE=DIRECTORY/"REPORT.json.gz"
SUMMARY=DIRECTORY/"SUMMARY.json"

def verify():
    summary=json.loads(SUMMARY.read_text())
    compressed=ARCHIVE.read_bytes()
    if hashlib.sha256(compressed).hexdigest()!=summary["gzip_sha256"]:
        raise ValueError("V2 gzip hash mismatch")
    raw=gzip.decompress(compressed)
    if hashlib.sha256(raw).hexdigest()!=summary["raw_report_sha256"]:
        raise ValueError("V2 raw report hash mismatch")
    if len(raw)!=summary["raw_report_bytes"]:
        raise ValueError("V2 raw report size mismatch")
    report=json.loads(raw)
    if not freeze.verify():
        raise ValueError("V2 freeze verification failed")
    if report["population_file_sha256"]!=bank.population_file_sha256():
        raise ValueError("V2 population mismatch")
    rebuilt=campaign.adjudicate(report["streams"])
    if rebuilt!=report["adjudication"]:
        raise ValueError("V2 adjudication does not replay")
    if rebuilt!=summary["adjudication"]:
        raise ValueError("V2 summary differs from report")
    if not rebuilt["operational_l9_passed"]:
        raise ValueError("V2 archived verdict is not positive")
    for stream in report["streams"]:
        for epoch in stream["epochs"]:
            if sum(len(r["candidates"]) for r in epoch["records"])!=epoch["evaluations"]:
                raise ValueError("V2 candidate retention mismatch")
    return True

if __name__=="__main__":
    print("L9_OE1_V2_ARCHIVE_OK" if verify() else "FAIL")
