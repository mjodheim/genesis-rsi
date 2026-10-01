"""Decisive CI replay of a preserved V25 outcome, positive or negative."""
from __future__ import annotations

import argparse
import json
import subprocess

from experiment.rsi_v25.commitments import HERE, ROOT, digest
from experiment.rsi_v25.build_l5_freeze import preserved_v24_files
from experiment.rsi_v25.campaign_adjudication import adjudicate
from experiment.rsi_v25.executable_meta import ARMS
from experiment.rsi_v25.scientific_freeze import FREEZE_PATH, committed_freeze
from experiment.rsi_v25.run_executable_campaign import ATTEMPT, ADJUDICATION


def require_committed_record(path):
    relative = path.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(["git", "show", f"HEAD:{relative}"], cwd=ROOT)
    if committed != path.read_bytes():
        raise ValueError(f"Canonical evidence is not preserved as committed bytes: {relative}")


def check(*, require_result=False):
    preserved_v24_files()
    if not FREEZE_PATH.exists():
        if ATTEMPT.exists() or ADJUDICATION.exists() or require_result:
            raise ValueError("Canonical V25 evidence requires a committed full scientific freeze")
        return {"status": "EXECUTABLE_APPARATUS_PREPARATION", "v25_l5_positive": False}
    freeze = committed_freeze()
    if not ATTEMPT.exists():
        if ADJUDICATION.exists() or require_result:
            raise ValueError("Scientific freeze exists but the required attempt is missing")
        return {"status": "PREREGISTERED_UNCONSUMED", "v25_l5_positive": False}
    require_committed_record(ATTEMPT)
    require_committed_record(ADJUDICATION)
    attempt = json.loads(ATTEMPT.read_text())
    record = json.loads(ADJUDICATION.read_text())
    if (attempt["canonical_attempts"] != 1 or attempt["freeze_sha256"] != freeze["freeze_sha256"]
            or attempt["runtime_versions"] != freeze["runtime_versions"]):
        raise ValueError("Canonical count, runtime or freeze identity changed")
    if attempt["status"] == "INSTRUMENT_ABORTED":
        if (record["verdict"] != "PRESERVED_INSTRUMENT_ABORT" or record["v25_l5_positive"]
                or not record["partial_evidence_preserved"] or not attempt["instrument_error"]):
            raise ValueError("The preserved instrument failure was relabeled")
        return {"status": "PRESERVED_INSTRUMENT_ABORT", "v25_l5_positive": False}
    if attempt["status"] != "COMPLETED" or set(attempt["meta"]) != set(ARMS):
        raise ValueError("A partial canonical attempt cannot supply a final verdict")
    calibration = json.loads((HERE / "PUBLIC_DEVELOPMENT_CALIBRATION.json").read_text())
    native = json.loads((HERE / "NATIVE_HOST_CALIBRATION.json").read_text())
    if digest(attempt["native_seeded"]) != digest({row["task_id"]: row["seeded"] for row in native["tasks"]}):
        raise ValueError("Native seeded roots changed after freezing")
    replay = adjudicate(attempt, freeze, calibration)
    if digest(replay) != digest(record):
        raise ValueError("Preserved verdict disagrees with independent evidence replay")
    return {"status": replay["verdict"], "v25_l5_positive": replay["v25_l5_positive"],
            "fresh_global_utilities": replay["fresh_global_utilities"],
            "holdout_consumed": replay["holdout_consumed"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-result", action="store_true")
    result = check(require_result=parser.parse_args().require_result)
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
