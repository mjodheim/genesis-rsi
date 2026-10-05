"""Matched V53 scaffold benchmark against frozen V52 and inherited controls."""
from collections import defaultdict

from experiment.rsi_v31 import programs
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52 import engine as v52
from experiment.rsi_v52.abstractions import AbstractionMemory, instantiate
from experiment.rsi_v53 import engine


def _best(row):
    return row["search"]["best_quality_milli"]


def _discoveries(rows):
    seen = set()
    windows = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                windows[row["window"]] += 1
    return seen, dict(windows)


def _record_exact(memory, row, cold, task, ids):
    signature = memory.observed_signature(row["root_evaluation"]["quality_milli"])
    hits = {
        hit.strategy_id: hit
        for hit in memory.retrieve(
            signature,
            position=row["position"],
            top_k=2,
            min_similarity=v51.MIN_SIMILARITY,
            min_utility=v51.MIN_UTILITY,
            compatible_width=task["width"],
        )
    }
    q_delta = _best(row) - _best(cold)
    e_delta = cold["charged_evaluations"] - row["charged_evaluations"]
    for rank, strategy_id in enumerate(ids):
        hit = hits.get(strategy_id)
        if hit is not None:
            memory.record_usage(
                task_sha256=row["task_sha256"],
                hit=hit,
                position=row["position"],
                rank=rank,
                impact_quality_milli=q_delta,
                impact_evaluations=e_delta,
            )


def _record_abstract(memory, row, baseline, task):
    hits = memory.retrieve(
        root_quality_milli=row["root_evaluation"]["quality_milli"],
        width=task["width"],
        position=row["position"],
        top_k=1,
        allowed_modes=None,
    )
    by_source = {
        programs.descriptor(instantiate(hit.recipe, task["width"]))["source_sha256"]: hit
        for hit in hits
    }
    q_delta = _best(row) - _best(baseline)
    e_delta = baseline["charged_evaluations"] - row["charged_evaluations"]
    for source in set(row.get("evaluated_abstract_sources", ())):
        hit = by_source.get(source)
        if hit is not None:
            memory.record_usage(
                task_sha256=row["task_sha256"],
                hit=hit,
                position=row["position"],
                quality_delta_milli=q_delta,
                evaluation_delta=e_delta,
            )


def run(seed, directory, *, tasks, isolated=False, scope="V53_DEVELOPMENT"):
    tasks = list(tasks)
    directory.mkdir(parents=True, exist_ok=True)

    e53 = ExperimentalMemory(directory / "v53-exact.db")
    a53 = AbstractionMemory(directory / "v53-abstract.db")
    e52 = ExperimentalMemory(directory / "v52-exact.db")
    a52 = AbstractionMemory(directory / "v52-abstract.db")
    m51 = ExperimentalMemory(directory / "v51.db")

    r53, r52, r51, archive, cold_rows = [], [], [], [], []
    scaffold_tasks = scaffold_gains = scaffold_regressions = 0
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

            x53 = engine.episode(task, position, e53, a53, isolated=isolated)
            x53.update(window=task["window"], width=task["width"], task_family=task["family"])
            _record_exact(e53, x53, cold, task, x53["routing"]["exact_strategy_ids"])
            _record_abstract(a53, x53, x51, task)
            if x53["evaluated_scaffold_sources"]:
                scaffold_tasks += 1
                scaffold_gains += int(x53["solved"] and not x52["solved"])
                scaffold_regressions += int(x52["solved"] and not x53["solved"])
            engine.remember(e53, a53, x53)

            x_archive = v32.episode(
                task, position, v32.history_from(archive), "adaptive", 25,
                isolated=isolated,
            )

            r53.append(x53)
            r52.append(x52)
            r51.append(x51)
            archive.append(x_archive)
            cold_rows.append(cold)

        s53, w53 = _discoveries(r53)
        s52, w52 = _discoveries(r52)
        result = {
            "schema": "mira-genesis-v53-scaffold-benchmark-v1",
            "seed": seed,
            "tasks": len(tasks),
            "scope": scope,
            "v53": engine.summary(r53),
            "v52": v52.summary(r52),
            "v51": v51.summary(r51),
            "archive": v32.summary(archive),
            "cold": v32.summary(cold_rows),
            "distinct_solved_semantics": {"v53": len(s53), "v52": len(s52)},
            "v53_first_discoveries_by_window": {
                str(w): w53.get(w, 0) for w in sorted({t["window"] for t in tasks})
            },
            "v52_first_discoveries_by_window": {
                str(w): w52.get(w, 0) for w in sorted({t["window"] for t in tasks})
            },
            "scaffold_contribution": {
                "tasks_exercised": scaffold_tasks,
                "solve_gains_vs_v52": scaffold_gains,
                "solve_regressions_vs_v52": scaffold_regressions,
            },
            "l9_general_open_ended_passed": False,
            "l10_independent_passed": False,
        }
        result["deltas"] = {
            "solved_vs_v52": result["v53"]["solved"] - result["v52"]["solved"],
            "evaluations_vs_v52": result["v53"]["evaluations"] - result["v52"]["evaluations"],
            "distinct_semantics_vs_v52": len(s53) - len(s52),
        }
        return result
    finally:
        e53.close()
        a53.close()
        e52.close()
        a52.close()
        m51.close()


def aggregate(results):
    return {
        "tasks": sum(r["tasks"] for r in results),
        "v53_solved": sum(r["v53"]["solved"] for r in results),
        "v52_solved": sum(r["v52"]["solved"] for r in results),
        "v51_solved": sum(r["v51"]["solved"] for r in results),
        "archive_solved": sum(r["archive"]["solved"] for r in results),
        "cold_solved": sum(r["cold"]["solved"] for r in results),
        "v53_evaluations": sum(r["v53"]["evaluations"] for r in results),
        "v52_evaluations": sum(r["v52"]["evaluations"] for r in results),
        "scaffold_candidates_evaluated": sum(
            r["v53"]["scaffold_candidates_evaluated"] for r in results
        ),
        "scaffold_solve_gains_vs_v52": sum(
            r["scaffold_contribution"]["solve_gains_vs_v52"] for r in results
        ),
        "scaffold_solve_regressions_vs_v52": sum(
            r["scaffold_contribution"]["solve_regressions_vs_v52"] for r in results
        ),
        "l9_general_open_ended_passed": False,
    }
