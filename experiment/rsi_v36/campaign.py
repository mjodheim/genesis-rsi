"""V36 segmented campaign, derived from V35 with prospective complete audits."""
import argparse
import gzip
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank, engine

FREEZE = ROOT / "experiment/rsi_v36/FRESH_FREEZE.json"


def population(mode):
    seeds = bank.DEV_SEEDS if mode == "pilot" else bank.FRESH_SEEDS
    epochs, count = (6, 8) if mode == "pilot" else (bank.EPOCHS, bank.TASKS_PER_EPOCH)
    return {f"{seed}-{domain}": bank.stream(seed, domain, epochs=epochs, tasks_per_epoch=count)
            for seed in seeds for domain in native.DOMAINS}


def inputs():
    paths = []
    for version in (23, 25, 27, 29, 31, 32, 35, 36):
        paths.extend((ROOT / f"experiment/rsi_v{version}").glob("*.py"))
    paths.extend((ROOT / "experiment/rsi_v36/PROTOCOL.md",
                  ROOT / "tests/test_rsi_v36.py",
                  ROOT / "docs/IP_REVIEWS/V36_LEARNED_RECOMBINATION_REVIEW.md",
                  ROOT / "results/rsi-v30/target-20261001/G7_SELECTED_POLICY.py"))
    return {p.relative_to(ROOT).as_posix(): digest_bytes(p.read_bytes()) for p in sorted(paths)}


def head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def manifest(mode):
    tasks = population(mode)
    return {"schema": "mira-genesis-v36-native-campaign-v1", "mode": mode, "track": "B",
            "git_head": head(), "inputs": inputs(), "runtime": native.runtime(),
            "isolated": mode == "fresh", "arms": list(engine.ARMS),
            "population_sha256": digest(tasks), "streams": {k: digest(v) for k, v in tasks.items()},
            "tasks_per_arm": sum(map(len, tasks.values())), "max_evaluations": engine.MAX_EVALUATIONS,
            "scientific_external_model_calls": 0}


def verify_manifest(value):
    mode = value["mode"]
    expected = manifest(mode)
    expected["git_head"] = value["git_head"]
    if expected != value:
        raise ValueError("Changed apparatus, curriculum, runtime or campaign manifest")
    subprocess.run(["git", "merge-base", "--is-ancestor", value["git_head"], "HEAD"], cwd=ROOT, check=True)
    # Pilot too: bind every enabling input before any campaign behavior.
    for path, sha in value["inputs"].items():
        raw = subprocess.check_output(["git", "show", value["git_head"] + ":" + path], cwd=ROOT)
        if digest_bytes(raw) != sha:
            raise ValueError("Apparatus was not committed before behavior")
    if mode == "fresh" and FREEZE.exists() and storage.read_json(FREEZE) != value:
        raise ValueError("Fresh manifest differs from prospective freeze")
    if mode == "fresh" and FREEZE.exists():
        frozen_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", FREEZE.relative_to(ROOT).as_posix()],
            cwd=ROOT, text=True).strip()
        frozen = subprocess.check_output(["git", "show", frozen_commit + ":" + FREEZE.relative_to(ROOT).as_posix()], cwd=ROOT)
        if frozen != storage.read_regular(FREEZE):
            raise ValueError("Changed committed prospective freeze")
        subprocess.run(["git", "merge-base", "--is-ancestor", value["git_head"], frozen_commit], cwd=ROOT, check=True)
        subprocess.run(["git", "merge-base", "--is-ancestor", frozen_commit, "HEAD"], cwd=ROOT, check=True)
    return True


def freeze():
    pilot_root = ROOT / "results/local/v36-recombination-pilot-20261004"
    pilot = check(pilot_root)
    if not pilot["development_progression_passed"]:
        raise ValueError("V36 pilot progression failed; no fresh attempt authorized by this protocol")
    value = manifest("fresh")
    verify_manifest(value)
    storage.publish_json(FREEZE, value)
    return digest(value)


def binding(tasks, arm, apparatus, prior_head, history, isolated):
    return {"schema": "mira-genesis-v36-epoch-binding-v1", "tasks_sha256": digest(tasks),
            "arm": arm, "manifest_sha256": apparatus, "prior_epoch_head": prior_head,
            "history_sha256": digest(history), "isolated": isolated, "full_task_reserve": 14}


