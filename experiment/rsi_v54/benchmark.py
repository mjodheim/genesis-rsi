"""Matched V54 lineage-credit benchmark against V53 and inherited controls."""
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52 import engine as v52
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v53.benchmark import _discoveries, _record_abstract, _record_exact
from experiment.rsi_v54 import engine
from experiment.rsi_v54.lineage import LineageMemory


def run(seed, directory, *, tasks, isolated=False, limit=None,
        scope="CONSUMED_V53_PROSPECTIVE_V54_DEVELOPMENT"):
    tasks = list(tasks)
    if limit is not None:
        tasks = tasks[:limit]
    directory.mkdir(parents=True, exist_ok=True)

    e54 = ExperimentalMemory(directory / "v54-exact.db")
    a54 = AbstractionMemory(directory / "v54-abstract.db")
    l54 = LineageMemory(directory / "v54-lineage.db")

    e53 = ExperimentalMemory(directory / "v53-exact.db")
    a53 = AbstractionMemory(directory / "v53-abstract.db")
    e52 = ExperimentalMemory(directory / "v52-exact.db")
    a52 = AbstractionMemory(directory / "v52-abstract.db")
    m51 = ExperimentalMemory(directory / "v51.db")

    r54, r53, r52, r51, archive, cold_rows = [], [], [], [], [], []
    lineage_events = 0
    try:
        for position, task in enumerate(tasks):
            cold = v32.episode(task, position, {}, "cold", 25, isolated=isolated)

            x51 = v51.episode(task, position, m51, isolated=isolated)
            x51.update(window=task["window"], width=task["width"], task_family=task["family"])
            _record_exact(m51, x51, cold, task, x51["routing"]["retrieved_strategy_ids"])
            v51.remember(m51, x51)

            x52 = v52.episode(
                task, position, e52, a52,
                abstract_top_k=1,
                abstract_only_without_exact=True,
                allowed_modes=None,
                isolated=isolated,
            )
            x52.update(window=task["window"], width=task["width"], task_family=task["family"])
            _record_exact(e52, x52, cold, task, x52["routing"]["exact_strategy_ids"])
            _record_abstract(a52, x52, x51, task)
            v52.remember(e52, a52, x52)

            x53 = v53.episode(task, position, e53, a53, isolated=isolated)
            x53.update(window=task["window"], width=task["width"], task_family=task["family"])
            _record_exact(e53, x53, cold, task, x53["routing"]["exact_strategy_ids"])
            _record_abstract(a53, x53, x51, task)
            v53.remember(e53, a53, x53)

            x54 = engine.episode(task, position, e54, a54, l54, isolated=isolated)
            x54.update(window=task["window"], width=task["width"], task_family=task["family"])
            _record_exact(e54, x54, cold, task, x54["routing"]["exact_strategy_ids"])
            _record_abstract(a54, x54, x51, task)
            lineage_events += engine.remember(e54, a54, l54, x54)

            x_archive = v32.episode(
                task, position, v32.history_from(archive), "adaptive", 25,
                isolated=isolated,
            )

            r54.append(x54)
            r53.append(x53)
            r52.append(x52)
            r51.append(x51)
            archive.append(x_archive)
            cold_rows.append(cold)

        s54, w54 = _discoveries(r54)
        s53, w53 = _discoveries(r53)
        result = {
            "schema": "mira-genesis-v54-lineage-credit-development-v1",
            "seed": seed,
            "tasks": len(tasks),
            "scope": scope,
            "v54": engine.summary(r54),
            "v53": v53.summary(r53),
            "v52": v52.summary(r52),
            "v51": v51.summary(r51),
            "archive": v32.summary(archive),
            "cold": v32.summary(cold_rows),
            "distinct_solved_semantics": {"v54": len(s54), "v53": len(s53)},
            "v54_first_discoveries_by_window": {
                str(w): w54.get(w, 0) for w in sorted({t["window"] for t in tasks})
            },
            "v53_first_discoveries_by_window": {
                str(w): w53.get(w, 0) for w in sorted({t["window"] for t in tasks})
            },
            "lineage_counts": l54.counts(),
            "lineage_events_recorded": lineage_events,
            "l9_general_open_ended_passed": False,
            "l10_independent_passed": False,
        }
        result["deltas"] = {
            "solved_vs_v53": result["v54"]["solved"] - result["v53"]["solved"],
            "evaluations_vs_v53": result["v54"]["evaluations"] - result["v53"]["evaluations"],
            "distinct_semantics_vs_v53": len(s54) - len(s53),
        }
        return result
    finally:
        e54.close()
        a54.close()
        l54.close()
        e53.close()
        a53.close()
        e52.close()
        a52.close()
        m51.close()


def aggregate(results):
    return {
        "tasks": sum(r["tasks"] for r in results),
        "v54_solved": sum(r["v54"]["solved"] for r in results),
        "v53_solved": sum(r["v53"]["solved"] for r in results),
        "v54_evaluations": sum(r["v54"]["evaluations"] for r in results),
        "v53_evaluations": sum(r["v53"]["evaluations"] for r in results),
        "lineage_scaffold_routes": sum(r["v54"]["lineage_scaffold_routes"] for r in results),
        "lineage_events": sum(r["lineage_events_recorded"] for r in results),
        "l9_general_open_ended_passed": False,
    }
