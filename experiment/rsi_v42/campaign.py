"""Single-assignment epoch evidence, with a committed external receipt between epochs."""
import argparse
import gzip
import json
import sys
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import storage
from experiment.rsi_v42 import bank, engine, freeze, programs

DIRECTORY = ROOT / "results/rsi-v42/continuing-20261002"
NAMES = ("RESERVATION.json", "ATTEMPT_RAW.json.gz", "FINAL_ADJUDICATION.json", "COMPLETION.json")


def directory(epoch):
    if type(epoch) is not int or not 0 <= epoch < programs.MAX_STEPS:
        raise ValueError("Epoch exceeds fixed governance capacity")
    return DIRECTORY / f"epoch-{epoch:03d}"


def read_complete(epoch, *, committed=False):
    where = directory(epoch)
    reservation, verdict, receipt = (storage.read_json(where / name) for name in (NAMES[0], NAMES[2], NAMES[3]))
    raw = storage.read_regular(where / NAMES[1])
    encoded = gzip.decompress(raw)
    record = json.loads(encoded)
    if (encoded != canonical(record) + b"\n" or reservation.get("schema") != "mira-genesis-v42-epoch-reservation-v1"
            or reservation.get("status") != "RESERVED" or receipt.get("schema") != "mira-genesis-v42-epoch-completion-v1"
            or receipt.get("status") != "COMPLETED" or receipt.get("raw_sha256") != digest_bytes(raw)
            or receipt.get("uncompressed_sha256") != digest_bytes(encoded) or receipt.get("record_sha256") != digest(record)
            or receipt.get("verdict_sha256") != digest(verdict)
            or receipt.get("reservation_sha256") != digest_bytes(storage.read_regular(where / NAMES[0]))
            or any(record.get(key) != receipt.get(key) or record.get(key) != reservation.get(key)
                   for key in ("epoch", "freeze_sha256", "previous_receipt_sha256", "tasks_sha256"))
            or record.get("epoch") != epoch):
        raise ValueError("Altered epoch reservation, raw, verdict, continuation or completion")
    if committed:
        for name in NAMES:
            path = where / name
            if freeze.git("show", "HEAD:" + path.relative_to(ROOT).as_posix()) != path.read_bytes():
                raise ValueError("Previous epoch must be externally committed before continuation")
    return record, verdict, receipt


def past(epoch, frozen, *, replay=False, committed=False):
    histories = {str(seed): {arm: [] for arm in engine.ARMS} for seed in bank.FRESH_SEEDS}
    previous = None
    verdicts = []
    for old_epoch in range(epoch):
        record, stored, receipt = read_complete(old_epoch, committed=committed)
        computed = adjudicate(record, frozen, histories, previous, replay=replay)
        if digest(computed) != digest(stored):
            raise ValueError("Stored earlier verdict differs from full epoch evidence")
        for seed, arms in record["streams"].items():
            for arm, stream in arms.items():
                histories[seed][arm].extend(stream["episodes"])
        previous = digest_bytes(storage.read_regular(directory(old_epoch) / NAMES[3]))
        verdicts.append(computed)
    return histories, previous, verdicts


