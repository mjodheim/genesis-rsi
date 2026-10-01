"""Lossless single-assignment development on all 456 already consumed tasks."""
import gzip
import json

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v31 import bank as v31
from experiment.rsi_v32 import bank as v32, storage
from experiment.rsi_v33 import engine

PATH = ROOT / "experiment/rsi_v33/DEVELOPMENT.json.gz"
SEEDS = (*v31.DEV_SEEDS, *v31.FRESH_SEEDS, *v32.FRESH_SEEDS)
VARIANTS = tuple(("adaptive", margin) for margin in engine.MARGINS) + tuple((arm, 0) for arm in engine.ARMS[1:])
INPUT_NAMES = ("engine.py", "development.py", "DEVELOPMENT_PROTOCOL.md")


def tasks_for(seed):
    return v31.stream(seed) if seed in v31.DEV_SEEDS + v31.FRESH_SEEDS else v32.stream(seed)


def run():
    storage.publish_json(PATH.with_name("DEVELOPMENT_RESERVATION.json"),
                         {"scope": "ALL_456_CONSUMED_V31_V32_TASKS_NOT_FRESH", "variants": VARIANTS})
    record = {"scope": "ALL_456_CONSUMED_V31_V32_TASKS_NOT_FRESH", "isolated": False,
              "population_sha256": digest([tasks_for(seed) for seed in SEEDS]),
              "implementation_sha256": {name: digest_bytes((PATH.parent / name).read_bytes()) for name in INPUT_NAMES},
              "variants": {}}
    for arm, margin in VARIANTS:
        streams = {}
        for seed in SEEDS:
            rows = []
            for position, task in enumerate(tasks_for(seed)):
                rows.append(engine.episode(task, position, engine.history_from(rows), arm, margin, isolated=False))
            streams[str(seed)] = {"episodes": rows, "summary": engine.summary(rows)}
        totals = {key: sum(stream["summary"][key] for stream in streams.values())
                  for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solutions", "probe_roots", "identity_roots")}
        record["variants"][f"{arm}:{margin}"] = {"streams": streams, "totals": totals}
        print(arm, margin, totals, flush=True)
    storage.publish_once(PATH, gzip.compress(canonical(record) + b"\n", mtime=0))
    print("selected", selection(), flush=True)


def selection():
    record = json.loads(gzip.decompress(PATH.read_bytes()))
    def key(margin):
        totals = record["variants"][f"adaptive:{margin}"]["totals"]
        return totals["solved"], totals["quality_milli"], -totals["evaluations"], -margin
    return max(engine.MARGINS, key=key)


def verify(*, replay=True):
    record = json.loads(gzip.decompress(PATH.read_bytes()))
    if (record["scope"] != "ALL_456_CONSUMED_V31_V32_TASKS_NOT_FRESH" or record["isolated"] is not False
            or record["population_sha256"] != digest([tasks_for(seed) for seed in SEEDS])
            or set(record["variants"]) != {f"{arm}:{margin}" for arm, margin in VARIANTS}):
        raise ValueError("Development scope, population or complete variants changed")
    for name, sha in record["implementation_sha256"].items():
        if digest_bytes((PATH.parent / name).read_bytes()) != sha:
            raise ValueError("Development implementation changed after observation")
    for label, variant in record["variants"].items():
        arm, margin = label.split(":")
        if set(variant["streams"]) != {str(seed) for seed in SEEDS}:
            raise ValueError("Omitted consumed development stream")
        for seed, stream in variant["streams"].items():
            tasks, rows = tasks_for(int(seed)), stream["episodes"]
            if len(rows) != len(tasks) or digest(stream["summary"]) != digest(engine.summary(rows)):
                raise ValueError("Development summary omitted or altered outcomes")
            if replay:
                engine.verify_stream(tasks, arm, int(margin), rows, isolated=False)
        totals = {key: sum(stream["summary"][key] for stream in variant["streams"].values())
                  for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solutions", "probe_roots", "identity_roots")}
        if variant["totals"] != totals:
            raise ValueError("Altered development selection totals")
    return {"scope": record["scope"], "selected_margin_milli": selection(), "variants": len(VARIANTS),
            "tasks_per_variant": 456, "development_bytes_sha256": digest_bytes(PATH.read_bytes())}


if __name__ == "__main__":
    run()