def journal_rows(archive, tasks):
    rows, pending = [], None
    for event in archive.read()[1:]:
        data = event["data"]
        if event["kind"] == "start":
            if pending is not None:
                raise ValueError("Unfinished reservation: no retry")
            expected = {"position": len(rows), "task_sha256": digest(tasks[len(rows)]), "reserved_evaluations": 14}
            if data != expected:
                raise ValueError("Changed task reservation or budget")
            pending = data
        elif event["kind"] == "episode":
            if (pending is None or data["task_sha256"] != pending["task_sha256"]
                    or data["charged_evaluations"] > 14):
                raise ValueError("Unreserved or overspent episode")
            rows.append(data)
            pending = None
        else:
            raise ValueError("Unknown journal event")
    if pending is not None:
        raise ValueError("Unfinished reserved task; quarantine and charge fourteen, no free retry")
    return rows


def read_epoch(directory, tasks, arm, apparatus, prior_head, previous, isolated, *, replay=False):
    completion = storage.read_json(directory / "COMPLETION.json")
    raw = storage.read_regular(directory / "EVIDENCE.json.gz")
    rows = json.loads(gzip.decompress(raw))
    report = storage.read_json(directory / "REPORT.json")
    archive = Archive(directory / "journal.jsonl", binding(tasks, arm, apparatus, prior_head, previous, isolated))
    if (len(rows) != len(tasks) or digest_bytes(raw) != completion["raw_sha256"]
            or digest(report) != completion["report_sha256"] or completion["manifest_sha256"] != apparatus
            or journal_rows(archive, tasks) != rows or engine.summary(rows, previous) != report):
        raise ValueError("Altered epoch evidence, state or accounting")
    archive.read(expected_head=completion["head_sha256"])
    history = previous
    for index, (task, row) in enumerate(zip(tasks, rows)):
        if replay:
            engine.verify_episode(task, task["epoch"] * len(tasks) + index, history, arm, row, isolated=isolated)
        history = engine.history_from([row], history)
    return rows, completion["head_sha256"], history, report


def prior(directory, tasks, arm, apparatus, epoch, isolated, *, replay=False):
    history, previous_head, reports = {}, ZERO, []
    for index in range(epoch):
        subset = [t for t in tasks if t["epoch"] == index]
        _, previous_head, history, report = read_epoch(directory / f"epoch-{index:03}", subset, arm,
                                                      apparatus, previous_head, history, isolated, replay=replay)
        reports.append(report)
    return history, previous_head, reports


def run_epoch(root, label, arm, epoch, *, stop_after=None):
    root = Path(root)
    value = storage.read_json(root / "MANIFEST.json")
    tasks = population(value["mode"])[label]
    isolated, apparatus = value["isolated"], digest(value)
    directory = root / label / arm
    history, previous_head, _ = prior(directory, tasks, arm, apparatus, epoch, isolated)
    previous = history
    subset = [t for t in tasks if t["epoch"] == epoch]
    destination = directory / f"epoch-{epoch:03}"
    if (destination / "COMPLETION.json").exists():
        return read_epoch(destination, subset, arm, apparatus, previous_head, previous, isolated)[3]
    journal = destination / "journal.jsonl"
    archive = Archive(journal, binding(subset, arm, apparatus, previous_head, history, isolated), create=not journal.exists())
    rows = journal_rows(archive, subset)
    start = sum(t["epoch"] < epoch for t in tasks)
    for i, row in enumerate(rows):
        engine.verify_episode(subset[i], start + i, history, arm, row, isolated=isolated)
        history = engine.history_from([row], history)
    boundary = destination / "STOP_BOUNDARY.json"
    if boundary.exists():
        receipt = storage.read_json(boundary)
        size = receipt["completed_tasks"]
        events = archive.read()
        restored_prefix = engine.history_from(rows[:size], previous)
        if (digest(rows[:size]) != receipt["prefix_sha256"]
                or digest(restored_prefix) != receipt["history_sha256"]
                or events[2 * size]["sha256"] != receipt["head_sha256"]):
            raise ValueError("Altered interrupted prefix; refuse recovery")
        if stop_after is None and not (destination / "RECOVERY.json").exists():
            storage.publish_json(destination / "RECOVERY.json", {
                "boundary_sha256": digest(receipt), "prefix_reexecuted": False,
                "restored_history_sha256": digest(history), "completed_tasks_at_resume": len(rows)})
    for i in range(len(rows), len(subset)):
        if stop_after is not None and i >= stop_after:
            receipt = {"completed_tasks": i, "head_sha256": archive.read()[-1]["sha256"],
                       "prefix_sha256": digest(rows), "history_sha256": digest(history)}
            if boundary.exists():
                if storage.read_json(boundary) != receipt:
                    raise ValueError("Changed declared interruption")
            else:
                storage.publish_json(boundary, receipt)
            return {"status": "STOPPED_AT_COMPLETED_TASK_BOUNDARY", "completed_tasks": i}
        current_head = archive.read()[-1]["sha256"]
        current_head = archive.append("start", {"position": i, "task_sha256": digest(subset[i]),
                                                "reserved_evaluations": 14}, expected_head=current_head)
        row = engine.episode(subset[i], start + i, history, arm, isolated=isolated)
        engine.verify_episode(subset[i], start + i, history, arm, row, isolated=isolated)
        archive.append("episode", row, expected_head=current_head)
        rows.append(row)
        history = engine.history_from([row], history)
    report = engine.summary(rows, previous)
    raw = gzip.compress(canonical(rows) + b"\n", mtime=0)
    for name, content in (("EVIDENCE.json.gz", raw), ("REPORT.json", canonical(report) + b"\n")):
        path = destination / name
        if path.exists():
            if storage.read_regular(path) != content:
                raise ValueError("Attempt to replace preserved epoch evidence")
        else:
            storage.publish_once(path, content)
    storage.publish_json(destination / "COMPLETION.json", {"manifest_sha256": apparatus,
                         "raw_sha256": digest_bytes(raw), "report_sha256": digest(report),
                         "head_sha256": archive.read()[-1]["sha256"]})
    return report


