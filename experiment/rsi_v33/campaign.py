"""One prospective finite memory trial; retain every arm and original negative."""
import argparse
import gzip
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v31 import engine as v31, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import bank, engine, freeze, storage

DIRECTORY = ROOT / "results/rsi-v33/probes-20261002"
RESERVATION = DIRECTORY / "V33_RESERVATION.json"
COMPLETION = DIRECTORY / "V33_COMPLETION.json"


def validate_journal(tasks, arm, margin, stream, frozen):
    identity = engine.binding(tasks, arm, margin, frozen["freeze_sha256"])
    events = Archive.decode(stream["journal"].encode())
    if (not events or events[0]["data"] != identity
            or events[-1]["sha256"] != stream["head_sha256"]
            or stream["checkpoint_position"] != 6 or len(events) < 13
            or events[12]["sha256"] != stream["checkpoint_head_sha256"]):
        raise ValueError("Substituted journal, checkpoint or externally retained head")
    with tempfile.TemporaryDirectory(prefix="v33-receipt-journal-") as temporary:
        path = Path(temporary) / "journal.jsonl"
        path.write_text(stream["journal"])
        rows = Archive(path, identity).episodes()
    if digest(rows) != digest(stream["episodes"]):
        raise ValueError("Journal differs from complete episode evidence")
    return rows


