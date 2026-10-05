"""Single-assignment public-fixture DEVELOPMENT; not a fresh scientific assay."""
import argparse
import itertools
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v32 import storage
from experiment.rsi_v50 import native

WORDS = ((), *(values for length in range(1, 5) for values in itertools.product(range(1, 5), repeat=length)))


def inputs():
    paths = [*sorted((ROOT / "experiment/rsi_v50").glob("*.py")),
        ROOT / "experiment/rsi_v50/PROTOCOL.md", ROOT / "tests/test_rsi_v50.py",
        ROOT / "docs/IP_REVIEWS/V50_FREE_CODEC_MODEL_REVIEW.md",
        ROOT / "docs/V50_FREE_CODEC_CONTINUATION_ARGUMENT.md",
        ROOT / "experiment/rsi_v25/commitments.py", ROOT / "experiment/rsi_v29/native_worker.py",
        ROOT / "experiment/rsi_v32/storage.py", ROOT / "experiment/rsi_v35/native.py",
        ROOT / "experiment/rsi_v49/native.py"]
    return {p.relative_to(ROOT).as_posix(): digest_bytes(p.read_bytes()) for p in paths}


def manifest():
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    value = {"schema": "mira-genesis-v50-public-codec-fixtures-v1", "scope": "PUBLIC_FIXTURE_DEVELOPMENT_ONLY",
        "git_head": head, "inputs": inputs(), "runtime": native.runtime(), "texts": list(native.TEXTS),
        "words": [list(value) for value in WORDS], "reserved_calls": 2 * len(WORDS),
        "native_worker_isolated": True, "output_transport_cap_bytes": 2 * 1024 * 1024,
        "canonical_gzip_os_byte": 255, "scientific_external_model_calls": 0,
        "l9_general_open_ended_passed": False, "l10_independent_passed": False, "new_policy_generation": False}
    for path, sha in value["inputs"].items():
        original = subprocess.check_output(["git", "show", head + ":" + path], cwd=ROOT)
        if digest_bytes(original) != sha:
            raise ValueError("Commit every fixture apparatus input before collection")
    return value


def verify_manifest(value):
    expected = manifest()
    expected["git_head"] = value["git_head"]
    if expected != value:
        raise ValueError("Changed fixture scope, apparatus, governance or runtime")
    subprocess.run(["git", "merge-base", "--is-ancestor", value["git_head"], "HEAD"], cwd=ROOT, check=True)
    for path, sha in value["inputs"].items():
        original = subprocess.check_output(["git", "show", value["git_head"] + ":" + path], cwd=ROOT)
        if digest_bytes(original) != sha:
            raise ValueError("Original apparatus commitment mismatch")


def collect(root, workers=4):
    root = Path(root)
    if root.exists():
        raise FileExistsError("Existing or pending fixture attempt is consumed; no rerun")
    value = manifest()
    root.mkdir(parents=True, exist_ok=False)
    storage.publish_json(root / "MANIFEST.json", value)
    storage.publish_json(root / "RESERVATION.json", {"manifest_sha256": digest(value), "reserved_calls": 2 * len(WORDS)})

    def case(item):
        position, ops = item
        directory = root / f"word-{position:04}"
        binding = {"position": position, "word": list(ops), "source_sha256": native.source_sha(ops), "reserved_calls": 2}
        storage.publish_json(directory / "STARTED.json", binding)
        executions, failure, requested = [], None, 0
        try:
            for _ in range(2):
                requested += 1
                executions.append(native.execute(ops))
            for rows in executions:
                native.validate_outputs(ops, rows)
            if executions[0] != executions[1]:
                raise ValueError("Exact native repetition differs")
        except (RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
            failure = {"type": type(error).__name__, "message": str(error)}
        identity = list(native.decode(native.unpack(executions[0][0]["value"]))[0]) if failure is None else None
        result = {**binding, "executed_requests": requested, "charged_calls": 2,
            "executions": executions, "failure": failure, "validated": failure is None,
            "inverse_decoded_word": identity,
            "primitive_visits": sum(row["value"]["primitive_visits"] for rows in executions for row in rows if row.get("ok") is True),
            "encoder_interface_bytes": sum(row["value"]["encoder_interface_bytes"] for rows in executions for row in rows if row.get("ok") is True),
            "quarantined_visit_upper_bound": 8 * len(ops) if failure else 0}
        storage.publish_json(directory / "RESULT.json", result)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(case, enumerate(WORDS)))
    report = summary(rows)
    storage.publish_json(root / "REPORT.json", report)
    storage.publish_json(root / "COMPLETION.json", {"manifest_sha256": digest(value), "report_sha256": digest(report),
        "case_sha256": [digest(row) for row in rows]})
    return report


