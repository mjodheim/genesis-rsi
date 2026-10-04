"""Supplemental V35 ledger audit; preserves the frozen apparatus and acceptance rule."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import campaign, engine

TRANSITIVE = ("experiment/rsi_v23/policy_guard.py", "experiment/rsi_v23/sandbox_policy.py",
              "experiment/rsi_v23/policy_worker.py")


def audit_transitive(value):
    observed = {}
    for path in TRANSITIVE:
        committed = subprocess.check_output(["git", "show", value["git_head"] + ":" + path], cwd=ROOT)
        if (ROOT / path).read_bytes() != committed:
            raise ValueError("Changed transitive guard/sandbox from the original apparatus commit: " + path)
        observed[path] = digest_bytes(committed)
    return observed


def audit_header(root):
    root = Path(root)
    value = storage.read_json(root / "MANIFEST.json")
    campaign.verify_manifest(value)
    reservation = {"manifest_sha256": digest(value), "status": "RESERVED_SINGLE_ATTEMPT",
                   "maximum_charged_evaluations": value["tasks_per_arm"] * 3 * 14}
    if storage.read_json(root / "RESERVATION.json") != reservation:
        raise ValueError("Altered campaign single-attempt reservation or maximum cost")
    if value["mode"] == "fresh":
        if storage.read_json(campaign.FREEZE) != value:
            raise ValueError("Fresh campaign differs from original prospective freeze")
        freeze_commit = subprocess.check_output(
            ["git", "log", "-1", "--format=%H", "--", "experiment/rsi_v35/FRESH_FREEZE.json"],
            cwd=ROOT, text=True).strip()
        frozen = subprocess.check_output(["git", "show", freeze_commit + ":experiment/rsi_v35/FRESH_FREEZE.json"], cwd=ROOT)
        if frozen != storage.read_regular(campaign.FREEZE):
            raise ValueError("Changed committed prospective freeze")
        subprocess.run(["git", "merge-base", "--is-ancestor", value["git_head"], freeze_commit], cwd=ROOT, check=True)
        subprocess.run(["git", "merge-base", "--is-ancestor", freeze_commit, "HEAD"], cwd=ROOT, check=True)
    return value


def audit_recovery(root, value):
    if value["mode"] != "fresh":
        return
    root = Path(root)
    tasks = campaign.population("fresh")["81173-relational-sql"]
    history, previous_head, _ = campaign.prior(root / "81173-relational-sql/archive", tasks,
                                              "archive", digest(value), 6, True)
    subset = [t for t in tasks if t["epoch"] == 6]
    directory = root / "81173-relational-sql/archive/epoch-006"
    archive = Archive(directory / "journal.jsonl", campaign.binding(subset, "archive", digest(value), previous_head, history, True))
    rows, events = campaign.journal_rows(archive, subset), archive.read()
    expected_stop = {"completed_tasks": 16, "head_sha256": events[32]["sha256"],
                     "prefix_sha256": digest(rows[:16]),
                     "history_sha256": digest(engine.history_from(rows[:16], history))}
    if storage.read_json(directory / "STOP_BOUNDARY.json") != expected_stop:
        raise ValueError("Interrupted prefix receipt differs from the actual ledger head")
    expected_recovery = {"boundary_sha256": digest(expected_stop), "prefix_reexecuted": False,
                         "restored_history_sha256": expected_stop["history_sha256"], "completed_tasks_at_resume": 16}
    if storage.read_json(directory / "RECOVERY.json") != expected_recovery:
        raise ValueError("Recovery receipt differs from the exact interrupted history")


def check(root):
    value = audit_header(root)
    transitive = audit_transitive(value)
    report = campaign.check(root)
    audit_recovery(root, value)
    if any(t["evaluations"] > value["tasks_per_arm"] * 14 or t["tasks"] != value["tasks_per_arm"]
           for t in report["totals"].values()):
        raise ValueError("Omitted arm tasks or global charged cap exceeded")
    return {"schema": "mira-genesis-v35-supplemental-ledger-audit-v1", "status": "VERIFIED",
            "manifest_sha256": digest(value), "report_sha256": digest(report),
            "transitive_commit_files": transitive,
            "frozen_acceptance_rule_unchanged": True, "independent_replication": False,
            "scoped_sustained_assay_passed": report["scoped_sustained_assay_passed"],
            "l9_general_open_ended_passed": report["l9_general_open_ended_passed"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.output_dir), sort_keys=True))
