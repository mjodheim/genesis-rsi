#!/usr/bin/env python3
"""Build the prospective V25 pre-holdout freeze.

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

APPARATUS = (
    V25 / "V25_L5_PREREGISTRATION.md",
    V25 / "V25_TRANSFER_DIAGNOSIS_AND_PROSPECTIVE_PLAN.md",
    V25 / "controls.py",
    V25 / "exploration_grammar.py",
    V25 / "meta_search.py",
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
    """Require concrete committed V24 final evidence; never infer it from prose."""
    if not V24_RESULT_ROOT.is_dir():
        raise SystemExit(
            "V24 final result directory is not committed; materialize or bind the "
            "twelve final task results and adjudication before V25 freeze"
        )
    files = sorted(path for path in V24_RESULT_ROOT.rglob("*") if path.is_file())
    if len(files) < 13:
        raise SystemExit(
            "V24 evidence incomplete: expected final adjudication plus at least "
            "twelve task-result files"
        )
    return files


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
    hashes = {str(p.relative_to(ROOT)): sha256(p) for p in files}
    payload = {
        "schema": "mira-genesis-rsi-v25-l5-freeze-v1",
        "status": "FROZEN_BEFORE_ANY_V25_HOLDOUT_ACCESS",
        "apparatus_commit": apparatus_commit,
        "files": hashes,
        "v24_evidence_file_count": len(v24),
        "holdout_consumed": False,
    }
    payload["freeze_payload_sha256"] = canonical_sha256(payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apparatus-commit", required=True)
    parser.add_argument("--output", default=str(V25 / "V25_FREEZE.json"))
    args = parser.parse_args()
    payload = build(args.apparatus_commit)
    Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
