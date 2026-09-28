#!/usr/bin/env python3
"""Build the prospective V24/L5 freeze record.

The builder must run on the complete V24 apparatus commit immediately before
the freeze-only commit. It validates the preserved V23 negative predecessor,
all V23 frozen bytes, and the complete V24 semantic bridge before emitting
V24_FREEZE.json. It never runs a scientific meta-search arm.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
V23 = ROOT / "experiment" / "rsi_v23"
V24 = ROOT / "experiment" / "rsi_v24"
V23_FREEZE_PATH = V23 / "V23_FREEZE.json"
V23_NEGATIVE_PATH = (
    ROOT
    / "results"
    / "rsi-v23"
    / "l5-20260924"
    / "V23_L5_PRE_HOLDOUT_ADJUDICATION.json"
)
V23_RESULTS_DIR = ROOT / "results" / "rsi-v23" / "l5-20260924"

EXPECTED_V23_FREEZE_PAYLOAD_SHA256 = (
    "fcd93040efb8bcf3681f7d88acb817605f700d4182f780eadfa430d9136a4272"
)
EXPECTED_G1_SHA256 = (
    "3354f887a93a08d9f00e9c54ccb097003f727ba77c1e1b4e9997adf676d35434"
)
EXPECTED_G2_SHA256 = (
    "69d0d725601cd32adff27379dbb25f5c7be29946f9e9c6ac4858a0634cbd5fdf"
)

FORBIDDEN_PRE_FREEZE = (
    ROOT / "results" / "rsi-v24",
    V24 / "G3_SELECTED.py",
    V24 / "G1_META_SELECTED.py",
    V24 / "G2_ABLATION_SELECTED.py",
    V24 / "NO_META_SELECTED.py",
    V24 / "V24_META_SEARCH_RESULT.json",
    V24 / "V24_PRE_HOLDOUT_GATE.json",
    V24 / "V24_L5_ADJUDICATION.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_v23_predecessor() -> tuple[dict[str, Any], dict[str, Any]]:
    if not V23_FREEZE_PATH.is_file():
        raise SystemExit("V23 freeze is missing")
    if not V23_NEGATIVE_PATH.is_file():
        raise SystemExit("preserved V23 negative adjudication is missing")

    freeze = json.loads(V23_FREEZE_PATH.read_text(encoding="utf-8"))
    if freeze.get("schema") != "mira-genesis-rsi-v23-l5-freeze-v1":
        raise SystemExit("unexpected V23 freeze schema")
    if freeze.get("status") != "FROZEN_BEFORE_ANY_V23_META_SEARCH":
        raise SystemExit("V23 was not frozen before meta-search")
    if freeze.get("freeze_payload_sha256") != EXPECTED_V23_FREEZE_PAYLOAD_SHA256:
        raise SystemExit("V23 freeze payload identity changed")
    if freeze.get("g1_source_sha256") != EXPECTED_G1_SHA256:
        raise SystemExit("V23 G1 identity changed")
    if freeze.get("g2_source_sha256") != EXPECTED_G2_SHA256:
        raise SystemExit("V23 G2 identity changed")

    for rel, expected in sorted(dict(freeze.get("files", {})).items()):
        path = ROOT / rel
        if not path.is_file():
            raise SystemExit(f"reused V23 frozen file missing: {rel}")
        got = sha256(path)
        if got != expected:
            raise SystemExit(
                f"reused V23 frozen file changed: {rel}: {got} != {expected}"
            )

    negative = json.loads(V23_NEGATIVE_PATH.read_text(encoding="utf-8"))
    if (
        negative.get("schema")
        != "mira-genesis-rsi-v23-l5-pre-holdout-adjudication-v1"
    ):
        raise SystemExit("unexpected V23 negative adjudication schema")
    if (
        negative.get("status")
        != "NEGATIVE_CAUSAL_ATTRIBUTION_BEFORE_FRESH_HOLDOUT"
    ):
        raise SystemExit("V23 predecessor is not the preserved causal negative")
    if negative.get("fresh_holdout_consumed") is not False:
        raise SystemExit("V23 fresh holdout is no longer fresh")
    if negative.get("eligible_for_fresh_holdout") is not False:
        raise SystemExit("V23 negative unexpectedly claims holdout eligibility")
    if negative.get("l5_positive") is not False:
        raise SystemExit("V23 negative unexpectedly claims positive L5")
    if negative.get("g2_meta_process_strictly_beats_g2_ablation") is not False:
        raise SystemExit("V23 causal failure predicate changed")

    return freeze, negative


def required_files() -> list[Path]:
    paths: list[Path] = []
    for path in sorted(V24.rglob("*")):
        if path.is_file() and path.name != "V24_FREEZE.json":
            paths.append(path)
    for path in sorted((ROOT / "tests").glob("test_rsi_v24*.py")):
        if path.is_file():
            paths.append(path)
    paths.append(V23_FREEZE_PATH)
    workflow = ROOT / ".github" / "workflows" / "v24-l5-freeze-build.yml"
    if workflow.is_file():
        paths.append(workflow)
    for path in sorted(V23_RESULTS_DIR.rglob("*")):
        if path.is_file():
            paths.append(path)

    unique = {str(path.relative_to(ROOT)): path for path in paths}
    return [unique[key] for key in sorted(unique)]


def validate_complete_bridge() -> dict[str, Any]:
    bridge = _load(
        "v24_freeze_semantic_bridge",
        V24 / "semantic_quality_bridge.py",
    )
    rows = tuple(bridge.bridged_universe())
    if not rows:
        raise SystemExit("V24 public bridge universe is empty")

    root = tuple(bridge.ROOT_DEVELOPMENT_UTILITY)
    root_rows = [
        row
        for row in rows
        if tuple(row["development_utility"]) == root
        and int(row["mutation_depth"]) == 0
    ]
    if len(root_rows) != 1:
        raise SystemExit("V24 bridge must contain exactly one root G2 row")
    if int(root_rows[0]["quality_milli"]) != int(bridge.NEUTRAL_QUALITY):
        raise SystemExit("V24 root G2 does not map to the neutral quality")

    utility_to_quality: dict[tuple[int, ...], int] = {}
    for row in rows:
        utility = tuple(int(x) for x in row["development_utility"])
        quality = int(row["quality_milli"])
        prior = utility_to_quality.get(utility)
        if prior is not None and prior != quality:
            raise SystemExit("same public utility received two semantic qualities")
        utility_to_quality[utility] = quality

        if utility < root and not 0 <= quality <= int(bridge.PROMISING_MAX):
            raise SystemExit("worse-than-G2 utility escaped 0..710")
        if utility == root and quality != int(bridge.NEUTRAL_QUALITY):
            raise SystemExit("root-equivalent utility escaped neutral quality")
        if utility > root and not int(bridge.STRONG_THRESHOLD) <= quality <= int(
            bridge.MAX_QUALITY
        ):
            raise SystemExit("strict successor utility escaped 780..1000")

    worse = sorted(value for value in utility_to_quality if value < root)
    better = sorted(value for value in utility_to_quality if value > root)
    if any(
        utility_to_quality[a] >= utility_to_quality[b]
        for a, b in zip(worse, worse[1:])
    ):
        raise SystemExit("V24 bridge loses strict order below root G2")
    if any(
        utility_to_quality[a] >= utility_to_quality[b]
        for a, b in zip(better, better[1:])
    ):
        raise SystemExit("V24 bridge loses strict order above root G2")

    map_rows = [
        {
            "development_utility": list(utility),
            "quality_milli": quality,
        }
        for utility, quality in sorted(utility_to_quality.items())
    ]
    candidate_rows = [
        {
            "params_digest": str(row["params_digest"]),
            "source_sha256": str(row["source_sha256"]),
            "mutation_depth": int(row["mutation_depth"]),
            "development_utility": [
                int(x) for x in row["development_utility"]
            ],
            "quality_milli": int(row["quality_milli"]),
        }
        for row in sorted(rows, key=lambda item: str(item["params_digest"]))
    ]

    return {
        "root_development_utility": list(root),
        "candidate_count": len(rows),
        "unique_utility_count": len(utility_to_quality),
        "semantic_quality_map": map_rows,
        "semantic_quality_map_sha256": canonical_sha256(map_rows),
        "bridged_candidate_manifest_sha256": canonical_sha256(candidate_rows),
    }


def g2_ablation_sha256() -> str:
    search = _load("v24_freeze_meta_search", V24 / "l5_meta_search.py")
    source = search.g2_ablation_source()
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def build(apparatus_commit: str) -> dict[str, Any]:
    actual = git_head()
    if actual != apparatus_commit:
        raise SystemExit(
            f"apparatus commit mismatch: {actual} != {apparatus_commit}"
        )

    for path in FORBIDDEN_PRE_FREEZE:
        if path.exists():
            raise SystemExit(
                f"pre-freeze V24 result contamination: {path.relative_to(ROOT)}"
            )

    v23_freeze, v23_negative = verify_v23_predecessor()
    files = required_files()
    missing = [
        str(path.relative_to(ROOT))
        for path in files
        if not path.is_file()
    ]
    if missing:
        raise SystemExit(
            "missing required V24 freeze files: " + ", ".join(missing)
        )

    bridge_record = validate_complete_bridge()

    payload: dict[str, Any] = {
        "schema": "mira-genesis-rsi-v24-l5-freeze-v1",
        "status": "FROZEN_BEFORE_ANY_V24_META_SEARCH",
        "apparatus_commit": apparatus_commit,
        "v23_predecessor": {
            "freeze_payload_sha256": v23_freeze["freeze_payload_sha256"],
            "negative_status": v23_negative["status"],
            "negative_adjudication_sha256": sha256(V23_NEGATIVE_PATH),
            "fresh_holdout_consumed": False,
            "eligible_for_fresh_holdout": False,
        },
        "g1_source_sha256": EXPECTED_G1_SHA256,
        "g2_source_sha256": EXPECTED_G2_SHA256,
        "g2_ablation_source_sha256": g2_ablation_sha256(),
        "g2_ablation_definition": (
            "exact G2 with only the strong-result block "
            "'if best >= 780: return []' removed"
        ),
        "meta_budgets": {
            "represented_requests_per_arm": 9,
            "rounds_per_arm": 8,
            "max_parallelism": 2,
            "mutation_depth": 2,
        },
        "bridge": bridge_record,
        "reused_v23_frozen_file_count": len(v23_freeze["files"]),
        "files": {
            str(path.relative_to(ROOT)): sha256(path)
            for path in files
        },
    }
    payload_sha = canonical_sha256(payload)
    return {**payload, "freeze_payload_sha256": payload_sha}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apparatus-commit", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = build(args.apparatus_commit)
    args.out.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