def adjudicate(cohorts, mode):
    predicates = {"complete_warmup": True, "positive_each_transfer_epoch": True,
                  "beats_all_controls_each_seed_domain": True, "cost_no_greater_than_cold": True,
                  "strict_archive_and_solved_growth": True, "branching_and_rediscovery": True}
    for arms in cohorts.values():
        archive = arms["archive"]
        predicates["complete_warmup"] &= all(r["solved"] == r["tasks"] for r in archive[:3])
        predicates["positive_each_transfer_epoch"] &= all(r["first_solving_semantics"] >= 1 for r in archive[3:])
        solved = sum(r["solved"] for r in archive[3:])
        predicates["beats_all_controls_each_seed_domain"] &= all(
            solved > sum(r["solved"] for r in arms[control][3:]) for control in engine.ARMS if control != "archive")
        predicates["cost_no_greater_than_cold"] &= (sum(r["evaluations"] for r in archive)
                                                  <= sum(r["evaluations"] for r in arms["cold"]))
        old_size = old_solved = 0
        for row in archive:
            predicates["strict_archive_and_solved_growth"] &= (
                row["archive_size"] > old_size and row["solved_semantic_size"] > old_solved)
            old_size, old_solved = row["archive_size"], row["solved_semantic_size"]
        predicates["branching_and_rediscovery"] &= (archive[2]["branches"] == 4
                                                    and sum(r["rediscoveries"] for r in archive) > 0)
    keys = ("tasks", "solved", "evaluations", "policy_calls", "first_solving_semantics", "rediscoveries",
            "splice_evaluations", "splice_solves")
    totals = {arm: {key: sum(r[key] for arms in cohorts.values() for r in arms[arm])
                    for key in keys} for arm in engine.ARMS}
    transfer = {arm: {key: sum(r[key] for arms in cohorts.values() for r in arms[arm][3:])
                      for key in keys} for arm in engine.ARMS}
    return {"scope": "NATIVE_WHOLE_BODY_RECOMBINATION_" + mode.upper(), "track": "B", "cohorts": cohorts,
            "totals": totals, "transfer_totals": transfer, "predicates": predicates,
            "development_progression_passed": mode == "pilot" and all(predicates.values()),
            "scoped_recombination_assay_passed": mode == "fresh" and all(predicates.values()),
            "l9_general_open_ended_passed": False, "l10_independent_passed": False,
            "new_policy_generation": False, "recovery": "FRESH_PROCESS_EACH_EPOCH_AND_MID_EPOCH_STOP"}


def reservation(value):
    return {"manifest_sha256": digest(value), "status": "RESERVED_SINGLE_ATTEMPT",
            "maximum_charged_evaluations": value["tasks_per_arm"] * len(engine.ARMS) * engine.MAX_EVALUATIONS}


def audit_recovery(root, value):
    seed = bank.DEV_SEEDS[0] if value["mode"] == "pilot" else bank.FRESH_SEEDS[0]
    label, epoch, size = f"{seed}-relational-sql", 3, 4 if value["mode"] == "pilot" else 8
    tasks = population(value["mode"])[label]
    directory = root / label / "archive" / f"epoch-{epoch:03}"
    earlier, old_head, _ = prior(root / label / "archive", tasks, "archive", digest(value), epoch, value["isolated"])
    subset = [t for t in tasks if t["epoch"] == epoch]
    journal = Archive(directory / "journal.jsonl", binding(subset, "archive", digest(value), old_head, earlier, value["isolated"]))
    rows, events = journal_rows(journal, subset), journal.read()
    stop = {"completed_tasks": size, "head_sha256": events[2 * size]["sha256"],
            "prefix_sha256": digest(rows[:size]), "history_sha256": digest(engine.history_from(rows[:size], earlier))}
    if storage.read_json(directory / "STOP_BOUNDARY.json") != stop:
        raise ValueError("Interrupted prefix receipt differs from exact ledger head/history")
    expected = {"boundary_sha256": digest(stop), "prefix_reexecuted": False,
                "restored_history_sha256": stop["history_sha256"], "completed_tasks_at_resume": size}
    if storage.read_json(directory / "RECOVERY.json") != expected:
        raise ValueError("Recovery receipt differs from exact interrupted state")


