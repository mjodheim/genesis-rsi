"""After a trial is sealed: is each test-passing repair the developer's own fix?

    python scripts/audit_repair_bench_trial.py --name T1 --workspace /srv/genesis/bench

Passing the test suite does not make a patch correct. This reads the FIXED revision of every case
an arm solved and reports whether the accepted file is identical to the developer's, ignoring
whitespace. Identical is a lower bound on correct: a different patch may also be right, and only a
person can say. It must run after the result file exists, and it spends nothing: the cases were
already consumed by the trial.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox  # noqa: E402
from genesis.repair_bench import squashed_sha256  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

BENCH = ROOT / "experiment/bench"
SCHEMA = "genesis-repair-bench-reveal-v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    result = json.loads((BENCH / f"TRIAL_{arguments.name}_RESULT.json").read_text(encoding="utf-8"))
    sandbox = Defects4JSandbox(arguments.workspace)
    rows = []
    for case in result["cases"]:
        solved = {arm: data for arm, data in case.get("arms", {}).items() if data["solved"]}
        if not solved:
            continue
        project, bug = case["case"].rsplit("-", 1)
        fixed = f"{case['case']}-f"
        if not (arguments.workspace / fixed).is_dir() and not sandbox.checkout(project, int(bug), "f", fixed).ok:
            raise SystemExit(f"cannot check out the fixed revision of {case['case']}")
        for arm, data in solved.items():
            reference = arguments.workspace / fixed / data["plausible_path"]
            identical = reference.is_file() and squashed_sha256(
                reference.read_text(encoding="utf-8", errors="replace")) == data["plausible_squashed_sha256"]
            rows.append({"case": case["case"], "arm": arm, "identical_to_developer_fix": identical})
    arms = sorted({row["arm"] for row in rows})
    body = {
        "schema": SCHEMA,
        "name": result["name"],
        "result_digest": result["result_digest"],
        "fixed_revision_consulted": True,
        "rows": rows,
        "summary": {
            arm: {
                "plausible": sum(row["arm"] == arm for row in rows),
                "identical_to_developer_fix": sum(row["arm"] == arm and row["identical_to_developer_fix"] for row in rows),
            }
            for arm in arms
        },
        "identical_is_a_lower_bound_on_correct": True,
    }
    target = BENCH / f"TRIAL_{arguments.name}_REVEAL.json"
    target.write_text(json.dumps({**body, "reveal_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(body["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
