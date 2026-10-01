"""Reconstruct every consumed development variant before freezing fresh work."""
import gzip
import json

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v31 import bank
from experiment.rsi_v32 import development, engine


def verify(*, replay=True):
    record = json.loads(gzip.decompress(development.PATH.read_bytes()))
    if (record["scope"] != "ALL_240_CONSUMED_V31_TASKS_NOT_FRESH" or record["isolated"] is not False
            or record["population_sha256"] != digest([bank.stream(seed) for seed in development.SEEDS])):
        raise ValueError("Development substituted consumed population or scope")
    for name, sha in record["implementation_sha256"].items():
        if digest_bytes((development.PATH.parent / name).read_bytes()) != sha:
            raise ValueError("Development implementation changed after observation")
    for label, variant in record["variants"].items():
        arm, tolerance = label.split(":")
        if set(variant["streams"]) != {str(seed) for seed in development.SEEDS}:
            raise ValueError("Omitted consumed development stream")
        for seed, stream in variant["streams"].items():
            tasks, rows = bank.stream(int(seed)), stream["episodes"]
            if len(rows) != len(tasks) or digest(stream["summary"]) != digest(engine.summary(rows)):
                raise ValueError("Development summary omitted or altered outcomes")
            if replay:
                engine.verify_stream(tasks, arm, int(tolerance), rows, isolated=False)
        expected = {key: sum(stream["summary"][key] for stream in variant["streams"].values())
                    for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solutions")}
        if variant["totals"] != expected:
            raise ValueError("Altered development selection totals")
    return {"scope": record["scope"], "selected_tolerance_milli": development.selection(),
            "variants": len(record["variants"]), "tasks_per_variant": 240,
            "development_bytes_sha256": digest_bytes(development.PATH.read_bytes())}
