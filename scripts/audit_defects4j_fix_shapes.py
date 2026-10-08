"""How large are Defects4J's human fixes, and does the failing trace point at them?

Aggregate counts over every active bug, read from the benchmark's own patch and trigger-test
files in the validator image. The files are copied to a temporary directory that is deleted when
the script ends, and only aggregates are written. The counts still describe the whole benchmark,
so they must not be used to tune a repair mechanism that is later evaluated on a held-out part.

    python scripts/audit_defects4j_fix_shapes.py --out shapes.json
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SCHEMA = "genesis-defects4j-fix-shape-audit-v1"

# Defects4J stores each fix as a REVERSE patch (fixed -> buggy), so a '-' line is code the fix adds
# and the '+' side of a hunk header is the buggy line range.
_COPY = '''cd /defects4j/framework/projects && for p in */; do p=${p%/}; [ -f $p/active-bugs.csv ] || continue;
mkdir -p /work/$p && cp $p/active-bugs.csv /work/$p/ && cp -r $p/patches $p/trigger_tests /work/$p/; done'''


def shape_counts(base: Path) -> dict:
    """Aggregate counts over every exported patch under ``base``."""
    code = lambda lines: [l for l in lines if l.strip() and not l.strip().startswith(("//", "*", "/*"))]
    rows = []
    for project in sorted(p for p in base.iterdir() if (p / "active-bugs.csv").is_file()):
        for record in csv.DictReader(open(project / "active-bugs.csv")):
            bug = record["bug.id"]
            patch = project / "patches" / f"{bug}.src.patch"
            if not patch.is_file():
                continue
            files, current = [], None
            for line in patch.read_text(errors="replace").splitlines():
                if line.startswith("+++ "):
                    current = {"path": line[4:].split("\t")[0].strip(), "hunks": []}
                    files.append(current)
                elif line.startswith("@@") and current is not None:
                    m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
                    current["hunks"].append({"start": int(m.group(1)), "length": int(m.group(2) or 1), "add": [], "del": []})
                elif current and current["hunks"]:
                    if line.startswith("-") and not line.startswith("---"):
                        current["hunks"][-1]["add"].append(line[1:])
                    elif line.startswith("+") and not line.startswith("+++"):
                        current["hunks"][-1]["del"].append(line[1:])
            files = [f for f in files if f["path"].endswith(".java")]
            hunks = [h for f in files for h in f["hunks"] if code(h["add"]) or code(h["del"])]
            trace_path = project / "trigger_tests" / bug
            trace = trace_path.read_text(errors="replace") if trace_path.is_file() else ""
            frames = re.findall(r"\tat [\w.$]+\.[\w$<>]+\(([\w$]+\.java):(\d+)\)", trace)
            distance = None
            for f in files:
                name = f["path"].rsplit("/", 1)[-1]
                for frame_file, frame_line in frames:
                    if frame_file != name:
                        continue
                    for h in f["hunks"]:
                        low, high, at = h["start"], h["start"] + h["length"], int(frame_line)
                        d = 0 if low <= at <= high else min(abs(at - low), abs(at - high))
                        distance = d if distance is None else min(distance, d)
            rows.append({
                "files": len(files), "hunks": len(hunks),
                "added": sum(len(code(h["add"])) for h in hunks), "removed": sum(len(code(h["del"])) for h in hunks),
                "trace_distance": distance,
            })
    count = lambda test: sum(1 for r in rows if test(r))
    one_hunk = lambda r: r["files"] == 1 and r["hunks"] == 1
    return {
        "active_bugs": len(rows),
        "single_file": count(lambda r: r["files"] == 1),
        "single_file_single_hunk": count(one_hunk),
        "single_hunk_at_most_2_changed_lines": count(lambda r: one_hunk(r) and r["added"] + r["removed"] <= 2),
        "single_hunk_at_most_3_changed_lines": count(lambda r: one_hunk(r) and r["added"] + r["removed"] <= 3),
        "single_hunk_at_most_5_changed_lines": count(lambda r: one_hunk(r) and r["added"] + r["removed"] <= 5),
        "one_line_replaced_by_one_line": count(lambda r: r["hunks"] == 1 and r["added"] == 1 and r["removed"] == 1),
        "fix_adds_at_least_one_line": count(lambda r: r["added"] > 0),
        "fix_only_adds_lines": count(lambda r: r["added"] > 0 and r["removed"] == 0),
        "failing_trace_reaches_fixed_file": count(lambda r: r["trace_distance"] is not None),
        "failing_trace_inside_fix_hunk": count(lambda r: r["trace_distance"] == 0),
        "failing_trace_within_5_lines_of_fix": count(lambda r: r["trace_distance"] is not None and r["trace_distance"] <= 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="genesis-d4j-shapes-") as directory:
        sandbox = Defects4JSandbox(Path(directory))
        run = sandbox.execute(["sh", "-c", _COPY], timeout_seconds=300)
        if not run.ok:
            raise SystemExit(run.output[-2000:])
        counts = shape_counts(Path(directory))
    body = {"schema": SCHEMA, "image": sandbox.image, "per_bug_fix_content_exported": False,
            "counts": counts}
    arguments.out.write_text(json.dumps({**body, "audit_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(body["counts"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
