from __future__ import annotations

import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()
path = root / "internal/runtime/docker.go"
text = path.read_text(encoding="utf-8", errors="replace")

start = text.find("func (r *dockerRuntime) WaitForHealth")
if start < 0:
    payload = {
        "schema": "mira-genesis-a6-task009-evaluator-v1",
        "objective_ok": False,
        "error": "WaitForHealth not found",
        "external_model_calls": 0,
    }
    print(json.dumps(payload))
    raise SystemExit(1)

next_func = text.find("\nfunc ", start + 5)
body = text[start:] if next_func < 0 else text[start:next_func]

match = re.search(r"for\s+i\s*:=\s*0\s*;\s*i\s*(<=|<|>=|>)\s*retries\s*;\s*i\+\+\s*\{", body)
operator = None if match is None else match.group(1)

def cond(i: int, retries: int) -> bool:
    if operator == "<":
        return i < retries
    if operator == "<=":
        return i <= retries
    if operator == ">":
        return i > retries
    if operator == ">=":
        return i >= retries
    return False

attempts = 0
i = 0
while attempts < 20 and cond(i, 3):
    attempts += 1
    i += 1

default_logic_ok = bool(re.search(r"if\s+retries\s*<=\s*0\s*\{\s*retries\s*=\s*3", body, re.S))
message_ok = 'health check failed after %d retries' in body

payload = {
    "schema": "mira-genesis-a6-task009-evaluator-v1",
    "operator": operator,
    "attempts_for_retries_3": attempts,
    "expected_attempts": 3,
    "default_logic_ok": default_logic_ok,
    "message_ok": message_ok,
    "objective_ok": operator == "<" and attempts == 3 and default_logic_ok and message_ok,
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
