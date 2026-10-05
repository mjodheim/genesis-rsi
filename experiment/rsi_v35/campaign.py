"""Single-attempt native campaign, segmented immutable evidence and process recovery."""
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
from experiment.rsi_v35 import bank, engine, native

FREEZE = ROOT / "experiment/rsi_v35/FRESH_FREEZE.json"


def population(mode):
    seeds = bank.DEV_SEEDS if mode == "pilot" else bank.FRESH_SEEDS
    epochs, count = (4, 8) if mode == "pilot" else (bank.EPOCHS, bank.TASKS_PER_EPOCH)
    return {f"{seed}-{domain}": bank.stream(seed, domain, epochs=epochs, tasks_per_epoch=count)
            for seed in seeds for domain in native.DOMAINS}


def inputs():
    paths = []
    for version in (25, 27, 29, 31, 32, 35):
        paths.extend((ROOT / f"experiment/rsi_v{version}").glob("*.py"))
    paths.extend((ROOT / "experiment/rsi_v35/PROTOCOL.md",
                  ROOT / "tests/test_rsi_v35.py",
                  ROOT / "docs/IP_REVIEWS/V35_NATIVE_SUSTAINED_ARCHIVE_REVIEW.md",
                  ROOT / "results/rsi-v30/target-20261001/G7_SELECTED_POLICY.py"))
    return {p.relative_to(ROOT).as_posix(): digest_bytes(p.read_bytes()) for p in sorted(paths)}


