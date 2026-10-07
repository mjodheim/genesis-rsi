"""Deterministically select the ER1-J1 Commons Lang bug from a frozen Defects4J active-bug list."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

G10_CHAIN_RESULT_DIGEST = "ccbc75ac2de8bbf821dc6912b32d2d08fbbf5f284d51775bcedbfd5a2f8d80f2"
DOMAIN = "GENESIS-ER1-J1|"


def _active_ids(path: Path) -> list[int]:
    text = path.read_text(encoding="utf-8")
    ids: set[int] = set()
    for row in csv.reader(text.splitlines()):
        for cell in row:
            value = cell.strip()
            if value.isdigit():
                ids.add(int(value))
    if not ids:
        raise SystemExit(f"no numeric active bug ids found in {path}")
    return sorted(ids)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--active-bugs", type=Path, required=True)
    parser.add_argument("--dataset-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.active_bugs.read_bytes()
    eligible = _active_ids(args.active_bugs)
    selector_digest = hashlib.sha256((DOMAIN + G10_CHAIN_RESULT_DIGEST).encode()).hexdigest()
    index = int(selector_digest, 16) % len(eligible)
    payload = {
        "schema": "genesis-er1-j1-selection-v1",
        "project": "Lang",
        "dataset_revision": args.dataset_revision,
        "active_bug_list_sha256": hashlib.sha256(raw).hexdigest(),
        "g10_chain_result_digest": G10_CHAIN_RESULT_DIGEST,
        "selector_domain": DOMAIN,
        "selector_sha256": selector_digest,
        "eligible_count": len(eligible),
        "eligible_ids": eligible,
        "selected_index": index,
        "selected_bug_id": eligible[index],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
