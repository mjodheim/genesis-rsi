"""Matched V55 diagnostic benchmark against frozen V53."""
from collections import defaultdict

from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import benchmark as b53
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v55 import engine


def _discoveries(rows):
    seen = set()
    windows = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                windows[row["window"]] += 1
    return seen, dict(windows)


def run(seed, directory, *, tasks, isolated=False,
        scope="CONSUMED_V53_PROSPECTIVE_V55_DEVELOPMENT"):
    tasks = list(tasks)
    directory.mkdir(parents=True, exist_ok=True)

    e55 = ExperimentalMemory(directory / "v55-exact.db")
    a55 = AbstractionMemory(directory / "v55-abstract.db")
    e53 = ExperimentalMemory(directory / "v53-exact.db")
    a53 = AbstractionMemory(directory / "v53-abstract.db")
    m51 = ExperimentalMemory(directory / "v51.db")

    rows55, rows53, rows51, cold_rows = [], [], [], []
    diagnostic_tasks = diagnostic_gains = diagnostic_regressions = 0

    try:
        for position, task in enumerate(tasks):
            cold = v32.episode(
                task, position, {}, "cold", 25, isolated=isolated
            )

            x51 = v51.episode(
                task, position, m51, isolated=isolated
            )
            x51.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            b53._record_exact(
                m51, x51, cold, task,
                x51["routing"]["retrieved_strategy_ids"],
            )
            v51.remember(m51, x51)

            x53 = v53.episode(
                task, position, e53, a53, isolated=isolated
            )
            x53.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            b53._record_exact(
                e53, x53, cold, task,
                x53["routing"]["exact_strategy_ids"],
            )
            b53._record_abstract(a53, x53, x51, task)
            v53.remember(e53, a53, x53)

            x55 = engine.episode(
                task, position, e55, a55, isolated=isolated
            )
            x55.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            b53._record_exact(
                e55, x55, cold, task,
                x55["routing"]["exact_strategy_ids"],
            )
            b53._record_abstract(a55, x55, x51, task)
            engine.remember(e55, a55, x55)

            if x55["routing"]["diagnostic_active"]:
                diagnostic_tasks += 1
                diagnostic_gains += int(
                    x55["solved"] and not x53["solved"]
                )
                diagnostic_regressions += int(
                    x53["solved"] and not x55["solved"]
                )

            rows55.append(x55)
            rows53.append(x53)
            rows51.append(x51)
            cold_rows.append(cold)

        seen55, windows55 = _discoveries(rows55)
        seen53, windows53 = _discoveries(rows53)
        result = {
            "schema": "mira-genesis-v55-feedback-diagnostic-development-v1",
            "seed": seed,
            "tasks": len(tasks),
            "scope": scope,
            "configuration": {
                "diagnostic_min_width": engine.DIAGNOSTIC_MIN_WIDTH,
                "max_evaluations_per_task": engine.MAX_EVALUATIONS,
                "diagnostic_sparse_mask_max_bits": 2,
            },
            "v55": engine.summary(rows55),
            "v53": v53.summary(rows53),
            "v51": v51.summary(rows51),
            "cold": v32.summary(cold_rows),
            "diagnostic_contribution": {
                "tasks": diagnostic_tasks,
                "solve_gains_vs_v53": diagnostic_gains,
                "solve_regressions_vs_v53": diagnostic_regressions,
            },
            "distinct_solved_semantics": {
                "v55": len(seen55),
                "v53": len(seen53),
            },
            "v55_first_discoveries_by_window": {
                str(window): windows55.get(window, 0)
                for window in sorted({
                    task["window"] for task in tasks
                })
            },
            "v53_first_discoveries_by_window": {
                str(window): windows53.get(window, 0)
                for window in sorted({
                    task["window"] for task in tasks
                })
            },
            "deltas": {
                "solved_vs_v53": (
                    engine.summary(rows55)["solved"]
                    - v53.summary(rows53)["solved"]
                ),
                "evaluations_vs_v53": (
                    engine.summary(rows55)["evaluations"]
                    - v53.summary(rows53)["evaluations"]
                ),
                "distinct_semantics_vs_v53": (
                    len(seen55) - len(seen53)
                ),
            },
            "l9_general_open_ended_passed": False,
            "l10_independent_passed": False,
        }
        return result
    finally:
        e55.close()
        a55.close()
        e53.close()
        a53.close()
        m51.close()


def aggregate(results):
    return {
        "tasks": sum(row["tasks"] for row in results),
        "v55_solved": sum(row["v55"]["solved"] for row in results),
        "v53_solved": sum(row["v53"]["solved"] for row in results),
        "cold_solved": sum(row["cold"]["solved"] for row in results),
        "v55_evaluations": sum(
            row["v55"]["evaluations"] for row in results
        ),
        "v53_evaluations": sum(
            row["v53"]["evaluations"] for row in results
        ),
        "diagnostic_routes": sum(
            row["v55"]["diagnostic_routes"] for row in results
        ),
        "diagnostic_tasks_solved": sum(
            row["v55"]["diagnostic_tasks_solved"]
            for row in results
        ),
        "diagnostic_solve_gains_vs_v53": sum(
            row["diagnostic_contribution"]["solve_gains_vs_v53"]
            for row in results
        ),
        "diagnostic_solve_regressions_vs_v53": sum(
            row["diagnostic_contribution"]["solve_regressions_vs_v53"]
            for row in results
        ),
        "l9_general_open_ended_passed": False,
    }
