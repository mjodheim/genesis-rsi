from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve()
path = root / "taskiq/cli/worker/run.py"
tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

interrupt = None
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "interrupt_handler":
        interrupt = node
        break

operator = None
increment_found = False
counter_init_zero = False

# Verify the enclosing start_listen initializes the counter at zero.
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "start_listen":
        for stmt in node.body:
            if isinstance(stmt, ast.Assign):
                if any(isinstance(t, ast.Name) and t.id == "hardkill_counter" for t in stmt.targets):
                    counter_init_zero = isinstance(stmt.value, ast.Constant) and stmt.value.value == 0
        break

if interrupt is not None:
    for node in ast.walk(interrupt):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left = node.left
            right = node.comparators[0]
            if (
                isinstance(left, ast.Name)
                and left.id == "hardkill_counter"
                and isinstance(right, ast.Attribute)
                and right.attr == "hardkill_count"
                and isinstance(right.value, ast.Name)
                and right.value.id == "args"
            ):
                operator = type(node.ops[0]).__name__
        if isinstance(node, ast.AugAssign):
            if (
                isinstance(node.target, ast.Name)
                and node.target.id == "hardkill_counter"
                and isinstance(node.op, ast.Add)
                and isinstance(node.value, ast.Constant)
                and node.value.value == 1
            ):
                increment_found = True

def triggers(op: str | None, before: int, limit: int) -> bool:
    if op == "Gt":
        return before > limit
    if op == "GtE":
        return before >= limit
    if op == "Eq":
        return before == limit
    if op == "Lt":
        return before < limit
    if op == "LtE":
        return before <= limit
    return False

counter = 0
trigger_signal = None
for signal_index in range(1, 8):
    if triggers(operator, counter, 3):
        trigger_signal = signal_index
        break
    counter += 1

payload = {
    "schema": "mira-genesis-a6-task008-evaluator-v1",
    "operator": operator,
    "counter_init_zero": counter_init_zero,
    "increment_found": increment_found,
    "trigger_signal_for_hardkill_count_3": trigger_signal,
    "expected_trigger_signal": 4,
    "objective_ok": (
        operator == "GtE"
        and counter_init_zero
        and increment_found
        and trigger_signal == 4
    ),
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
