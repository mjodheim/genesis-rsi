"""Complete, recoverable comparison on consumed V31/V32 populations only."""
import argparse
import gzip
import json
import platform
import subprocess
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v31 import bank as v31_bank
from experiment.rsi_v32 import bank as v32_bank, freeze as v32_freeze, storage
from experiment.rsi_v34 import engine

HERE = Path(__file__).resolve().parent


def population():
    return {**{f"v31-{seed}": v31_bank.stream(seed) for seed in v31_bank.DEV_SEEDS + v31_bank.FRESH_SEEDS},
            **{f"v32-{seed}": v32_bank.stream(seed) for seed in v32_bank.FRESH_SEEDS}}


def manifest():
    previous = json.loads(v32_freeze.PATH.read_text())
    v32_freeze.verify(previous)
    paths = [*HERE.glob("*.py"), HERE / "PROTOCOL.md",
             *(ROOT / "experiment/rsi_v33").glob("*.py"),
             ROOT / "experiment/rsi_v33/PROTOCOL.md",
             ROOT / "docs/IP_REVIEWS/V33_PROBE_MEMORY_DEVELOPMENT_REVIEW.md",
             ROOT / "tests/test_rsi_v33.py",
             ROOT / "docs/IP_REVIEWS/V34_PROBE_ACCOUNTING_CORRECTION_REVIEW.md",
             ROOT / "tests/test_rsi_v34.py"]
    inputs = {**previous["inputs"], **{p.relative_to(ROOT).as_posix(): digest_bytes(p.read_bytes()) for p in paths}}
    tasks = population()
    return {"schema": "mira-genesis-v34-consumed-development-manifest-v1",
            "scope": "ALL_456_CONSUMED_V31_V32_TASKS_NOT_FRESH", "track": "B", "isolated": False,
            "success_scope": "ALL_CHARGED_CANDIDATES", "all_evaluated_probes_retained": True,
            "python_version": platform.python_version(), "inputs": inputs,
            "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
            "v32_freeze_sha256": previous["freeze_sha256"], "arms": list(engine.ARMS),
            "caps": engine.CAPS.__dict__, "max_charged_evaluations_per_task": engine.MAX_EVALUATIONS,
            "population_sha256": digest(tasks), "stream_sha256": {key: digest(value) for key, value in tasks.items()},
            "tasks_per_arm": sum(len(value) for value in tasks.values()),
            "scientific_external_model_calls": 0, "l9_open_ended_passed": False, "l10_independent_passed": False}


def adjudicate(streams):
    totals = {arm: {key: sum(engine.summary(stream[arm]["episodes"])[key] for stream in streams.values())
                    for key in ("tasks", "solved", "evaluations", "new_solutions", "retrieval_evaluated",
                                "retrieval_worse_than_root")} for arm in engine.ARMS}
    paired = {}
    for arm in engine.ARMS[1:]:
        counts = {"both_solved": 0, "probe_only": 0, "control_only": 0, "neither_solved": 0}
        for stream in streams.values():
            a, b = stream["probe"]["episodes"], stream[arm]["episodes"]
            if len(a) != len(b):
                raise ValueError("Unequal paired population")
            for left, right in zip(a, b):
                if left["task_sha256"] != right["task_sha256"]:
                    raise ValueError("Different paired task")
                name = "both_solved" if left["solved"] and right["solved"] else (
                    "probe_only" if left["solved"] else "control_only" if right["solved"] else "neither_solved")
                counts[name] += 1
        paired[arm] = counts
    predicates = {"more_solves_than_every_control": all(totals["probe"]["solved"] > totals[a]["solved"]
                                                       for a in engine.ARMS[1:]),
                  "cost_no_greater_than_cold": totals["probe"]["evaluations"] <= totals["cold"]["evaluations"],
                  "no_stream_regression_against_cold": all(
                      sum(e["solved"] for e in s["probe"]["episodes"]) >=
                      sum(e["solved"] for e in s["cold"]["episodes"]) for s in streams.values())}
    return {"scope": "CONSUMED_DEVELOPMENT_ONLY", "totals": totals, "paired": paired, "predicates": predicates,
            "descriptive_finite_usefulness": all(predicates.values()),
            "new_recursive_transition_established": False, "l9_open_ended_passed": False,
            "l10_independent_passed": False}


