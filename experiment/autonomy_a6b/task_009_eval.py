from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

EXPECTED_OTHER = {
    "average": "84dd7002469fd89847b51eee0e71b5c7dd513db0f63c4cd712f1dfedb239da28",
    "is_palindrome": "3280994ee5ef8e6c3d566d3b9fbd114e455b89dc08897e40271bb0220a1429e7",
    "chunk": "1a9c6d4627d9c2424736626723724aee03983a4e322fc1e58e94ec4f44b249b8",
}


def digest(node: ast.AST) -> str:
    return hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_009_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    source = root / "string_utils.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    others = {
        n.name: digest(n)
        for n in tree.body
        if isinstance(n, ast.FunctionDef) and n.name != "truncate"
    }
    unrelated_ok = all(others.get(k) == v for k, v in EXPECTED_OTHER.items())

    spec = importlib.util.spec_from_file_location("a6b_task009", source)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)

    cases = [
        ("hello world", 5, "hello..."),
        ("abcdef", 1, "a..."),
        ("abcdef", 6, "abcdef"),
        ("hi", 10, "hi"),
        ("", 0, ""),
    ]
    results = []
    semantics_ok = True
    for text, max_len, expected in cases:
        actual = mod.truncate(text, max_len)
        ok = actual == expected
        results.append({"text": text, "max_len": max_len, "actual": actual, "expected": expected, "ok": ok})
        semantics_ok = semantics_ok and ok

    objective_ok = semantics_ok and unrelated_ok
    print(json.dumps({
        "schema": "mira-genesis-a6b-task009-evaluator-v1",
        "objective_ok": objective_ok,
        "semantics_ok": semantics_ok,
        "unrelated_functions_preserved": unrelated_ok,
        "cases": results,
        "external_model_calls": 0,
    }, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
