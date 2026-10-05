"""Matched V54 refinement benchmark against frozen V53."""
from collections import defaultdict

from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52.abstractions import AbstractionMemory
from experiment.rsi_v53 import benchmark as b53
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v54 import engine
from experiment.rsi_v54.refinements import RefinementMemory


def _discoveries(rows):
    seen = set()
    windows = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                windows[row["window"]] += 1
    return seen, dict(windows)


def _best(row):
    return row["search"]["best_quality_milli"]


def run(seed, directory, *, tasks, isolated=False,
        scope="CONSUMED_V53_PROSPECTIVE_V54_DEVELOPMENT"):
    tasks = list(tasks)
    directory.mkdir(parents=True, exist_ok=True)

    e54 = ExperimentalMemory(directory / "v54-exact.db")
    a54 = AbstractionMemory(directory / "v54-abstract.db")
    refinements = RefinementMemory(directory / "v54-refinements.db")

    e53 = ExperimentalMemory(directory / "v53-exact.db")
    a53 = AbstractionMemory(directory / "v53-abstract.db")
    m51 = ExperimentalMemory(directory / "v51.db")

    rows54, rows53, rows51, cold_rows = [], [], [], []
    refinement_uses = refinement_helpful = 0
    refinement_solve_gains = refinement_solve_regressions = 0

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

            hits = refinements.retrieve(
                root_quality_milli=x51["root_evaluation"]["quality_milli"],
                width=task["width"],
                position=position,
                top_k=engine.REFINEMENT_TOP_K,
            )
            hit_by_id = {
                hit.refinement_id: hit for hit in hits
            }

            x54 = engine.episode(
                task, position, e54, a54, refinements,
                isolated=isolated,
            )
            x54.update(
                window=task["window"],
                width=task["width"],
                task_family=task["family"],
            )
            b53._record_exact(
                e54, x54, cold, task,
                x54["routing"]["exact_strategy_ids"],
            )
            b53._record_abstract(a54, x54, x51, task)

            for refinement_id in set(
                x54["routing"]["refinement_ids"]
            ):
                hit = hit_by_id.get(refinement_id)
                if hit is None:
                    continue
                lineage_success = any(
                    row["quality_milli"] == 1000
                    and row["scaffold_ancestor_refinement_id"]
                    == refinement_id
                    for row in x54["programs"]
                )
                quality_delta = _best(x54) - _best(x53)
                evaluation_delta = (
                    x53["charged_evaluations"]
                    - x54["charged_evaluations"]
                )
                helpful = (
                    lineage_success
                    and (
                        quality_delta > 0
                        or (x54["solved"] and not x53["solved"])
                    )
                )
                refinements.record_usage(
                    task_sha256=x54["task_sha256"],
                    hit=hit,
                    position=position,
                    quality_delta_milli=quality_delta,
                    evaluation_delta=evaluation_delta,
                    helpful=helpful,
                )
                refinement_uses += 1
                refinement_helpful += int(helpful)

            if x54["evaluated_refined_scaffold_sources"]:
                refinement_solve_gains += int(
                    x54["solved"] and not x53["solved"]
                )
                refinement_solve_regressions += int(
                    x53["solved"] and not x54["solved"]
                )

            engine.remember(
                e54, a54, refinements, x54
            )

            rows54.append(x54)
            rows53.append(x53)
            rows51.append(x51)
            cold_rows.append(cold)

        seen54, windows54 = _discoveries(rows54)
        seen53, windows53 = _discoveries(rows53)
        return {
            "schema": "mira-genesis-v54-refinement-development-v1",
            "seed": seed,
            "tasks": len(tasks),
            "scope": scope,
            "configuration": {
                "scaffold_top_k": engine.SCAFFOLD_TOP_K,
                "refinement_top_k": engine.REFINEMENT_TOP_K,
                "scaffold_min_width": engine.SCAFFOLD_MIN_WIDTH,
                "scaffold_root_quality_max": (
                    engine.SCAFFOLD_ROOT_QUALITY_MAX
                ),
                "max_evaluations_per_task": (
                    engine.MAX_EVALUATIONS
                ),
            },
            "v54": engine.summary(rows54),
            "v53": v53.summary(rows53),
            "v51": v51.summary(rows51),
            "cold": v32.summary(cold_rows),
            "refinement_memory": refinements.counts(),
            "refinement_lineage_depths": (
                refinements.lineage_depths()
            ),
            "refinement_contribution": {
                "uses": refinement_uses,
                "helpful_uses": refinement_helpful,
                "helpful_rate": (
                    refinement_helpful / refinement_uses
                    if refinement_uses else 0.0
                ),
                "solve_gains_vs_v53": refinement_solve_gains,
                "solve_regressions_vs_v53": (
                    refinement_solve_regressions
                ),
            },
            "distinct_solved_semantics": {
                "v54": len(seen54),
                "v53": len(seen53),
            },
            "v54_first_discoveries_by_window": {
                str(window): windows54.get(window, 0)
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
                    engine.summary(rows54)["solved"]
                    - v53.summary(rows53)["solved"]
                ),
                "evaluations_vs_v53": (
                    engine.summary(rows54)["evaluations"]
                    - v53.summary(rows53)["evaluations"]
                ),
                "distinct_semantics_vs_v53": (
                    len(seen54) - len(seen53)
                ),
            },
            "l9_general_open_ended_passed": False,
            "l10_independent_passed": False,
        }
    finally:
        e54.close()
        a54.close()
        refinements.close()
        e53.close()
        a53.close()
        m51.close()


def aggregate(results):
    return {
        "tasks": sum(row["tasks"] for row in results),
        "v54_solved": sum(row["v54"]["solved"] for row in results),
        "v53_solved": sum(row["v53"]["solved"] for row in results),
        "cold_solved": sum(row["cold"]["solved"] for row in results),
        "v54_evaluations": sum(
            row["v54"]["evaluations"] for row in results
        ),
        "v53_evaluations": sum(
            row["v53"]["evaluations"] for row in results
        ),
        "refined_routes": sum(
            row["v54"]["refined_scaffold_routes"]
            for row in results
        ),
        "refined_lineage_successes": sum(
            row["v54"]["refined_lineage_successes"]
            for row in results
        ),
        "max_scaffold_generation_used": max(
            (
                row["v54"]["max_scaffold_generation_used"]
                for row in results
            ),
            default=0,
        ),
        "l9_general_open_ended_passed": False,
    }