def adjudicate(record, frozen, histories, previous, *, replay=True):
    epoch = record.get("epoch")
    if (set(record) != {"schema", "status", "epoch", "freeze_sha256", "previous_receipt_sha256", "tasks_sha256",
                       "policy_sha256", "python_version", "track", "scientific_external_model_calls", "streams"}
            or record["schema"] != "mira-genesis-v42-complete-epoch-v1" or record["status"] != "COMPLETED"
            or type(epoch) is not int or not 0 <= epoch < programs.MAX_STEPS
            or record["freeze_sha256"] != frozen["freeze_sha256"] or record["previous_receipt_sha256"] != previous
            or record["tasks_sha256"] != digest({str(seed): bank.stream(seed, epoch) for seed in bank.FRESH_SEEDS})
            or record["policy_sha256"] != programs.PARENT_SHA256 or record["python_version"] != frozen["python_version"]
            or record["track"] != "B" or record["scientific_external_model_calls"] != 0
            or set(record["streams"]) != {str(seed) for seed in bank.FRESH_SEEDS}):
        raise ValueError("Altered epoch, authority, task population or missing evidence")
    summaries = {}
    for seed in bank.FRESH_SEEDS:
        key, tasks = str(seed), bank.stream(seed, epoch)
        arms = record["streams"][key]
        if set(arms) != set(engine.ARMS):
            raise ValueError("Omitted matched archive control")
        summaries[key] = {}
        for arm, stream in arms.items():
            prefix = histories[key][arm]
            binding = engine.binding(tasks, arm, frozen["freeze_sha256"], previous, prefix)
            events = Archive.decode(stream["journal"].encode())
            if (not events or events[0]["data"] != binding or events[-1]["sha256"] != stream["head_sha256"]
                    or stream["checkpoint_position"] != 3 or len(events) < 7
                    or events[6]["sha256"] != stream["checkpoint_head_sha256"]):
                raise ValueError("Altered checkpoint, journal, history or externally retained head")
            with tempfile.TemporaryDirectory(prefix="v35-journal-receipt-") as temporary:
                path = Path(temporary) / "journal.jsonl"
                path.write_text(stream["journal"])
                rows = Archive(path, binding).episodes()
            if (digest(rows) != digest(stream["episodes"]) or len(rows) != len(tasks)
                    or any(row["position"] != position or row["absolute_position"] != len(prefix) + position
                           or row["task_sha256"] != digest(task) or row["charged_evaluations"] > engine.MAX_EVALUATIONS
                           or row["charged_evaluations"] != row["search"]["represented_requests"] + 4
                           or row["search"]["policy_sha256"] != programs.PARENT_SHA256
                           or row["search"]["caps"] != engine.CAPS.__dict__ or not row["search"]["isolated_policy_processes"]
                           or row["routing"]["controller_sha256"] != programs.PARENT_SHA256
                           or row["routing"]["controller_calls"] != 1 or row["routing"]["probe_evaluations"] != 2
                           or row["routing"].get("memory_policy") != "last_chance_stagnation5_frontier_v1"
                           for position, (row, task) in enumerate(zip(rows, tasks)))):
                raise ValueError("Omitted failure, substituted policy or escaped external cost/isolation caps")
            if replay:
                engine.verify_stream(tasks, arm, prefix, rows)
            summaries[key][arm] = engine.summary(rows, prefix)
    positive_growth = all(row["adaptive"]["archive_source_size"] > row["adaptive"]["archive_source_size_before"]
                          and row["adaptive"]["archive_behavior_size"] > row["adaptive"]["archive_behavior_size_before"]
                          and row["adaptive"]["new_solving_behaviors"] > 0 and row["adaptive"]["branching_parents"] > 0
                          for row in summaries.values())
    return {"schema": "mira-genesis-v42-measured-epoch-adjudication-v1", "epoch": epoch,
            "freeze_sha256": frozen["freeze_sha256"], "previous_receipt_sha256": previous,
            "summaries": summaries, "complete_frozen_evidence_caps_and_recovery": True,
            "positive_growth_and_discovery_this_epoch": positive_growth,
            "monitoring_status": "OBSERVED_POSITIVE_EPOCH" if positive_growth else "VALID_NEGATIVE_EPOCH",
            "scope": "PROJECT_AUTHORED_V42_LAST_CHANCE_CONTINUING_ARCHIVE_PREFIX",
            "track": "B", "scientific_external_model_calls": 0, "new_recursive_transition_established": False,
            "l9_open_ended_passed": False, "l10_independent_passed": False}


