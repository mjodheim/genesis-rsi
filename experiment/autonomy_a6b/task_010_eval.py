from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_010_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    source = root / "textutil.py"
    spec = importlib.util.spec_from_file_location("a6b_task010", source)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    cases = [
        ("hello world", 5, "hello..."),
        ("abcdef", 1, "a..."),
        ("abcdef", 6, "abcdef"),
        ("hi", 10, "hi"),
    ]
    results = []
    ok_all = True
    for text, max_len, expected in cases:
        actual = mod.truncate(text, max_len)
        ok = actual == expected
        results.append({"text": text, "max_len": max_len, "actual": actual, "expected": expected, "ok": ok})
        ok_all = ok_all and ok
    print(json.dumps({
        "schema": "mira-genesis-a6b-task010-evaluator-v1",
        "objective_ok": ok_all,
        "cases": results,
        "external_model_calls": 0,
    }, sort_keys=True))
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
