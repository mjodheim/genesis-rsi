"""Single frozen operational assay, retaining all comparisons and failures."""
import argparse
import gzip
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v31 import bank, engine, freeze, programs
from experiment.rsi_v31.archive import Archive

ATTEMPT = ROOT / "results/rsi-v31/archive-20261001/V31_ATTEMPT.json"
RAW = ATTEMPT.with_name("V31_ATTEMPT_RAW.json.gz")
VERDICT = ATTEMPT.with_name("V31_FINAL_ADJUDICATION.json")
DEVELOPMENT = freeze.HERE / "DEVELOPMENT.json.gz"


def preserve(record):
    encoded = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    with RAW.open("wb") as stream:
        with gzip.GzipFile(fileobj=stream, mode="wb", mtime=0) as archive:
            archive.write(encoded)
    write_json(ATTEMPT, {"schema": "mira-genesis-v31-lossless-index-v1", "status": record["status"],
                        "freeze_sha256": record["freeze_sha256"], "canonical_attempts": record["canonical_attempts"],
                        "raw_filename": RAW.name, "raw_sha256": digest_bytes(RAW.read_bytes()),
                        "record_sha256": digest(record), "uncompressed_sha256": digest_bytes(encoded)})


def read_attempt():
    index = json.loads(ATTEMPT.read_text())
    encoded = gzip.decompress(RAW.read_bytes())
    record = json.loads(encoded)
    if (index["schema"] != "mira-genesis-v31-lossless-index-v1" or index["raw_filename"] != RAW.name
            or index["raw_sha256"] != digest_bytes(RAW.read_bytes()) or index["record_sha256"] != digest(record)
            or index["uncompressed_sha256"] != digest_bytes(encoded)
            or any(index[key] != record[key] for key in ("status", "freeze_sha256", "canonical_attempts"))):
        raise ValueError("Altered original attempt or lossless index")
    return record


def development():
    if DEVELOPMENT.exists():
        raise ValueError("Never overwrite development receipts")
    result = {"scope": "COMPLETE_PROJECT_AUTHORED_DEVELOPMENT_NOT_FRESH", "streams": {}}
    with tempfile.TemporaryDirectory(prefix="v31-development-") as temporary:
        for seed in bank.DEV_SEEDS:
            tasks = bank.stream(seed)
            result["streams"][str(seed)] = {}
            for arm in engine.ARMS:
                path = Path(temporary) / f"{seed}-{arm}.jsonl"
                rows, head = engine.run_stream(tasks, arm, path, "public-development", isolated=False)
                resumed_path = Path(temporary) / f"{seed}-{arm}-resumed.jsonl"
                engine.run_stream(tasks, arm, resumed_path, "public-development", isolated=False, stop_after=6)
                resumed, resumed_head = engine.run_stream(tasks, arm, resumed_path, "public-development", isolated=False)
                if rows != resumed or head != resumed_head:
                    raise ValueError("Recovery changed development choices or costs")
                result["streams"][str(seed)][arm] = {"tasks": tasks, "episodes": rows, "head_sha256": head,
                                                    "windows": engine.windows(rows), "recovery_byte_exact": True}
    encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    DEVELOPMENT.write_bytes(gzip.compress(encoded, mtime=0))
    return {seed: {arm: row["windows"] for arm, row in arms.items()} for seed, arms in result["streams"].items()}


