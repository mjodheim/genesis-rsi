from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

EXPECTED_OTHER_FUNCTIONS = {
    "add": "24500296e48dba3035d338b1c82ebcc216abb9c62047a6c0514390c7c1975e0b",
    "subtract": "23104f58df199939083433e5f45636537cf2aa5c1b875774c2fa5a207bde7ae5",
    "multiply": "437518e3250aeb40c635c0231a147c2ca3b3eb2055e4475a9dee36ddef9caa89",
    "divide": "67de26f11389f880cb6510bce6f9be5573f38b2f59313d299bbba6fcb50d5692",
    "power": "8424c63f0f05868eed72fe89f0b7ddaa26941163c8f91f3ea168fd033b63f7ea",
    "average": "6e73c35036c92442af2bd8b2cc9eb36fe1c379eebd855d6848d1b541f5c5c949",
    "is_even": "91dc8395e7a4f657d7c8b5ed77ec2123cc3058270487a3682793a600b6996970",
    "square_root": "6258fdf92329f87af0839809b78c4eb06156293e29c644b701eb0bf229ecde45",
}


def ast_digest(node: ast.AST) -> str:
    value = ast.dump(node, include_attributes=False)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_004_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    source = root / "src/calculator/calculator.py"
    text = source.read_text(encoding="utf-8")
    tree = ast.parse(text)

    other = {
        node.name: ast_digest(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name != "factorial"
    }
    unrelated_preserved = all(
        other.get(name) == digest
        for name, digest in EXPECTED_OTHER_FUNCTIONS.items()
    )

    spec = importlib.util.spec_from_file_location("a6b_task004_calc", source)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    cases = []
    semantics_ok = True
    for n in range(0, 8):
        actual = module.factorial(n)
        expected = math.factorial(n)
        ok = actual == expected
        cases.append({"n": n, "actual": actual, "expected": expected, "ok": ok})
        semantics_ok = semantics_ok and ok

    objective_ok = semantics_ok and unrelated_preserved
    result = {
        "schema": "mira-genesis-a6b-task004-evaluator-v1",
        "objective_ok": objective_ok,
        "semantics_ok": semantics_ok,
        "unrelated_functions_preserved": unrelated_preserved,
        "cases": cases,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if objective_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