def run(directory):
    directory = Path(directory)
    current = manifest()
    commitment = directory / "MANIFEST.json"
    if commitment.exists():
        if storage.read_json(commitment) != current:
            raise ValueError("Development apparatus, runtime or population changed")
    else:
        storage.publish_json(commitment, current)  # before the first evaluation
    if (directory / "COMPLETION.json").exists():
        raise FileExistsError("Development already completed; use check, do not rerun")
    apparatus = digest(current)
    streams = {}
    for label, tasks in population().items():
        streams[label] = {}
        for arm in engine.ARMS:
            path = directory / "journals" / f"{label}-{arm}.jsonl"
            rows, head = engine.run_stream(tasks, arm, path, apparatus, isolated=False)
            engine.verify_stream(tasks, arm, rows, isolated=False)
            streams[label][arm] = {"episodes": rows, "head_sha256": head, "summary": engine.summary(rows)}
            print(label, arm, {k: v for k, v in engine.summary(rows).items() if k != "windows"}, flush=True)
    record = {"schema": "mira-genesis-v34-consumed-development-evidence-v1", "manifest_sha256": apparatus,
              "status": "COMPLETED", "streams": streams}
    raw = gzip.compress(canonical(record) + b"\n", mtime=0)
    raw_path = directory / "DEVELOPMENT.json.gz"
    if raw_path.exists():
        if storage.read_regular(raw_path) != raw:
            raise ValueError("Existing complete raw evidence differs")
    else:
        storage.publish_once(raw_path, raw)
    report = adjudicate(streams)
    report_path = directory / "REPORT.json"
    if report_path.exists():
        if storage.read_json(report_path) != report:
            raise ValueError("Existing report differs")
    else:
        storage.publish_json(report_path, report)
    storage.publish_json(directory / "COMPLETION.json", {
        "manifest_sha256": apparatus, "raw_sha256": digest_bytes(raw), "report_sha256": digest(report),
        "heads": {label: {arm: stream["head_sha256"] for arm, stream in arms.items()}
                  for label, arms in streams.items()}})
    check(directory)
    return report


def check(directory):
    directory = Path(directory)
    current = manifest()
    if storage.read_json(directory / "MANIFEST.json") != current:
        raise ValueError("Altered manifest or apparatus")
    completion = storage.read_json(directory / "COMPLETION.json")
    raw = storage.read_regular(directory / "DEVELOPMENT.json.gz")
    if completion["manifest_sha256"] != digest(current) or completion["raw_sha256"] != digest_bytes(raw):
        raise ValueError("Altered completion or raw evidence")
    record = json.loads(gzip.decompress(raw))
    tasks_by_stream = population()
    if (record["status"] != "COMPLETED" or record["manifest_sha256"] != digest(current)
            or set(record["streams"]) != set(tasks_by_stream) or set(completion["heads"]) != set(tasks_by_stream)):
        raise ValueError("Incomplete consumed population or completion heads")
    for label, tasks in tasks_by_stream.items():
        streams = record["streams"][label]
        if set(streams) != set(engine.ARMS) or set(completion["heads"][label]) != set(engine.ARMS):
            raise ValueError("Omitted development control")
        for arm, stream in streams.items():
            archive = engine.Archive(directory / "journals" / f"{label}-{arm}.jsonl",
                                     engine.binding(tasks, arm, digest(current), False))
            events = archive.read(expected_head=completion["heads"][label][arm])
            if (events[-1]["sha256"] != stream["head_sha256"] or archive.episodes() != stream["episodes"]
                    or engine.summary(stream["episodes"]) != stream["summary"]):
                raise ValueError("Altered journal, cost or summary")
            engine.verify_stream(tasks, arm, stream["episodes"], isolated=False)
    report = storage.read_json(directory / "REPORT.json")
    if report != adjudicate(record["streams"]) or digest(report) != completion["report_sha256"]:
        raise ValueError("Altered descriptive report")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("run", "check"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps((run if args.action == "run" else check)(args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
