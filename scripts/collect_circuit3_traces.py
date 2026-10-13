#!/usr/bin/env python3
"""CIRCUIT3 training-only search traces; no held-out tasks, providers, or GPU.

The collector records target-conditioned novel signals from the frozen engine.
It is deliberately not a learned guide or a CIRCUIT3 result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.circuit_engine import Engine, solve
from genesis.circuit_tasks import LEARN, tasks


def collect(*, budget: int, families: tuple[str, ...], max_tasks: int | None = None) -> list[dict]:
    if budget < 1:
        raise ValueError("budget must be positive")
    if not families or any(family not in LEARN for family in families):
        raise ValueError("only learning families may be traced")
    if max_tasks is not None and max_tasks < 1:
        raise ValueError("max_tasks must be positive")
    result: list[dict] = []
    chosen = [task for family in families for task in tasks(family)]
    for task in chosen[:max_tasks]:
        trace: list[tuple[int, int, int]] = []
        solution = solve(Engine(), task, budget, trace=lambda table, cost, used: trace.append((table, cost, used)))
        result.append({"task": task.name, "family": task.family, "inputs": task.inputs,
                       "target": task.target, "budget": budget, "solved": solution.solved,
                       "evaluations": solution.evaluations,
                       "novel_signals": [{"table": table, "cost": cost, "evaluation": used}
                                         for table, cost, used in trace]})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget", type=int, default=1000)
    parser.add_argument("--max-tasks", type=int, default=5)
    parser.add_argument("--families", nargs="+", default=["and", "or"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = collect(budget=args.budget, families=tuple(args.families), max_tasks=args.max_tasks)
    content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(content)
    print(json.dumps({"tasks": len(rows), "signals": sum(len(row["novel_signals"]) for row in rows),
                      "sha256": hashlib.sha256(content.encode()).hexdigest(), "output": str(args.output)}))


if __name__ == "__main__":
    main()
