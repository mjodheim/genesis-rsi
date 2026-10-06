from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

REST_SHA256 = "37085718ae8e88f45ed7394bff77a2dfa0ba307264e2b362e0b8032d4786510e"


def replace_block(text: str, key: str, placeholder: str) -> str:
    start = text.index(key)
    brace = text.index("{", start)
    depth = 0
    end = None
    in_single = in_double = in_template = False
    escaped = False
    for i, ch in enumerate(text[brace:], start=brace):
        if escaped:
            escaped = False
            continue
        if ch == "\\" and (in_single or in_double or in_template):
            escaped = True
            continue
        if not in_double and not in_template and ch == "'":
            in_single = not in_single
            continue
        if not in_single and not in_template and ch == '"':
            in_double = not in_double
            continue
        if not in_single and not in_double and ch == "`":
            in_template = not in_template
            continue
        if in_single or in_double or in_template:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise ValueError(f"unbalanced block: {key}")
    return text[:start] + placeholder + text[end:]


def unrelated_digest(text: str) -> str:
    normalized = replace_block(text, "  init: async function()", "  <INIT_BLOCK>")
    normalized = replace_block(normalized, "  updateRange: async function()", "  <UPDATE_RANGE_BLOCK>")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


HARNESS = r"""
const fs = require('fs');
const source = fs.readFileSync(process.argv[2], 'utf8');
global.app = {};
global.document = { addEventListener: function() {} };
eval(source);

function fields() {
  return {
    range: { value: 'custom' },
    rangestart: { value: '2026-08-16', min: '', max: '' },
    rangeend: { value: '2026-08-16', min: '', max: '' },
    stat: { value: 'calories' },
  };
}
function calendar(d) {
  return [d.getFullYear(), d.getMonth() + 1, d.getDate()];
}
async function testUpdateRange() {
  app.Stats.el = fields();
  let captured = null;
  app.Stats.getDataFromDb = async (from, to) => {
    captured = [calendar(from), calendar(to)];
    return undefined;
  };
  await app.Stats.updateRange();
  return captured;
}
async function testInit() {
  app.Stats.el = fields();
  app.Stats.getComponents = function() { this.el = fields(); };
  app.Stats.bindUIActions = function() {};
  app.Stats.populateDropdownOptions = function() {};
  app.Stats.setChartTypeButtonVisibility = function() {};
  app.Stats.updateChart = function() {};
  app.Stats.renderStatLog = function() {};
  app.Settings = {
    get: function(section, key) {
      if (section !== 'statistics') return undefined;
      if (key === 'last-range-start') return '2026-08-16';
      if (key === 'last-range-end') return '2026-08-16';
      if (key === 'last-range') return undefined;
      if (key === 'last-stat') return undefined;
      if (key === 'chart-type') return 0;
      return undefined;
    }
  };
  let captured = null;
  app.Stats.getDataFromDb = async (from, to) => {
    captured = [calendar(from), calendar(to)];
    return undefined;
  };
  await app.Stats.init();
  return captured;
}
(async () => {
  const result = {
    updateRange: await testUpdateRange(),
    init: await testInit(),
  };
  console.log(JSON.stringify(result));
})().catch(err => { console.error(err); process.exit(2); });
"""


def run_timezone(source: Path, tz: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="a6b-task012-") as td:
        harness = Path(td) / "harness.js"
        harness.write_text(HARNESS, encoding="utf-8")
        env = dict(os.environ)
        env["TZ"] = tz
        proc = subprocess.run(
            ["node", str(harness), str(source)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
            timeout=20,
        )
        parsed = None
        if proc.returncode == 0 and proc.stdout.strip():
            parsed = json.loads(proc.stdout.decode().strip().splitlines()[-1])
        return {
            "timezone": tz,
            "exit_code": proc.returncode,
            "parsed": parsed,
            "stderr": proc.stderr.decode("utf-8", errors="replace"),
        }


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: task_012_eval.py <workspace>")
    root = Path(sys.argv[1]).resolve()
    source = root / "www/activities/statistics/js/statistics.js"
    text = source.read_text(encoding="utf-8")

    unrelated_ok = unrelated_digest(text) == REST_SHA256
    invariants = {
        "custom_range_still_supported": 'app.Stats.el.range.value != "custom"' in text,
        "range_settings_still_saved": 'app.Settings.put("statistics", "last-range-start"' in text,
        "database_path_still_used": "this.getDataFromDb" in text and "app.Stats.dbData" in text,
    }

    runs = [run_timezone(source, "America/New_York"), run_timezone(source, "Asia/Tokyo")]
    expected = [[2026, 8, 16], [2026, 8, 16]]
    behavior_ok = all(
        run["exit_code"] == 0
        and run["parsed"] is not None
        and run["parsed"].get("updateRange") == expected
        and run["parsed"].get("init") == expected
        for run in runs
    )

    result = {
        "schema": "mira-genesis-a6b-task012-evaluator-v2",
        "objective_ok": unrelated_ok and behavior_ok and all(invariants.values()),
        "selected_date_preserved_as_local_calendar_day": behavior_ok,
        "unrelated_source_preserved": unrelated_ok,
        "invariants": invariants,
        "timezone_runs": runs,
        "external_model_calls": 0,
    }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
