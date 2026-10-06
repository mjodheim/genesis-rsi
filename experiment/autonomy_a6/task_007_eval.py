from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

WORKSPACE = Path(sys.argv[1]).resolve()
PROBE = Path("/home/anthony/mira-genesis-autonomy/experiment/autonomy_a6/task_007_probe.ts")
TSX = "/home/anthony/experiments/a6v2-c010/node_modules/.bin/tsx"
EXPECTED = [
    "exc-nas-food-02",
    "exc-nas-kayak-03",
    "exc-nas-reef-01",
]
TIMEZONES = ["UTC", "America/Nassau", "Pacific/Honolulu"]

results = []
for tz in TIMEZONES:
    env = os.environ.copy()
    env["TZ"] = tz
    proc = subprocess.run(
        [TSX, str(PROBE), str(WORKSPACE)],
        cwd=WORKSPACE,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        text=True,
    )
    parsed = None
    if proc.stdout.strip():
        try:
            parsed = json.loads(proc.stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass
    found = None if parsed is None else parsed.get("found")
    results.append(
        {
            "tz": tz,
            "exit_code": int(proc.returncode),
            "found": found,
            "expected": EXPECTED,
            "ok": proc.returncode == 0 and found == EXPECTED,
            "stderr": proc.stderr,
        }
    )

payload = {
    "schema": "mira-genesis-a6-task007-evaluator-v1",
    "objective_ok": all(item["ok"] for item in results),
    "results": results,
    "external_model_calls": 0,
}
print(json.dumps(payload, sort_keys=True))
raise SystemExit(0 if payload["objective_ok"] else 1)
