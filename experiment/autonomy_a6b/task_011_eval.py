from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

BASE_REST_SHA = "659f0b8736a7fd5dfae8717c0ed115bb4064f25c9711afcb29f659ed64d0c24c"
OLD = "const month1Data = COMPREHENSIVE_ROADMAP_CHECKLIST[1];"
NEW = "const month1Data = COMPREHENSIVE_ROADMAP_CHECKLIST[0];"
PLACEHOLDER = "const month1Data = COMPREHENSIVE_ROADMAP_CHECKLIST[<INDEX>];"


def normalize(text: str) -> str:
    if NEW in text:
        return text.replace(NEW, PLACEHOLDER, 1)
    if OLD in text:
        return text.replace(OLD, PLACEHOLDER, 1)
    return text


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_011_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    view = (root / "components/erlangga/ErlanggaRoadmapView.tsx").read_text(encoding="utf-8")
    data = (root / "components/erlangga/roadmapChecklistData.ts").read_text(encoding="utf-8")

    index_ok = view.count(NEW) == 1 and OLD not in view
    unrelated_ok = hashlib.sha256(normalize(view).encode()).hexdigest() == BASE_REST_SHA

    array_month1_first = bool(re.search(
        r"COMPREHENSIVE_ROADMAP_CHECKLIST[^=]*=\s*\[\s*(?:/\*[\s\S]*?\*/\s*|//[^\n]*\n\s*)*\{\s*month:\s*1\b",
        data,
    ))

    result = {
        "schema": "mira-genesis-a6b-task011-evaluator-v1",
        "objective_ok": index_ok and unrelated_ok and array_month1_first,
        "month1_index_zero": index_ok,
        "unrelated_view_source_preserved": unrelated_ok,
        "checklist_first_entry_is_month1": array_month1_first,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
