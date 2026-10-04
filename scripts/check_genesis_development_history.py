"""Replay preserved V33/V34 evidence across descendant Git commits without rewriting it."""
import argparse
import gzip
import importlib
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v32 import storage


def check(version, directory):
    directory = Path(directory)
    development = importlib.import_module(f"experiment.rsi_v{version}.development")
    engine = importlib.import_module(f"experiment.rsi_v{version}.engine")
    manifest = storage.read_json(directory / "MANIFEST.json")
    if manifest["python_version"] != platform.python_version():
        raise ValueError("Use the original development Python runtime")
    subprocess.run(["git", "merge-base", "--is-ancestor", manifest["git_head"], "HEAD"], cwd=ROOT, check=True)
    for path, sha in manifest["inputs"].items():
        if digest_bytes((ROOT / path).read_bytes()) != sha:
            raise ValueError("Changed original development apparatus: " + path)
    current = development.manifest()
    current["git_head"] = manifest["git_head"]
    if current != manifest:
        raise ValueError("Changed original runtime, population or manifest")
    completion = storage.read_json(directory / "COMPLETION.json")
    raw = storage.read_regular(directory / "DEVELOPMENT.json.gz")
    record = json.loads(gzip.decompress(raw))
    if (completion["manifest_sha256"] != digest(manifest) or completion["raw_sha256"] != digest_bytes(raw)
            or record["manifest_sha256"] != digest(manifest) or record["status"] != "COMPLETED"):
        raise ValueError("Altered original raw evidence or manifest receipt")
    tasks_by_stream = development.population()
    if set(record["streams"]) != set(tasks_by_stream) or set(completion["heads"]) != set(tasks_by_stream):
        raise ValueError("Omitted original stream")
    for label, tasks in tasks_by_stream.items():
        arms = record["streams"][label]
        if set(arms) != set(engine.ARMS) or set(completion["heads"][label]) != set(engine.ARMS):
            raise ValueError("Omitted original control")
        for arm, stream in arms.items():
            archive = engine.Archive(directory / "journals" / f"{label}-{arm}.jsonl",
                                     engine.binding(tasks, arm, digest(manifest), False))
            events = archive.read(expected_head=completion["heads"][label][arm])
            if (events[-1]["sha256"] != stream["head_sha256"] or archive.episodes() != stream["episodes"]
                    or engine.summary(stream["episodes"]) != stream["summary"]):
                raise ValueError("Altered original journal, head or summary")
            engine.verify_stream(tasks, arm, stream["episodes"], isolated=False)
    report = storage.read_json(directory / "REPORT.json")
    if development.adjudicate(record["streams"]) != report or completion["report_sha256"] != digest(report):
        raise ValueError("Altered original adjudication")
    return {"version": version, "status": "VERIFIED_UNCHANGED", "original_git_head": manifest["git_head"],
            "raw_sha256": digest_bytes(raw), "report_sha256": digest(report)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", type=int, choices=(33, 34))
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(check(arguments.version, arguments.output_dir), sort_keys=True))
