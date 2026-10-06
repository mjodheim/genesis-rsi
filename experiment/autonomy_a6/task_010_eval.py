from __future__ import annotations

import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1]).resolve()

TARGETS = [
    ("WaitForHealth", root / "internal/runtime/docker.go"),
    ("doHTTPCheck", root / "internal/health/health.go"),
]

results = []
for name, path in TARGETS:
    text = path.read_text(encoding="utf-8", errors="replace")
    if name == "WaitForHealth":
        start = text.find("func (r *dockerRuntime) WaitForHealth")
    else:
        start = text.find("func (c *Checker) doHTTPCheck")
    if start < 0:
        results.append({"name": name, "operator": None, "attempts_for_3": None, "ok": False})
        continue
    next_func = text.find("\nfunc ", start + 5)
    body = text[start:] if next_func < 0 else text[start:next_func]
    match = re.search(r"for\s+i\s*:=\s*0\s*;\s*i\s*(<=|<|>=|>)\s*retries\s*;\s*i\+\+\s*\{", body)
    operator = None if match is None else match.group(1)

    attempts = None
    if operator in {"<", "<=", ">", ">="}:
        def cond(i: int) -> bool:
            return {
                "<": i < 3,
                "<=": i <= 3,
                ">": i > 3,
                ">=": i >= 3,
            }[operator]
        i = 0
        count = 0
        while count < 20 and cond(i):
            count += 1
            i += 1
        attempts = count

    default_logic_ok = bool(
        re.search(r"if\s+retries\s*<=\s*0\s*\{\s*retries\s*=\s*3", body, re.S)
    )
    results.append({
        "name": name,
        "operator": operator,
        "attempts_for_3": attempts,
        "default_logic_ok": default_logic_ok,
        "ok": operator == "<" and attempts == 3 and default_logic_ok,
    })

payload = {
    "schema": "mira-genesis-a6-task010-evaluator-v1",
    "objective_ok": all(item["ok"] for item in results),
    "results": results,
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
