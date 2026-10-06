from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import sys


def find_compare(path: Path, function_name: str, mode: str) -> ast.Compare:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    fn = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "PlantEnv")
    method = next(n for n in fn.body if isinstance(n, ast.FunctionDef) and n.name == function_name)

    if mode == "terminated_assignment":
        for node in ast.walk(method):
            if isinstance(node, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == "terminated" for t in node.targets):
                    value = node.value
                    if isinstance(value, ast.Call) and value.args:
                        value = value.args[0]
                    if isinstance(value, ast.Compare):
                        return value
    elif mode == "return":
        for node in ast.walk(method):
            if isinstance(node, ast.Return) and isinstance(node.value, ast.Compare):
                return node.value
    raise RuntimeError(f"compare not found: {function_name}/{mode}")


def evaluate(expr: ast.Compare, time_value: int, max_steps: int) -> bool:
    expression = ast.Expression(body=expr)
    ast.fix_missing_locations(expression)
    return bool(eval(
        compile(expression, "<genesis-a6-task003>", "eval"),
        {"__builtins__": {}},
        {
            "state": SimpleNamespace(time=time_value),
            "params": SimpleNamespace(max_steps_in_episode=max_steps),
        },
    ))


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    path = root / "plant_env.py"
    try:
        step_expr = find_compare(path, "step_env", "terminated_assignment")
        terminal_expr = find_compare(path, "is_terminal", "return")
        cases = []
        for max_steps in (1, 2, 5, 10):
            for t in range(0, max_steps + 2):
                step = evaluate(step_expr, t, max_steps)
                terminal = evaluate(terminal_expr, t, max_steps)
                cases.append({
                    "time": t,
                    "max_steps": max_steps,
                    "step_env": step,
                    "is_terminal": terminal,
                    "ok": step == terminal,
                })
        objective_ok = all(c["ok"] for c in cases)
        result = {
            "schema": "mira-genesis-a6-task003-evaluator-v1",
            "objective_ok": objective_ok,
            "case_count": len(cases),
            "mismatches": [c for c in cases if not c["ok"]],
            "external_model_calls": 0,
        }
    except Exception as exc:
        result = {
            "schema": "mira-genesis-a6-task003-evaluator-v1",
            "objective_ok": False,
            "exception": repr(exc),
            "external_model_calls": 0,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
