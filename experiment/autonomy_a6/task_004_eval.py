from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

DUP_RE = re.compile(r"if\s+slots\[(?P<expr>[^\]]+)\]\.ID\s*>\s*0")
ASSIGN_RE = re.compile(r"slots\[(?P<expr>[^\]]+)\]\s*=\s*i")


def eval_index(expr: str, instrument_id: int) -> int:
    expr = expr.replace("i.ID", str(instrument_id)).strip()
    node = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.Constant, ast.Add, ast.Sub, ast.BinOp, ast.UnaryOp, ast.USub)
    if any(not isinstance(n, allowed) for n in ast.walk(node)):
        raise ValueError(f"unsupported index expression: {expr}")
    return int(eval(compile(node, "<a6-go-index>", "eval"), {"__builtins__": {}}, {}))


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    text = (root / "internal/protracker/modproject.go").read_text(encoding="utf-8")
    dup = DUP_RE.search(text)
    assignment = ASSIGN_RE.search(text)
    if not dup or not assignment:
        result = {
            "schema": "mira-genesis-a6-task004-evaluator-v1",
            "objective_ok": False,
            "reason": "required duplicate-check/assignment expressions not found",
            "external_model_calls": 0,
        }
    else:
        cases = []
        for instrument_id in (1, 31):
            dup_index = eval_index(dup.group("expr"), instrument_id)
            assignment_index = eval_index(assignment.group("expr"), instrument_id)
            expected = instrument_id - 1
            cases.append({
                "instrument_id": instrument_id,
                "duplicate_check_index": dup_index,
                "assignment_index": assignment_index,
                "expected_zero_based_index": expected,
                "duplicate_in_bounds": 0 <= dup_index < 31,
                "assignment_in_bounds": 0 <= assignment_index < 31,
                "ok": dup_index == expected and assignment_index == expected,
            })
        result = {
            "schema": "mira-genesis-a6-task004-evaluator-v1",
            "objective_ok": all(c["ok"] for c in cases),
            "duplicate_expr": dup.group("expr"),
            "assignment_expr": assignment.group("expr"),
            "cases": cases,
            "external_model_calls": 0,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
