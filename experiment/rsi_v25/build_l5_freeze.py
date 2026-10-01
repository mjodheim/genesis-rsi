#!/usr/bin/env python3
"""Commit the V25 development apparatus without authorizing a fresh holdout.

This builder is deliberately fail-closed. It hashes only committed evidence and
apparatus bytes and never runs a scientific arm or reads/authors V25 holdout outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
V25 = ROOT / "experiment" / "rsi_v25"
V24_RESULT_ROOT = ROOT / "results" / "rsi-v24"
V24_MANIFEST = V25 / "V24_PRESERVED_EVIDENCE_MANIFEST.json"
V24_TASKS = (
    "brewstead-brew-lifecycle-thresholds", "brewstead-effect-rounding",
    "brewtrack-brewmath-precision", "brewtrack-recipemath-units-water",
)
V24_ARMS = ("g1meta", "g2", "g3")

APPARATUS = (
    V25 / "V25_L5_PREREGISTRATION.md",
    V25 / "V25_TRANSFER_DIAGNOSIS_AND_PROSPECTIVE_PLAN.md",
    V25 / "controls.py",
    V25 / "exploration_grammar.py",
    V25 / "meta_search.py",
    V25 / "build_l5_freeze.py",
    V24_MANIFEST,
)
FORBIDDEN_PRE_FREEZE = (
    ROOT / "results" / "rsi-v25",
    V25 / "V25_L5_ADJUDICATION.json",
    V25 / "V25_HOLDOUT_RESULT.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def preserved_v24_files() -> list[Path]:
    """Verify all thirteen exact archived bytes and their negative adjudication."""
    if not V24_RESULT_ROOT.is_dir():
        raise SystemExit(
            "V24 final result directory is not committed; materialize or bind the "
            "twelve final task results and adjudication before V25 freeze"
        )
    manifest = json.loads(V24_MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("schema") != "mira-genesis-rsi-v24-l5-preserved-evidence-v1"
            or manifest.get("l5_positive") is not False):
        raise SystemExit("V24 evidence manifest must preserve the observed negative")
    names = {f"{arm}-{task}.json" for arm in V24_ARMS for task in V24_TASKS}
    names.add("V24_L5_FINAL_ADJUDICATION.json")
    if set(manifest.get("files", {})) != names:
        raise SystemExit("V24 evidence incomplete: exactly twelve tasks and adjudication required")
    directory = ROOT / manifest["evidence_directory"]
    if not directory.resolve().is_relative_to(V24_RESULT_ROOT.resolve()):
        raise SystemExit("V24 evidence directory escapes its preserved result root")
    files = sorted(directory / name for name in names)
    for path in files:
        if not path.is_file() or path.is_symlink() or sha256(path) != manifest["files"][path.name]:
            raise SystemExit(f"V24 preserved evidence missing or changed: {path.name}")

    final = json.loads((directory / "V24_L5_FINAL_ADJUDICATION.json").read_text(encoding="utf-8"))
    if (final.get("schema") != "mira-genesis-rsi-v24-l5-final-adjudication-v1"
            or final.get("l5_positive") is not False):
        raise SystemExit("V24 final adjudication must remain negative")
    aggregate_keys = {
        "g1meta": "g1_meta_successor_global_utility",
        "g2": "g2_global_utility", "g3": "g3_global_utility",
    }
    for arm in V24_ARMS:
        rows = []
        for task in V24_TASKS:
            row = json.loads((directory / f"{arm}-{task}.json").read_text(encoding="utf-8"))
            if (row.get("schema") != "mira-genesis-rsi-v23-l5-holdout-task-result-v1"
                    or row.get("task_id") != task):
                raise SystemExit("V24 task identity or result schema changed")
            rows.append(row)
        aggregate = [sum(row["best_quality_milli"] == 1000 for row in rows),
                     sum(row["best_quality_milli"] for row in rows),
                     -sum(row["represented_requests"] for row in rows),
                     -sum(row["rounds"] for row in rows)]
        if final.get(aggregate_keys[arm]) != aggregate:
            raise SystemExit("V24 final utility does not match its task results")
    return files


def require_committed_bytes(paths: list[Path], commit: str) -> None:
    """A HEAD label must not conceal untracked or modified working-tree evidence."""
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        try:
            committed = subprocess.check_output(
                ["git", "show", f"{commit}:{relative}"], cwd=ROOT,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError as error:
            raise SystemExit(f"V25 input is not committed: {relative}") from error
        if path.is_symlink() or path.read_bytes() != committed:
            raise SystemExit(f"V25 input differs from committed bytes: {relative}")


def build(apparatus_commit: str) -> dict[str, Any]:
    if git_head() != apparatus_commit:
        raise SystemExit("apparatus commit must equal current HEAD")
    contaminated = [str(p.relative_to(ROOT)) for p in FORBIDDEN_PRE_FREEZE if p.exists()]
    if contaminated:
        raise SystemExit("V25 pre-freeze contamination: " + ", ".join(contaminated))
    missing = [str(p.relative_to(ROOT)) for p in APPARATUS if not p.is_file()]
    if missing:
        raise SystemExit("V25 apparatus incomplete: " + ", ".join(missing))

    v24 = preserved_v24_files()
    files = sorted(set(APPARATUS).union(v24), key=lambda p: str(p.relative_to(ROOT)))
    require_committed_bytes(files, apparatus_commit)
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in files}
    payload = {
        "schema": "mira-genesis-rsi-v25-apparatus-commitment-v1",
        "status": "DEVELOPMENT_APPARATUS_COMMITTED_HOLDOUT_NOT_AUTHORIZED",
        "apparatus_commit": apparatus_commit,
        "files": hashes,
        "v24_evidence_file_count": len(v24),
        "holdout_consumed": False,
        "authorizes_fresh_holdout": False,
        "remaining_requirements": [
            "bind executable descendant search and all controls to the preserved predecessor",
            "freeze and pass L4 retention for the selected executable successor",
            "prospectively bind a genuinely new task population and evaluator",
        ],
    }
    payload["freeze_payload_sha256"] = canonical_sha256(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apparatus-commit", required=True)
    parser.add_argument("--output", default=str(V25 / "V25_APPARATUS_COMMITMENT.json"))
    args = parser.parse_args()
    payload = build(args.apparatus_commit)
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