def adjudicate(record, frozen, *, replay=True):
    if (set(record) != {"schema", "status", "freeze_sha256", "canonical_attempts", "policy_sha256",
                       "python_version", "track", "scientific_external_model_calls", "margin_milli", "streams"}
            or record["schema"] != "mira-genesis-v33-complete-attempt-v1" or record["status"] != "COMPLETED"
            or record["freeze_sha256"] != frozen["freeze_sha256"] or record["canonical_attempts"] != 1
            or record["policy_sha256"] != programs.PARENT_SHA256 or record["python_version"] != frozen["python_version"]
            or record["track"] != "B" or record["scientific_external_model_calls"] != 0
            or record["margin_milli"] != frozen["margin_milli"]
            or set(record["streams"]) != {str(seed) for seed in bank.FRESH_SEEDS}):
        raise ValueError("Incomplete attempt or substituted scientific scope, authority or population")
    summaries, windows, pairs = {}, {}, {}
    margin = frozen["margin_milli"]
    for seed in bank.FRESH_SEEDS:
        arms = record["streams"][str(seed)]
        if set(arms) != set(engine.ARMS):
            raise ValueError("Omitted matched control")
        summaries[str(seed)], windows[str(seed)], pairs[str(seed)] = {}, {}, {}
        tasks = bank.stream(seed)
        for arm, stream in arms.items():
            rows = validate_journal(tasks, arm, margin, stream, frozen)
            if (len(rows) != len(tasks) or any(row["position"] != position or row["task_sha256"] != digest(task)
                    or row["charged_evaluations"] > engine.MAX_EVALUATIONS
                    or row["charged_evaluations"] != row["search"]["represented_requests"] + 4
                    or not row["search"]["isolated_policy_processes"]
                    or row["search"]["caps"] != engine.CAPS.__dict__
                    or row["search"]["policy_sha256"] != programs.PARENT_SHA256
                    or row["routing"]["controller_calls"] != 1
                    or row["routing"]["probe_evaluations"] != 2
                    or row["routing"]["controller_sha256"] != digest_bytes(engine.controller(arm).encode())
                    for position, (row, task) in enumerate(zip(rows, tasks)))):
                raise ValueError("Omitted task/negative, nonisolated actor or escaped cost/policy cap")
            if replay:
                engine.verify_stream(tasks, arm, margin, rows, isolated=True)
            summaries[str(seed)][arm], windows[str(seed)][arm] = engine.summary(rows), v31.windows(rows)
        adaptive = arms["adaptive"]["episodes"]
        for arm in engine.ARMS[1:]:
            controls = arms[arm]["episodes"]
            pairs[str(seed)][arm] = {
                "adaptive_only_solved": sum(a["solved"] and not b["solved"] for a, b in zip(adaptive, controls)),
                "control_only_solved": sum(b["solved"] and not a["solved"] for a, b in zip(adaptive, controls)),
                "both_solved": sum(a["solved"] and b["solved"] for a, b in zip(adaptive, controls)),
                "neither_solved": sum(not a["solved"] and not b["solved"] for a, b in zip(adaptive, controls))}
    totals = {arm: {key: sum(row[arm][key] for row in summaries.values())
                       for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solutions")}
              for arm in engine.ARMS}
    routes = Counter("probe" if row["routing"]["used_probe_root"] else "identity"
                     for arms in record["streams"].values() for row in arms["adaptive"]["episodes"])
    all_control_advantage = all(totals["adaptive"]["solved"] > totals[arm]["solved"] for arm in engine.ARMS[1:])
    growing_positive = all(all(window["new_solutions"] > 0 and window["archive_semantic_size"] >
                              (rows[index - 1]["archive_semantic_size"] if index else 0)
                              for index, window in enumerate(rows))
                           for rows in (arms["adaptive"] for arms in windows.values()))
    predicates = {"complete_frozen_evidence_caps_and_recovery": True,
                  "more_solved_than_cold_and_greedy": all(totals["adaptive"]["solved"] > totals[arm]["solved"]
                                                         for arm in ("cold", "greedy")),
                  "cost_no_more_than_cold": totals["adaptive"]["evaluations"] <= totals["cold"]["evaluations"],
                  "no_cold_solved_regression_per_seed": all(row["adaptive"]["solved"] >= row["cold"]["solved"]
                                                           for row in summaries.values()),
                  "probe_and_identity_roots_both_exercised": routes["probe"] > 0 and routes["identity"] > 0,
                  "growing_archive_and_positive_new_solving_sources_every_window": growing_positive}
    positive = all(predicates.values())
    return {"schema": "mira-genesis-v33-finite-memory-adjudication-v1", "finite_archive_utility_positive": positive,
            "verdict": "POSITIVE_FINITE_ARCHIVE_UTILITY" if positive else "VALID_NEGATIVE_FINITE_ARCHIVE_UTILITY",
            "predicates": predicates, "strict_all_control_solved_advantage": all_control_advantage, "totals": totals, "summaries": summaries, "windows": windows,
            "paired_solved": pairs, "adaptive_routes": dict(routes), "freeze_sha256": frozen["freeze_sha256"],
            "policy_sha256": programs.PARENT_SHA256, "margin_milli": margin,
            "fresh_tasks_per_arm": frozen["tasks_per_arm"], "track": "B", "scientific_external_model_calls": 0,
            "scope": "FINITE_PROJECT_AUTHORED_ACTIVE_PROBE_ROOT_SELECTION_WITH_UNCHANGED_G7",
            "new_recursive_transition_established": False, "l9_open_ended_passed": False,
            "l10_independent_passed": False, "independent_task_authorship": False}


def run():
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if frozen["python_version"] != sys.version.split()[0]:
        raise ValueError("Canonical Python version differs from freeze")
    if any((DIRECTORY / name).exists() or (DIRECTORY / name).is_symlink()
           for name in ("V33_RESERVATION.json", "V33_COMPLETION.json", "V33_ATTEMPT_RAW.json.gz",
                        "V33_FINAL_ADJUDICATION.json", "V33_INTERRUPTION.json")):
        raise ValueError("An attempt is already reserved, consumed or interrupted; never rerun")
    reservation = {"schema": "mira-genesis-v33-single-attempt-reservation-v1", "status": "RESERVED",
                   "freeze_sha256": frozen["freeze_sha256"], "canonical_attempts": 1}
    storage.publish_json(RESERVATION, reservation)
    record = {"schema": "mira-genesis-v33-complete-attempt-v1", "status": "STARTED",
              "freeze_sha256": frozen["freeze_sha256"], "canonical_attempts": 1,
              "policy_sha256": programs.PARENT_SHA256, "python_version": frozen["python_version"],
              "track": "B", "scientific_external_model_calls": 0,
              "margin_milli": frozen["margin_milli"], "streams": {}}
    try:
        for seed in bank.FRESH_SEEDS:
            tasks = bank.stream(seed)
            record["streams"][str(seed)] = {}
            for arm in engine.ARMS:
                path = DIRECTORY / f"s{seed}-{arm}.jsonl"
                engine.run_stream(tasks, arm, frozen["margin_milli"], path, frozen["freeze_sha256"], stop_after=6)
                checkpoint = Archive(path, engine.binding(tasks, arm, frozen["margin_milli"],
                                                         frozen["freeze_sha256"])).read()[-1]["sha256"]
                rows, head = engine.run_stream(tasks, arm, frozen["margin_milli"], path, frozen["freeze_sha256"])
                record["streams"][str(seed)][arm] = {"episodes": rows, "journal": storage.read_regular(path).decode(),
                    "head_sha256": head, "checkpoint_position": 6, "checkpoint_head_sha256": checkpoint}
                print("completed", seed, arm, engine.summary(rows), flush=True)
        record["status"] = "COMPLETED"
        # Complete raw evidence is preserved before expensive receipt adjudication.
        storage.publish_once(DIRECTORY / "V33_ATTEMPT_RAW.json.gz", gzip.compress(canonical(record) + b"\n", mtime=0))
        result = adjudicate(record, frozen, replay=True)
        storage.complete(DIRECTORY, record, result)
        return result
    except BaseException as error:
        storage.publish_json(DIRECTORY / "V33_INTERRUPTION.json", {
            "schema": "mira-genesis-v33-interruption-v1", "freeze_sha256": frozen["freeze_sha256"],
            "canonical_attempts": 1, "status": "INTERRUPTED", "error_class": type(error).__name__,
            "partial_streams_sha256": digest(record["streams"]),
            "journal_bytes_sha256": {path.name: digest_bytes(storage.read_regular(path))
                                     for path in DIRECTORY.glob("s*-*.jsonl")}})
        raise


def check(*, require_result=False, replay=True):
    if not freeze.PATH.exists():
        if require_result:
            raise ValueError("Missing prospective V33 freeze")
        return {"status": "UNFROZEN", "l9_open_ended_passed": False, "l10_independent_passed": False}
    frozen = json.loads(freeze.PATH.read_text())
    freeze.verify(frozen)
    if not COMPLETION.exists():
        if require_result or RESERVATION.exists():
            raise ValueError("Missing completion; any reserved attempt remains consumed")
        return {"status": "FROZEN_NOT_EXECUTED", "l9_open_ended_passed": False, "l10_independent_passed": False}
    record, stored = storage.read_complete(DIRECTORY)
    result = adjudicate(record, frozen, replay=replay)
    if digest(result) != digest(stored):
        raise ValueError("Stored verdict differs from full evidence")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    parser.add_argument("--no-replay", action="store_true")
    args = parser.parse_args()
    result = run() if args.action == "run" else check(replay=not args.no_replay)
    print(json.dumps({key: value for key, value in result.items() if key not in ("windows", "summaries", "paired_solved")}, indent=2))
