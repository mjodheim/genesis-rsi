"""Matched real-evaluator benchmark for OE1 online search versus V53."""
from collections import defaultdict

from experiment.l9_oe1 import online
from experiment.l9_oe1.improver import ImproverGenome
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v53.benchmark import _record_abstract, _record_exact


def _discoveries(rows):
    seen = set()
    per_window = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                per_window[row["window"]] += 1
    return seen, dict(per_window)


def run(seed, directory, *, tasks, improver=None, isolated=False, limit=None):
    improver = improver or ImproverGenome(replay_budget=online.SEARCH_BUDGET)
    tasks = list(tasks)
    if limit is not None:
        tasks = tasks[:limit]
    directory.mkdir(parents=True, exist_ok=True)

    oe_exact = ExperimentalMemory(directory / "oe1-exact.db")
    oe_abstract = AbstractionMemory(directory / "oe1-abstract.db")
    v53_exact = ExperimentalMemory(directory / "v53-exact.db")
    v53_abstract = AbstractionMemory(directory / "v53-abstract.db")
    v51_memory = ExperimentalMemory(directory / "v51.db")

    oe_rows, v53_rows, v51_rows, cold_rows = [], [], [], []
    try:
        for position, task in enumerate(tasks):
            cold = v32.episode(task, position, {}, "cold", 25, isolated=isolated)

            x51 = v51.episode(task, position, v51_memory, isolated=isolated)
            x51.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            _record_exact(
                v51_memory,
                x51,
                cold,
                task,
                x51["routing"]["retrieved_strategy_ids"],
            )
            v51.remember(v51_memory, x51)

            x53 = v53.episode(
                task,
                position,
                v53_exact,
                v53_abstract,
                isolated=isolated,
            )
            x53.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            _record_exact(
                v53_exact,
                x53,
                cold,
                task,
                x53["routing"]["exact_strategy_ids"],
            )
            _record_abstract(v53_abstract, x53, x51, task)
            v53.remember(v53_exact, v53_abstract, x53)

            xoe = online.episode(
                task,
                position,
                oe_exact,
                oe_abstract,
                improver=improver,
                isolated=isolated,
            )
            xoe.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            _record_exact(
                oe_exact,
                xoe,
                cold,
                task,
                xoe["routing"]["exact_strategy_ids"],
            )
            _record_abstract(oe_abstract, xoe, x51, task)
            online.remember(oe_exact, oe_abstract, xoe)

            oe_rows.append(xoe)
            v53_rows.append(x53)
            v51_rows.append(x51)
            cold_rows.append(cold)

        oe_seen, oe_windows = _discoveries(oe_rows)
        v53_seen, v53_windows = _discoveries(v53_rows)
        return {
            "seed": seed,
            "tasks": len(tasks),
            "improver_sha256": improver.sha256(),
            "oe1": online.summary(oe_rows),
            "v53": v53.summary(v53_rows),
            "v51": v51.summary(v51_rows),
            "cold": v32.summary(cold_rows),
            "oe1_first_discoveries_by_window": {
                str(w): oe_windows.get(w, 0)
                for w in sorted({task["window"] for task in tasks})
            },
            "v53_first_discoveries_by_window": {
                str(w): v53_windows.get(w, 0)
                for w in sorted({task["window"] for task in tasks})
            },
            "distinct_solved_semantics": {
                "oe1": len(oe_seen),
                "v53": len(v53_seen),
            },
            "deltas": {
                "solved_vs_v53": online.summary(oe_rows)["solved"] - v53.summary(v53_rows)["solved"],
                "evaluations_vs_v53": online.summary(oe_rows)["evaluations"] - v53.summary(v53_rows)["evaluations"],
                "distinct_semantics_vs_v53": len(oe_seen) - len(v53_seen),
            },
        }
    finally:
        oe_exact.close()
        oe_abstract.close()
        v53_exact.close()
        v53_abstract.close()
        v51_memory.close()


def aggregate(results):
    return {
        "tasks": sum(r["tasks"] for r in results),
        "oe1_solved": sum(r["oe1"]["solved"] for r in results),
        "v53_solved": sum(r["v53"]["solved"] for r in results),
        "oe1_evaluations": sum(r["oe1"]["evaluations"] for r in results),
        "v53_evaluations": sum(r["v53"]["evaluations"] for r in results),
        "oe1_distinct_semantics": sum(
            r["distinct_solved_semantics"]["oe1"] for r in results
        ),
        "v53_distinct_semantics": sum(
            r["distinct_solved_semantics"]["v53"] for r in results
        ),
    }