def summary(rows):
    return {"scope": "PUBLIC_NATIVE_CODEC_FIXTURE_DEVELOPMENT", "programs": len(rows),
        "validated_programs": sum(row["validated"] for row in rows), "development_validated": all(row["validated"] for row in rows),
        "charged_calls": sum(row["charged_calls"] for row in rows),
        "executed_requests": sum(row["executed_requests"] for row in rows),
        "primitive_visits": sum(row["primitive_visits"] for row in rows),
        "encoder_interface_bytes": sum(row["encoder_interface_bytes"] for row in rows),
        "quarantined_visit_upper_bound": sum(row["quarantined_visit_upper_bound"] for row in rows),
        "exact_semantic_identities": [row["inverse_decoded_word"] for row in rows if row["validated"]],
        "semantic_identity": "Unhashed codec words recovered from actual output; injectivity conditional on stated model",
        "fresh_population": False, "l9_general_open_ended_passed": False,
        "l10_independent_passed": False, "new_policy_generation": False}


def check(root):
    root = Path(root)
    value = storage.read_json(root / "MANIFEST.json")
    verify_manifest(value)
    if storage.read_json(root / "RESERVATION.json") != {"manifest_sha256": digest(value), "reserved_calls": 2 * len(WORDS)}:
        raise ValueError("Altered fixture reservation")
    rows = []
    for position, ops in enumerate(WORDS):
        directory = root / f"word-{position:04}"
        binding = {"position": position, "word": list(ops), "source_sha256": native.source_sha(ops), "reserved_calls": 2}
        row = storage.read_json(directory / "RESULT.json")
        if storage.read_json(directory / "STARTED.json") != binding or any(row[k] != v for k, v in binding.items()):
            raise ValueError("Altered word/source reservation")
        if row["charged_calls"] != 2 or row["executed_requests"] not in (1, 2):
            raise ValueError("Altered charged requests")
        valid = row["failure"] is None
        if valid:
            if len(row["executions"]) != 2 or row["executed_requests"] != 2:
                raise ValueError("Omitted native execution or confirmation")
            expected = native.execute(ops, isolated=False)
            if row["executions"] != [expected, expected]:
                raise ValueError("Altered retained native output")
            native.validate_outputs(ops, expected)
        if row["validated"] != valid or row["inverse_decoded_word"] != (list(ops) if valid else None):
            raise ValueError("Relabelled failed fixture or altered semantic identity")
        visits = sum(o["value"]["primitive_visits"] for run in row["executions"] for o in run if o.get("ok") is True)
        size = sum(o["value"]["encoder_interface_bytes"] for run in row["executions"] for o in run if o.get("ok") is True)
        if row["primitive_visits"] != visits or row["encoder_interface_bytes"] != size or row["quarantined_visit_upper_bound"] != (8 * len(ops) if not valid else 0):
            raise ValueError("Altered work or quarantine accounting")
        rows.append(row)
    report = summary(rows)
    expected = {"manifest_sha256": digest(value), "report_sha256": digest(report), "case_sha256": [digest(row) for row in rows]}
    if storage.read_json(root / "REPORT.json") != report or storage.read_json(root / "COMPLETION.json") != expected:
        raise ValueError("Altered fixture report or completion")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("collect", "check"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    value = collect(args.output_dir, args.workers) if args.action == "collect" else check(args.output_dir)
    print(json.dumps({k: v for k, v in value.items() if k != "exact_semantic_identities"}, sort_keys=True))


if __name__ == "__main__":
    main()
