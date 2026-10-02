"""Fixed complete public pilot, distinct from subsequent prospective epochs."""
import gzip
import json

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v33 import storage
from experiment.rsi_v42 import bank, engine

PATH = ROOT / "experiment/rsi_v42/DEVELOPMENT.json.gz"
INPUT_NAMES = ("bank.py", "programs.py", "engine.py", "development.py", "PROTOCOL.md")
EPOCHS = 4


def run():
    storage.publish_json(PATH.with_name("DEVELOPMENT_RESERVATION.json"), {
        "scope": "PUBLIC_V42_LAST_CHANCE_FRONTIER_PILOT_NOT_FRESH", "seeds": bank.DEV_SEEDS, "epochs": EPOCHS, "arms": engine.ARMS})
    record = {"scope": "PUBLIC_V42_LAST_CHANCE_FRONTIER_PILOT_NOT_FRESH", "isolated": False,
              "implementation_sha256": {name: digest_bytes((PATH.parent / name).read_bytes()) for name in INPUT_NAMES},
              "streams": {}}
    for seed in bank.DEV_SEEDS:
        record["streams"][str(seed)] = {}
        for arm in engine.ARMS:
            prefix, epochs = [], []
            for epoch in range(EPOCHS):
                tasks, rows = bank.stream(seed, epoch), []
                for position, task in enumerate(tasks):
                    rows.append(engine.episode(task, position, [*prefix, *rows], arm, isolated=False))
                epochs.append({"epoch": epoch, "tasks_sha256": digest(tasks), "episodes": rows, "summary": engine.summary(rows, prefix)})
                prefix.extend(rows)
            record["streams"][str(seed)][arm] = epochs
            print(seed, arm, {"solved": sum(x["summary"]["solved"] for x in epochs),
                             "cost": sum(x["summary"]["evaluations"] for x in epochs),
                             "new_behaviors": [x["summary"]["new_solving_behaviors"] for x in epochs]}, flush=True)
    storage.publish_once(PATH, gzip.compress(canonical(record) + b"\n", mtime=0))


def verify(*, replay=True):
    record = json.loads(gzip.decompress(PATH.read_bytes()))
    if (set(record) != {"scope", "isolated", "implementation_sha256", "streams"}
            or record["scope"] != "PUBLIC_V42_LAST_CHANCE_FRONTIER_PILOT_NOT_FRESH" or record["isolated"] is not False
            or set(record["implementation_sha256"]) != set(INPUT_NAMES)
            or set(record["streams"]) != {str(seed) for seed in bank.DEV_SEEDS}):
        raise ValueError("Public pilot omitted scope, input or population")
    for name, sha in record["implementation_sha256"].items():
        if digest_bytes((PATH.parent / name).read_bytes()) != sha:
            raise ValueError("Pilot implementation changed after observation")
    for seed, arms in record["streams"].items():
        if set(arms) != set(engine.ARMS):
            raise ValueError("Omitted public control")
        for arm, epochs in arms.items():
            if len(epochs) != EPOCHS:
                raise ValueError("Omitted public epoch")
            prefix = []
            for epoch, stream in enumerate(epochs):
                tasks, rows = bank.stream(int(seed), epoch), stream["episodes"]
                if (stream["epoch"] != epoch or stream["tasks_sha256"] != digest(tasks)
                        or digest(stream["summary"]) != digest(engine.summary(rows, prefix))):
                    raise ValueError("Altered public task or archive summary")
                if replay:
                    engine.verify_stream(tasks, arm, prefix, rows, isolated=False)
                prefix.extend(rows)
    return {"scope": record["scope"], "tasks_per_arm": 120, "arms": len(engine.ARMS),
            "development_bytes_sha256": digest_bytes(PATH.read_bytes())}


if __name__ == "__main__":
    run()