def head():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def manifest(mode):
    tasks = population(mode)
    return {"schema": "mira-genesis-v35-native-campaign-v1", "mode": mode, "track": "B",
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
    if mode == "fresh":
        # Every enabling input must have existed byte-exactly in the apparatus commit.
        for path, sha in value["inputs"].items():
            raw = subprocess.check_output(["git", "show", value["git_head"] + ":" + path], cwd=ROOT)
            if digest_bytes(raw) != sha:
                raise ValueError("Fresh apparatus was not committed before behavior")
    return True


def freeze():
    value = manifest("fresh")
    verify_manifest(value)
    storage.publish_json(FREEZE, value)
    return digest(value)


def binding(tasks, arm, apparatus, prior_head, history, isolated):
    return {"schema": "mira-genesis-v35-epoch-binding-v1", "tasks_sha256": digest(tasks),
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
        if (digest(rows[:size]) != receipt["prefix_sha256"]
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
    predicates = {"four_final_window_discoveries": True, "positive_final_window_rate": True,
                  "strict_epoch_archive_and_solved_growth": True, "four_branches_and_rediscovery": True,
                  "beats_both_controls_each_seed_domain": True, "cost_no_greater_than_cold": True,
                  "reaches_declared_length": True}
    for arms in cohorts.values():
        archive = arms["archive"]
        for row in archive[-6:]:
            predicates["four_final_window_discoveries"] &= row["first_solving_semantics"] >= 4
            predicates["positive_final_window_rate"] &= row["first_solving_semantics"] * 112 >= row["evaluations"]
        old_size = old_solved = 0
        for row in archive:
            predicates["strict_epoch_archive_and_solved_growth"] &= (
                row["archive_size"] > old_size and row["solved_semantic_size"] > old_solved)
            old_size, old_solved = row["archive_size"], row["solved_semantic_size"]
        predicates["four_branches_and_rediscovery"] &= (all(r["branches"] >= 4 for r in archive)
                                                       and sum(r["rediscoveries"] for r in archive) > 0)
        solved = sum(r["solved"] for r in archive)
        predicates["beats_both_controls_each_seed_domain"] &= all(
            solved > sum(r["solved"] for r in arms[control]) for control in ("cold", "greedy"))
        predicates["cost_no_greater_than_cold"] &= (sum(r["evaluations"] for r in archive)
                                                  <= sum(r["evaluations"] for r in arms["cold"]))
        predicates["reaches_declared_length"] &= archive[-1]["max_solved_length"] == (4 if mode == "pilot" else 12)
    totals = {arm: {key: sum(r[key] for arms in cohorts.values() for r in arms[arm])
                    for key in ("tasks", "solved", "evaluations", "policy_calls", "first_solving_semantics", "rediscoveries")}
              for arm in engine.ARMS}
    return {"scope": "NATIVE_APPEND_EXTENSION_" + mode.upper(), "track": "B", "cohorts": cohorts,
            "totals": totals, "predicates": predicates,
            "scoped_sustained_assay_passed": mode == "fresh" and all(predicates.values()),
            "l9_general_open_ended_passed": False, "l10_independent_passed": False,
            "new_policy_generation": False, "recovery": "FRESH_PROCESS_EACH_EPOCH" +
            ("_AND_DECLARED_MID_EPOCH_STOP" if mode == "fresh" else "")}


def collect(root, *, replay):
    root = Path(root)
    value = storage.read_json(root / "MANIFEST.json")
    verify_manifest(value)
    cohorts, heads = {}, {}
    for label, tasks in population(value["mode"]).items():
        cohorts[label], heads[label] = {}, {}
        for arm in engine.ARMS:
            _, previous_head, reports = prior(root / label / arm, tasks, arm, digest(value),
                                              max(t["epoch"] for t in tasks) + 1, value["isolated"], replay=replay)
            cohorts[label][arm], heads[label][arm] = reports, previous_head
    if value["mode"] == "fresh":
        destination = root / "81173-relational-sql/archive/epoch-006"
        stop = storage.read_json(destination / "STOP_BOUNDARY.json")
        recovery = storage.read_json(destination / "RECOVERY.json")
        earlier_tasks = population("fresh")["81173-relational-sql"]
        earlier, _, _ = prior(root / "81173-relational-sql/archive", earlier_tasks, "archive", digest(value), 6, True)
        rows = json.loads(gzip.decompress(storage.read_regular(destination / "EVIDENCE.json.gz")))
        if (stop["completed_tasks"] != 16 or stop["prefix_sha256"] != digest(rows[:16])
                or stop["history_sha256"] != digest(engine.history_from(rows[:16], earlier))
                or recovery != {"boundary_sha256": digest(stop), "prefix_reexecuted": False,
                                "restored_history_sha256": stop["history_sha256"], "completed_tasks_at_resume": 16}):
            raise ValueError("Declared recovery not demonstrated")
    return adjudicate(cohorts, value["mode"]), heads


def run(root, mode, *, workers=4):
    root = Path(root)
    if (root / "COMPLETION.json").exists():
        raise FileExistsError("Campaign completed; use check, never rerun")
    value = storage.read_json(FREEZE) if mode == "fresh" else manifest(mode)
    verify_manifest(value)
    if mode == "fresh":
        committed = subprocess.check_output(["git", "show", "HEAD:experiment/rsi_v35/FRESH_FREEZE.json"], cwd=ROOT)
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
    reservation = {"manifest_sha256": digest(value), "status": "RESERVED_SINGLE_ATTEMPT",
                   "maximum_charged_evaluations": value["tasks_per_arm"] * 3 * 14}
    if (root / "RESERVATION.json").exists():
        if storage.read_json(root / "RESERVATION.json") != reservation:
            raise ValueError("Changed single attempt reservation")
    else:
        storage.publish_json(root / "RESERVATION.json", reservation)

    def cohort(item):
        label, arm = item
        epochs = 4 if mode == "pilot" else 12
        for epoch in range(epochs):
            command = [sys.executable, "-m", "experiment.rsi_v35.campaign", "worker", "--output-dir", str(root),
                       "--label", label, "--arm", arm, "--epoch", str(epoch)]
            declared = mode == "fresh" and label == "81173-relational-sql" and arm == "archive" and epoch == 6
            if declared:
                subprocess.run(command + ["--stop-after", "16"], cwd=ROOT, check=True)
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
