"""Complete retained comparisons on public, already consumed populations only."""
import argparse
import gzip
import json
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes
from experiment.rsi_v33 import storage
from experiment.rsi_v47 import bank, engine

HERE = Path(__file__).parent
SEEDS = (503, 887, 86028121, 86028157, 86028193)
EPOCHS = 8
INPUTS = ("bank.py", "programs.py", "engine.py", "development.py")
DIRECTORY = ROOT / "results/rsi-v47/development-20261004"


def run(variant, seed, arm="adaptive"):
    if variant not in engine.VARIANTS or seed not in SEEDS or arm not in engine.ARMS:
        raise ValueError("Unknown consumed development population or variant")
    identity = {"scope": "OUTCOME_CONDITIONED_CONSUMED_DEVELOPMENT_NOT_FRESH",
                "variant": variant, "seed": seed, "arm": arm, "epochs": EPOCHS,
                "isolated": False, "l9_open_ended_passed": False,
                "l10_independent_passed": False,
                "implementation_sha256": {name: digest_bytes((HERE / name).read_bytes()) for name in INPUTS}}
    where = DIRECTORY / f"{variant}-s{seed}-{arm}"
    storage.publish_json(where / "RESERVATION.json", identity)
    prefix, epochs = [], []
    for epoch in range(EPOCHS):
        tasks, rows = bank.stream(seed, epoch), []
        for position, task in enumerate(tasks):
            row = engine.episode(task, position, [*prefix, *rows], arm,
                                 isolated=False, variant=variant)
            rows.append(row)
        summary = engine.summary(rows, prefix)
        epochs.append({"epoch": epoch, "tasks_sha256": digest(tasks), "episodes": rows, "summary": summary})
        prefix.extend(rows)
        print(variant, seed, arm, epoch, summary["solved"], summary["evaluations"],
              summary["new_solving_behaviors"], flush=True)
    record = {**identity, "epochs": epochs}
    raw = gzip.compress(canonical(record) + b"\n", mtime=0)
    storage.publish_once(where / "RAW.json.gz", raw)
    result = {**identity, "tasks": len(prefix), "solved": sum(row["solved"] for row in prefix),
              "evaluations": sum(row["charged_evaluations"] for row in prefix),
              "new_solving_behaviors": [row["summary"]["new_solving_behaviors"] for row in epochs],
              "positive_growth_every_epoch": all(row["summary"]["new_solving_behaviors"] > 0
                  and row["summary"]["archive_source_size"] > row["summary"]["archive_source_size_before"]
                  and row["summary"]["archive_behavior_size"] > row["summary"]["archive_behavior_size_before"]
                  for row in epochs), "raw_sha256": digest_bytes(raw)}
    storage.publish_json(where / "RESULT.json", result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=engine.VARIANTS)
    parser.add_argument("seed", type=int, choices=SEEDS)
    parser.add_argument("--arm", default="adaptive", choices=engine.ARMS)
    arguments = parser.parse_args()
    run(arguments.variant, arguments.seed, arguments.arm)
