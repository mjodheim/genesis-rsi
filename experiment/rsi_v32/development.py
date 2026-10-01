"""Complete consumed-data sweep; preserve every outcome before choosing tolerance."""
import gzip
import json
import os

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v31 import bank
from experiment.rsi_v32 import engine

PATH = ROOT / "experiment/rsi_v32/DEVELOPMENT.json.gz"
SEEDS = bank.DEV_SEEDS + bank.FRESH_SEEDS


def sweep():
    # Reserve before any behavior, including failures. Never replace the result.
    fd = os.open(PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    result = {"scope": "ALL_240_CONSUMED_V31_TASKS_NOT_FRESH", "isolated": False,
              "implementation_sha256": {p.name: digest_bytes(p.read_bytes()) for p in PATH.parent.glob("*.py")},
              "population_sha256": digest([bank.stream(seed) for seed in SEEDS]), "variants": {}}
    try:
        for arm, tolerance in [("adaptive", t) for t in engine.TOLERANCES] + [
                (a, 0) for a in engine.ARMS if a != "adaptive"]:
            streams = {}
            for seed in SEEDS:
                episodes = []
                for position, task in enumerate(bank.stream(seed)):
                    episodes.append(engine.episode(task, position, engine.history_from(episodes), arm,
                                                   tolerance, isolated=False))
                streams[str(seed)] = {"episodes": episodes, "summary": engine.summary(episodes)}
            totals = {key: sum(stream["summary"][key] for stream in streams.values())
                      for key in ("tasks", "solved", "quality_milli", "evaluations", "new_solutions")}
            result["variants"][f"{arm}:{tolerance}"] = {"streams": streams, "totals": totals}
            print(arm, tolerance, totals, flush=True)
        best = max(engine.TOLERANCES, key=lambda t: (
            result["variants"][f"adaptive:{t}"]["totals"]["solved"],
            result["variants"][f"adaptive:{t}"]["totals"]["quality_milli"],
            -result["variants"][f"adaptive:{t}"]["totals"]["evaluations"], -t))
        result["selected_tolerance_milli"], result["status"] = best, "COMPLETED"
    except BaseException as error:
        result["status"], result["interruption"] = "INTERRUPTED", type(error).__name__
        raise
    finally:
        with os.fdopen(fd, "wb") as stream:
            stream.write(gzip.compress(json.dumps(result, sort_keys=True, separators=(",", ":")).encode(), mtime=0))
            stream.flush()
            os.fsync(stream.fileno())
    return result


def selection():
    record = json.loads(gzip.decompress(PATH.read_bytes()))
    if record["status"] != "COMPLETED" or set(record["variants"]) != {
            *(f"adaptive:{t}" for t in engine.TOLERANCES), *(f"{a}:0" for a in engine.ARMS if a != "adaptive")}:
        raise ValueError("Incomplete development sweep")
    best = max(engine.TOLERANCES, key=lambda t: (
        record["variants"][f"adaptive:{t}"]["totals"]["solved"],
        record["variants"][f"adaptive:{t}"]["totals"]["quality_milli"],
        -record["variants"][f"adaptive:{t}"]["totals"]["evaluations"], -t))
    if best != record["selected_tolerance_milli"]:
        raise ValueError("Changed development selection rule")
    return best


if __name__ == "__main__":
    print("Selected tolerance:", sweep()["selected_tolerance_milli"])