def adjudicate(record, frozen, *, replay=True):
    if record["status"] != "COMPLETED" or set(record["streams"]) != {str(seed) for seed in bank.FRESH_SEEDS}:
        raise ValueError("Incomplete operational assay")
    summaries = {}
    growth = branching = rediscovery = True
    for seed in bank.FRESH_SEEDS:
        arms = record["streams"][str(seed)]
        if set(arms) != set(engine.ARMS):
            raise ValueError("Omitted matched retention arm")
        summaries[str(seed)] = {}
        for arm, stream in arms.items():
            tasks, rows = bank.stream(seed), stream["episodes"]
            if len(rows) != len(tasks):
                raise ValueError("Omitted fresh task or negative")
            journal = stream["journal"].encode()
            events = Archive.decode(journal)
            if (events[-1]["sha256"] != stream["head_sha256"]
                    or events[0]["data"] != engine.binding(tasks, arm, frozen["freeze_sha256"])
                    or digest([event["data"] for event in events if event["kind"] == "episode"]) != digest(rows)):
                raise ValueError("Substituted journal or external head")
            with tempfile.TemporaryDirectory(prefix="v31-journal-replay-") as temporary:
                path = Path(temporary) / "archive.jsonl"
                path.write_bytes(journal)
                if Archive(path, engine.binding(tasks, arm, frozen["freeze_sha256"])).episodes() != rows:
                    raise ValueError("Invalid transaction or reservation")
            if replay:
                engine.verify_stream(tasks, arm, rows, isolated=True)
            if any(row["charged_evaluations"] > engine.CAPS.requests + 1 for row in rows):
                raise ValueError("External cost cap was exceeded")
            summary = engine.windows(rows)
            summaries[str(seed)][arm] = summary
            if arm == "archive":
                growth &= all(b["archive_semantic_size"] > a["archive_semantic_size"] and
                              b["cumulative_task_family_widths"] > a["cumulative_task_family_widths"]
                              for a, b in zip(summary, summary[1:]))
                history = engine.history_from(rows)
                counts = Counter(row["parent_source_sha256"] for row in history.values()
                                 if row["parent_source_sha256"] is not None)
                branching &= any(value > 1 for value in counts.values())
                rediscovery &= any(row["rediscovered"] for row in rows)
                if stream["checkpoint_position"] != 6 or stream["checkpoint_head_sha256"] != events[12]["sha256"]:
                    raise ValueError("Recovery checkpoint was altered")
    predicates = {"complete_frozen_evidence_and_equal_caps": record["freeze_sha256"] == frozen["freeze_sha256"]
                    and record["canonical_attempts"] == 1 and record["policy_sha256"] == programs.PARENT_SHA256
                    and record["track"] == "B" and record["scientific_external_model_calls"] == 0
                    and record["python_version"] == frozen["python_version"],
                  "archive_and_task_diversity_grow_every_seed": bool(growth),
                  "branching_every_seed": bool(branching), "rediscovery_every_seed": bool(rediscovery),
                  "task_boundary_recovery_and_receipt_replay": True}
    positive = all(predicates.values())
    return {"schema": "mira-genesis-v31-operational-adjudication-v1", "operational_precursor_positive": positive,
            "verdict": "POSITIVE_ARCHIVE_OPERATIONS" if positive else "VALID_NEGATIVE_ARCHIVE_OPERATIONS",
            "predicates": predicates, "windows": summaries, "freeze_sha256": frozen["freeze_sha256"],
            "policy_sha256": programs.PARENT_SHA256, "fresh_tasks_per_arm": 144, "track": "B",
            "discovery_positive_every_measured_window": all(row["new_solutions"] > 0 for arms in summaries.values()
                                                           for row in arms["archive"]),
            "scope": "FINITE_PROJECT_AUTHORED_TRANSDUCER_ARCHIVE_OPERATIONS_WITH_UNCHANGED_G7",
            "new_recursive_transition_established": False, "l9_open_ended_passed": False,
            "l10_independent_passed": False, "independent_task_authorship": False}


def run():
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if frozen["python_version"] != sys.version.split()[0]:
        raise ValueError("Canonical Python version differs from freeze")
    ATTEMPT.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ATTEMPT, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    record = {"status": "STARTED", "freeze_sha256": frozen["freeze_sha256"], "canonical_attempts": 1,
              "policy_sha256": programs.PARENT_SHA256, "python_version": frozen["python_version"],
              "track": "B", "scientific_external_model_calls": 0, "streams": {}}
    with os.fdopen(fd, "w") as stream:
        json.dump(record, stream)
    try:
        for seed in bank.FRESH_SEEDS:
            record["streams"][str(seed)] = {}
            for arm in engine.ARMS:
                tasks = bank.stream(seed)
                path = ATTEMPT.parent / f"s{seed}-{arm}.jsonl"
                _, checkpoint = engine.run_stream(tasks, arm, path, frozen["freeze_sha256"], stop_after=6)
                # The second call reconstructs all history from disk, not an executor cache.
                rows, head = engine.run_stream(tasks, arm, path, frozen["freeze_sha256"])
                record["streams"][str(seed)][arm] = {"episodes": rows, "head_sha256": head,
                    "journal": path.read_text(), "checkpoint_position": 6, "checkpoint_head_sha256": checkpoint}
                preserve(record)
        record["status"] = "COMPLETED"
        preserve(record)
        value = adjudicate(record, frozen, replay=True)
        write_json(VERDICT, value)
        return value
    except BaseException as error:
        record["status"], record["interruption"] = "INTERRUPTED", type(error).__name__
        preserve(record)
        raise


def check(*, require_result=False, replay=True):
    if not freeze.PATH.exists():
        if require_result:
            raise ValueError("Missing prospective V31 freeze")
        return {"operational_precursor_positive": False, "status": "UNFROZEN",
                "l9_open_ended_passed": False, "l10_independent_passed": False}
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if not ATTEMPT.exists():
        if require_result:
            raise ValueError("Missing canonical operational evidence")
        return {"status": "FROZEN_NOT_EXECUTED", "l9_open_ended_passed": False, "l10_independent_passed": False}
    result = adjudicate(read_attempt(), frozen, replay=replay)
    if digest(result) != digest(json.loads(VERDICT.read_text())):
        raise ValueError("Stored operational verdict differs from complete evidence")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("development", "run", "check"))
    args = parser.parse_args()
    print(json.dumps(globals()[args.action](), indent=2))
