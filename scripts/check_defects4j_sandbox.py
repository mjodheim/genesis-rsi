"""Observe the Defects4J container boundary and print the sealed probe as JSON.

    python scripts/check_defects4j_sandbox.py            # isolation probe only
    python scripts/check_defects4j_sandbox.py --smoke    # also check out, compile and test Lang-1

Exit status is 0 only when every isolation check holds (and, with --smoke, when the buggy
version of Lang-1 fails exactly its recorded triggering test).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import IMAGE, Defects4JSandbox  # noqa: E402

LANG_1_TRIGGER = ["org.apache.commons.lang3.math.NumberUtilsTest::TestLang747"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default=IMAGE)
    parser.add_argument("--smoke", action="store_true", help="also reproduce Lang-1 inside the boundary")
    arguments = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="genesis-d4j-check-") as directory:
        sandbox = Defects4JSandbox(Path(directory), image=arguments.image)
        report = {"probe": sandbox.probe()}
        passed = report["probe"]["isolated"]
        if passed and arguments.smoke:
            runs = [
                sandbox.checkout("Lang", 1, "b", "lang-1b"),
                sandbox.compile("lang-1b"),
                sandbox.test("lang-1b", relevant_only=True),
            ]
            failing = sandbox.failing_tests("lang-1b") if all(run.ok for run in runs) else None
            report["smoke"] = {
                "runs": [run.record() for run in runs],
                "failing_tests": failing,
                "reproduced": failing == LANG_1_TRIGGER,
            }
            passed = report["smoke"]["reproduced"]
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
