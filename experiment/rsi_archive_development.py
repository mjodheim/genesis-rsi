"""Replay retained public archive development without promoting scientific gates."""
import argparse
import gzip
import importlib
import json

from experiment.rsi_v25.commitments import digest, digest_bytes


def check_record(development, engine, directory, *, replay=True):
    reservation = json.loads((directory / "RESERVATION.json").read_text())
    result = json.loads((directory / "RESULT.json").read_text())
    raw = (directory / "RAW.json.gz").read_bytes()
    record = json.loads(gzip.decompress(raw))
    if any((key != "epochs" and record.get(key) != value) or result.get(key) != value
           for key, value in reservation.items()):
        raise ValueError("Changed development reservation")
    if (reservation["scope"] != "OUTCOME_CONDITIONED_CONSUMED_DEVELOPMENT_NOT_FRESH"
            or reservation["isolated"] is not False
            or reservation["l9_open_ended_passed"] is not False
            or reservation["l10_independent_passed"] is not False
            or reservation["seed"] not in development.SEEDS
            or reservation["variant"] not in engine.VARIANTS
            or reservation["arm"] not in engine.ARMS
            or reservation["epochs"] != development.EPOCHS):
        raise ValueError("Invalid development scope or gate")
    expected_inputs = {name: digest_bytes((development.HERE / name).read_bytes()) for name in development.INPUTS}
    if reservation["implementation_sha256"] != expected_inputs:
        raise ValueError("Changed executed implementation")
    if result["raw_sha256"] != digest_bytes(raw):
        raise ValueError("Changed raw development bytes")
    if len(record["epochs"]) != development.EPOCHS:
        raise ValueError("Incomplete retained epochs")
    prefix, summaries = [], []
    for index, epoch in enumerate(record["epochs"]):
        tasks = development.bank.stream(reservation["seed"], index)
        rows = epoch["episodes"]
        if epoch["epoch"] != index or epoch["tasks_sha256"] != digest(tasks) or len(rows) != len(tasks):
            raise ValueError("Changed development population")
        if any(row["routing"]["development_variant"] != reservation["variant"]
               or not 4 <= row["charged_evaluations"] <= engine.MAX_EVALUATIONS for row in rows):
            raise ValueError("Changed variant or evaluation cap")
        if replay:
            engine.verify_stream(tasks, reservation["arm"], prefix, rows, isolated=False)
        summary = engine.summary(rows, prefix)
        if digest(summary) != digest(epoch["summary"]):
            raise ValueError("Changed development summary")
        summaries.append(summary)
        prefix.extend(rows)
    expected = {**reservation, "tasks": len(prefix), "solved": sum(row["solved"] for row in prefix),
                "evaluations": sum(row["charged_evaluations"] for row in prefix),
                "new_solving_behaviors": [row["new_solving_behaviors"] for row in summaries],
                "positive_growth_every_epoch": all(row["new_solving_behaviors"] > 0
                    and row["archive_source_size"] > row["archive_source_size_before"]
                    and row["archive_behavior_size"] > row["archive_behavior_size_before"] for row in summaries),
                "raw_sha256": digest_bytes(raw)}
    if digest(expected) != digest(result):
        raise ValueError("Changed development result")
    return {"version": engine.__name__, "variant": reservation["variant"], "seed": reservation["seed"],
            "arm": reservation["arm"], "episodes": len(prefix), "replayed": replay}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--versions", nargs="+", type=int, choices=range(43, 48), default=list(range(43, 48)))
    parser.add_argument("--metadata-only", action="store_true")
    arguments = parser.parse_args()
    for version in arguments.versions:
        development = importlib.import_module(f"experiment.rsi_v{version}.development")
        engine = importlib.import_module(f"experiment.rsi_v{version}.engine")
        for directory in sorted(development.DIRECTORY.iterdir()):
            print(json.dumps(check_record(development, engine, directory, replay=not arguments.metadata_only)), flush=True)


if __name__ == "__main__":
    main()
