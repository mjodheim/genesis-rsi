"""Engineering replay of the selected, fully consumed V47 development evidence."""
import gzip
import json
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v33 import storage
from experiment.rsi_v47 import development as inherited
from experiment.rsi_v48 import bank, engine

HERE = Path(__file__).parent
PATH = HERE / "DEVELOPMENT.json.gz"
RESERVATION = HERE / "DEVELOPMENT_RESERVATION.json"


def sources():
    return sorted(path for path in inherited.DIRECTORY.glob("inverse4_successors-*/*")
                  if path.name in ("RAW.json.gz", "RESERVATION.json", "RESULT.json"))


def build():
    identity = {"schema": "mira-genesis-v48-engineering-development-v1",
                "scope": "CONSUMED_V47_ENGINEERING_REPLAY_NOT_FRESH",
                "selected_variant": "inverse4_successors",
                "selection_reason": "Only V47 variant with positive discovery and archive growth in every seed epoch; complete matched controls improve all five seeds",
                "source_inputs": {path.relative_to(ROOT).as_posix(): digest_bytes(path.read_bytes()) for path in sources()},
                "l9_open_ended_passed": False, "l10_independent_passed": False}
    storage.publish_json(RESERVATION, identity)
    streams = []
    for path in sources():
        if path.name != "RAW.json.gz":
            continue
        original = json.loads(gzip.decompress(path.read_bytes()))
        seed, arm = original["seed"], original["arm"]
        prefix, epochs = [], []
        for epoch in original["epochs"]:
            tasks = bank.stream(seed, epoch["epoch"])
            rows = []
            for position, (task, old) in enumerate(zip(tasks, epoch["episodes"])):
                row = engine.episode(task, position, [*prefix, *rows], arm, isolated=False, replay=old)
                for key in ("task_sha256", "charged_evaluations", "best_quality_milli", "solved", "new_solving_behaviors", "inference_output_calls"):
                    if row[key] != old[key]:
                        raise ValueError("Engineering replay changes executed discovery: " + key)
                if digest([r["evaluation"] for r in row["programs"]]) != digest([r["evaluation"] for r in old["programs"]]):
                    raise ValueError("Engineering replay changes measured candidates")
                rows.append(row)
            epochs.append({"epoch": epoch["epoch"], "episodes": rows, "summary": engine.summary(rows, prefix)})
            prefix.extend(rows)
        stream = {"seed": seed, "arm": arm, "epochs": epochs}
        streams.append(stream)
        print("engineering replay", seed, arm, len(prefix), flush=True)
    value = {**identity, "streams": streams}
    storage.publish_once(PATH, gzip.compress(canonical(value) + b"\n", mtime=0))
    return value


def verify(*, replay=True):
    value = json.loads(gzip.decompress(PATH.read_bytes()))
    reservation = storage.read_json(RESERVATION)
    if {key: value.get(key) for key in reservation} != reservation:
        raise ValueError("Changed engineering replay reservation")
    expected_sources = {path.relative_to(ROOT).as_posix(): digest_bytes(path.read_bytes()) for path in sources()}
    if reservation["source_inputs"] != expected_sources or len(value["streams"]) != len(bank.DEV_SEEDS) * len(engine.ARMS):
        raise ValueError("Changed or omitted consumed development sources")
    if {(r["seed"], r["arm"]) for r in value["streams"]} != {(s, a) for s in bank.DEV_SEEDS for a in engine.ARMS}:
        raise ValueError("Changed engineering replay population")
    for stream in value["streams"]:
        prefix = []
        if len(stream["epochs"]) != bank.INITIAL_EPOCHS:
            raise ValueError("Incomplete engineering replay")
        for index, epoch in enumerate(stream["epochs"]):
            tasks = bank.stream(stream["seed"], index)
            if epoch["epoch"] != index or len(tasks) != len(epoch["episodes"]):
                raise ValueError("Changed engineering replay epoch")
            if replay:
                engine.verify_stream(tasks, stream["arm"], prefix, epoch["episodes"], isolated=False)
            if digest(engine.summary(epoch["episodes"], prefix)) != digest(epoch["summary"]):
                raise ValueError("Changed engineering replay summary")
            prefix.extend(epoch["episodes"])
    return True


if __name__ == "__main__":
    build()
