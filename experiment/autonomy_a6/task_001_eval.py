from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np
from datetime import datetime


def load_function(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    node = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "get_weekly_variation"
    )
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"np": np, "datetime": datetime}
    exec(compile(module, str(path), "exec"), ns, ns)
    return ns["get_weekly_variation"]


def reference(data: np.ndarray, weather_year: int):
    jan_1_us = datetime.weekday(datetime.fromisoformat(f"{weather_year}-01-01"))
    jan_1_ca = datetime.weekday(datetime.fromisoformat(f"{weather_year}-01-01"))

    daily_avg = np.array([np.mean(data[24 * d:24 * (d + 1)]) for d in range(364)])
    weekly_avg = np.array([np.mean(data[7 * 24 * w:7 * 24 * (w + 1)]) for w in range(52)])
    day_of_week = [np.mean(daily_avg[d:52 * 7:7] / weekly_avg) for d in range(7)]
    hour_of_day = [np.mean(data[h:24 * 7 * 52:24] / daily_avg) for h in range(24)]
    time_of_week = [day_of_week[h // 24] * hour_of_day[h % 24] for h in range(24 * 7)]
    time_of_week_zeroed = time_of_week[-24 * jan_1_us:] + time_of_week[0:-24 * jan_1_us]
    tow_mults = time_of_week_zeroed[24 * jan_1_ca:] + time_of_week_zeroed[0:24 * jan_1_ca]
    tow_mults = tow_mults * 52 + tow_mults[0:24]
    tow_mults /= np.mean(tow_mults)
    return np.asarray(time_of_week_zeroed, dtype=float)


def main() -> int:
    root = Path(sys.argv[1]).resolve()
    target = root / "canoe_commercial" / "weather_mapping.py"
    fn = load_function(target)
    data = np.arange(1, 364 * 24 + 1, dtype=float)
    cfg = SimpleNamespace(weather_year=2024)

    try:
        actual = np.asarray(fn(data, cfg), dtype=float)
        expected = reference(data, 2024)
        shape_ok = actual.shape == (168,)
        finite_ok = bool(np.isfinite(actual).all())
        max_abs_error = (
            float(np.max(np.abs(actual - expected)))
            if shape_ok else None
        )
        objective_ok = bool(
            shape_ok
            and finite_ok
            and np.allclose(actual, expected, rtol=1e-12, atol=1e-12)
        )
        result = {
            "schema": "mira-genesis-a6-task001-evaluator-v1",
            "shape_ok": shape_ok,
            "finite_ok": finite_ok,
            "max_abs_error": max_abs_error,
            "objective_ok": objective_ok,
            "external_model_calls": 0,
        }
    except Exception as exc:
        result = {
            "schema": "mira-genesis-a6-task001-evaluator-v1",
            "objective_ok": False,
            "exception": repr(exc),
            "external_model_calls": 0,
        }

    print(json.dumps(result, sort_keys=True))
    return 0 if result["objective_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
