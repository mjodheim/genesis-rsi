"""Freeze the development / held-out split of the repair bench.

    python scripts/build_repair_bench_split.py

Reads the list of active bugs from the validator image and writes
experiment/bench/REPAIR_BENCH_SPLIT_V1.json. Refuses to overwrite an existing split: the split is
decided once.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import DEFECTS4J_REVISION, Defects4JSandbox  # noqa: E402
from genesis.repair_bench import build_split  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SPLIT = ROOT / "experiment/bench/REPAIR_BENCH_SPLIT_V1.json"
_LIST = (
    "cd /defects4j/framework/projects && for p in */; do p=${p%/}; [ -f $p/active-bugs.csv ] || continue; "
    "tail -n +2 $p/active-bugs.csv | cut -d, -f1 | sed \"s/^/$p /\"; done"
)


def main() -> int:
    if SPLIT.exists():
        raise SystemExit(f"{SPLIT.relative_to(ROOT)} already exists; the split is frozen")
    with tempfile.TemporaryDirectory(prefix="genesis-bench-split-") as directory:
        listed = Defects4JSandbox(Path(directory)).execute(["sh", "-c", _LIST], timeout_seconds=120)
    if not listed.ok:
        raise SystemExit(listed.output[-2000:])
    active = [(project, int(bug)) for project, bug in (line.split() for line in listed.output.splitlines() if line.strip())]
    body = {key: value for key, value in build_split(active).items() if key != "split_digest"}
    body = {**body, "defects4j_revision": DEFECTS4J_REVISION, "active_cases": len(active)}
    split = {**body, "split_digest": digest_of(body)}
    SPLIT.parent.mkdir(parents=True, exist_ok=True)
    SPLIT.write_text(json.dumps(split, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(split['held_out'])} held out, {len(split['development'])} development, digest {split['split_digest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