def run_epoch(epoch):
    frozen = storage.read_json(freeze.PATH)
    freeze.verify(frozen)
    if frozen["python_version"] != sys.version.split()[0]:
        raise ValueError("Canonical runtime differs from freeze")
    where = directory(epoch)
    if any((where / name).exists() or (where / name).is_symlink() for name in (*NAMES, "INTERRUPTION.json")):
        raise ValueError("Epoch already consumed, reserved or interrupted; never retry")
    histories, previous, _ = past(epoch, frozen, replay=False, committed=True)
    tasks_sha = digest({str(seed): bank.stream(seed, epoch) for seed in bank.FRESH_SEEDS})
    identity = {"epoch": epoch, "freeze_sha256": frozen["freeze_sha256"], "previous_receipt_sha256": previous, "tasks_sha256": tasks_sha}
    storage.publish_json(where / NAMES[0], {"schema": "mira-genesis-v42-epoch-reservation-v1", "status": "RESERVED", **identity})
    record = {"schema": "mira-genesis-v42-complete-epoch-v1", "status": "STARTED", **identity,
              "policy_sha256": programs.PARENT_SHA256, "python_version": frozen["python_version"], "track": "B",
              "scientific_external_model_calls": 0, "streams": {}}
    try:
        for seed in bank.FRESH_SEEDS:
            key, tasks = str(seed), bank.stream(seed, epoch)
            record["streams"][key] = {}
            for arm in engine.ARMS:
                path, prefix = where / f"s{seed}-{arm}.jsonl", histories[key][arm]
                engine.run_stream(tasks, arm, path, frozen["freeze_sha256"], previous, prefix, stop_after=3)
                checkpoint = Archive(path, engine.binding(tasks, arm, frozen["freeze_sha256"], previous, prefix)).read()[-1]["sha256"]
                rows, head = engine.run_stream(tasks, arm, path, frozen["freeze_sha256"], previous, prefix)
                record["streams"][key][arm] = {"episodes": rows, "journal": storage.read_regular(path).decode(),
                    "head_sha256": head, "checkpoint_position": 3, "checkpoint_head_sha256": checkpoint}
                print("completed", epoch, seed, arm, engine.summary(rows, prefix), flush=True)
        record["status"] = "COMPLETED"
        encoded = canonical(record) + b"\n"
        raw = gzip.compress(encoded, mtime=0)
        storage.publish_once(where / NAMES[1], raw)
        verdict = adjudicate(record, frozen, histories, previous)
        storage.publish_json(where / NAMES[2], verdict)
        receipt = {"schema": "mira-genesis-v42-epoch-completion-v1", "status": "COMPLETED", **identity,
                   "raw_sha256": digest_bytes(raw), "uncompressed_sha256": digest_bytes(encoded), "record_sha256": digest(record),
                   "verdict_sha256": digest(verdict), "reservation_sha256": digest_bytes(storage.read_regular(where / NAMES[0]))}
        storage.publish_json(where / NAMES[3], receipt)
        return verdict
    except BaseException as error:
        storage.publish_json(where / "INTERRUPTION.json", {"schema": "mira-genesis-v35-epoch-interruption-v1", **identity,
            "status": "INTERRUPTED", "error_class": type(error).__name__, "partial_streams_sha256": digest(record["streams"]),
            "journal_bytes_sha256": {path.name: digest_bytes(storage.read_regular(path)) for path in where.glob("s*-*.jsonl")}})
        raise


def check(*, require_prefix=False, replay=True):
    if not freeze.PATH.exists():
        if require_prefix:
            raise ValueError("Missing V35 prospective freeze")
        return {"status": "UNFROZEN", "l9_open_ended_passed": False, "l10_independent_passed": False}
    frozen = storage.read_json(freeze.PATH)
    freeze.verify(frozen)
    epochs = sorted(path for path in DIRECTORY.glob("epoch-*") if path.is_dir())
    if [path.name for path in epochs] != [f"epoch-{index:03d}" for index in range(len(epochs))]:
        raise ValueError("Omitted or reordered epoch")
    if require_prefix and len(epochs) < bank.INITIAL_EPOCHS:
        raise ValueError("Incomplete preregistered first prefix")
    histories, previous, verdicts = past(len(epochs), frozen, replay=replay)
    totals = {arm: {key: sum(engine.summary(rows)[key] for arms in histories.values() for a, rows in arms.items() if a == arm)
                   for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solving_behaviors")} for arm in engine.ARMS}
    predicates = {"complete_first_prefix": len(epochs) >= bank.INITIAL_EPOCHS,
        "positive_growth_and_discovery_every_seed_epoch": bool(verdicts) and all(v["positive_growth_and_discovery_this_epoch"] for v in verdicts),
        "more_solved_than_cold_and_greedy": all(totals["adaptive"]["solved"] > totals[a]["solved"] for a in ("cold", "greedy")),
        "cost_no_more_than_cold": totals["adaptive"]["evaluations"] <= totals["cold"]["evaluations"],
        "no_per_seed_cold_regression": all(engine.summary(arms["adaptive"])["solved"] >= engine.summary(arms["cold"])["solved"]
                                             for arms in histories.values())}
    return {"schema": "mira-genesis-v42-continuing-prefix-report-v1", "epochs": len(epochs), "totals": totals,
            "predicates": predicates, "measured_continuing_archive_positive": all(predicates.values()),
            "last_receipt_sha256": previous, "epoch_verdicts": verdicts,
            "l9_open_ended_passed": False, "l10_independent_passed": False, "new_recursive_transition_established": False,
            "finite_prefix_cannot_establish_open_endedness": True,
            "scope": "FINITE_V42_PREFIX_OF_CONTINUABLE_GOVERNED_PROGRAMME", "track": "B"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("run", "check"))
    parser.add_argument("--epoch", type=int)
    parser.add_argument("--no-replay", action="store_true")
    args = parser.parse_args()
    result = run_epoch(args.epoch) if args.action == "run" else check(replay=not args.no_replay)
    print(json.dumps({key: value for key, value in result.items() if key not in ("epoch_verdicts", "summaries")}, indent=2))