def collect(root, *, replay):
    root = Path(root)
    value = storage.read_json(root / "MANIFEST.json")
    verify_manifest(value)
    if storage.read_json(root / "RESERVATION.json") != reservation(value):
        raise ValueError("Altered global reservation")
    cohorts, heads = {}, {}
    for label, tasks in population(value["mode"]).items():
        cohorts[label], heads[label] = {}, {}
        for arm in engine.ARMS:
            _, previous_head, reports = prior(root / label / arm, tasks, arm, digest(value),
                                              max(t["epoch"] for t in tasks) + 1, value["isolated"], replay=replay)
            cohorts[label][arm], heads[label][arm] = reports, previous_head
    audit_recovery(root, value)
    return adjudicate(cohorts, value["mode"]), heads


def run(root, mode, *, workers=4):
    root = Path(root)
    if (root / "COMPLETION.json").exists():
        raise FileExistsError("Campaign completed; use check, never rerun")
    value = storage.read_json(FREEZE) if mode == "fresh" else manifest(mode)
    verify_manifest(value)
    if mode == "fresh":
        committed = subprocess.check_output(["git", "show", "HEAD:experiment/rsi_v36/FRESH_FREEZE.json"], cwd=ROOT)
        if committed != storage.read_regular(FREEZE):
            raise ValueError("Commit prospective freeze before the first fresh behavior")
    commitment = root / "MANIFEST.json"
    if commitment.exists():
        recorded = storage.read_json(commitment)
        verify_manifest(recorded)
        if recorded != value:
            raise ValueError("Changed campaign commitment")
    else:
        storage.publish_json(commitment, value)
    reserved = reservation(value)
    if (root / "RESERVATION.json").exists():
        if storage.read_json(root / "RESERVATION.json") != reserved:
            raise ValueError("Changed single attempt reservation")
    else:
        storage.publish_json(root / "RESERVATION.json", reserved)

    def cohort(item):
        label, arm = item
        epochs = 6 if mode == "pilot" else 10
        for epoch in range(epochs):
            command = [sys.executable, "-m", "experiment.rsi_v36.campaign", "worker", "--output-dir", str(root),
                       "--label", label, "--arm", arm, "--epoch", str(epoch)]
            declared = label == f"{bank.DEV_SEEDS[0] if mode == 'pilot' else bank.FRESH_SEEDS[0]}-relational-sql" and arm == "archive" and epoch == 3
            if declared:
                subprocess.run(command + ["--stop-after", "4" if mode == "pilot" else "8"], cwd=ROOT, check=True)
            subprocess.run(command, cwd=ROOT, check=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(cohort, ((label, arm) for label in population(mode) for arm in engine.ARMS)))
    report, heads = collect(root, replay=False)  # Every episode was verified before journal publication.
    storage.publish_json(root / "REPORT.json", report)
    storage.publish_json(root / "COMPLETION.json", {"manifest_sha256": digest(value),
                         "report_sha256": digest(report), "heads": heads})
    return report


def check(root):
    root = Path(root)
    report, heads = collect(root, replay=True)
    value = storage.read_json(root / "MANIFEST.json")
    if any(t["tasks"] != value["tasks_per_arm"] or t["evaluations"] > value["tasks_per_arm"] * 14
           for t in report["totals"].values()):
        raise ValueError("Omitted tasks or global evaluation cap exceeded")
    completion = storage.read_json(root / "COMPLETION.json")
    if (storage.read_json(root / "REPORT.json") != report
            or completion != {"manifest_sha256": digest(storage.read_json(root / "MANIFEST.json")),
                              "report_sha256": digest(report), "heads": heads}):
        raise ValueError("Altered campaign report, completion or heads")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "run", "check", "worker"))
    parser.add_argument("--mode", choices=("pilot", "fresh"), default="pilot")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--label")
    parser.add_argument("--arm", choices=engine.ARMS)
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--stop-after", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.action == "freeze":
        result = freeze()
    elif args.action == "worker":
        result = run_epoch(args.output_dir, args.label, args.arm, args.epoch, stop_after=args.stop_after)
    elif args.action == "run":
        result = run(args.output_dir, args.mode, workers=args.workers)
    else:
        result = check(args.output_dir)
    print(json.dumps({"label": args.label, "arm": args.arm, "epoch": args.epoch, "result": result}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
