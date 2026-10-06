from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

REST_SHA256 = "df914841f0ed3999221e4ee8ae64b96608111727f3e932da1e0d8cd423d5ab6e"
LOOP_RE = re.compile(r"for\s+_\s+in\s+(\d+)\.\.(=)?RETRY_ATTEMPTS\s*\{")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_006_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    path = root / "src/download.rs"
    text = path.read_text(encoding="utf-8")

    constant_ok = len(re.findall(r"const RETRY_ATTEMPTS: u8 = 4;", text)) == 2
    matches = list(LOOP_RE.finditer(text))
    counts = []
    for match in matches:
        start = int(match.group(1))
        inclusive = match.group(2) == "="
        counts.append(4 - start + (1 if inclusive else 0))

    loops_ok = len(matches) == 2 and counts == [4, 4]
    legacy_absent = "for _ in 1..RETRY_ATTEMPTS {" not in text
    rest = LOOP_RE.sub("<RETRY_LOOP>", text)
    unrelated_preserved = hashlib.sha256(rest.encode("utf-8")).hexdigest() == REST_SHA256

    result = {
        "schema": "mira-genesis-a6b-task006-evaluator-v1",
        "objective_ok": constant_ok and loops_ok and legacy_absent and unrelated_preserved,
        "constant_ok": constant_ok,
        "loop_iteration_counts": counts,
        "loops_ok": loops_ok,
        "legacy_loops_absent": legacy_absent,
        "unrelated_source_preserved": unrelated_preserved,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
