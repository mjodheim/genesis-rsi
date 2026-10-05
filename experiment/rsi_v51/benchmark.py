"""Matched V51 development benchmark: structured DB vs V32 archive vs cold."""
from __future__ import annotations

from collections import defaultdict

from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import bank, engine
from experiment.rsi_v51.memory import ExperimentalMemory


def _best_quality(row):
    return row["search"]["best_quality_milli"]


def _first_discoveries(rows):
    seen = set()
    per_window = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                per_window[row["window"]] += 1
    return seen, dict(per_window)


def run(seed, db_path, *, isolated=False, top_k=2, limit=None):
    tasks = bank.stream(seed)
    if limit is not None:
        tasks = tasks[:limit]
    memory = ExperimentalMemory(db_path)
    db_rows, archive_rows, cold_rows = [], [], []
    try:
        for position, task in enumerate(tasks):
            db_row = engine.episode(task, position, memory, top_k=top_k, isolated=isolated)
            db_row.update({"window": task["window"], "width": task["width"], "task_family": task["family"]})

            archive_history = v32.history_from(archive_rows)
            archive_row = v32.episode(task, position, archive_history, "adaptive", 25, isolated=isolated)
            cold_row = v32.episode(task, position, {}, "cold", 25, isolated=isolated)

            signature = memory.observed_signature(db_row["root_evaluation"]["quality_milli"])
            selected_ids = db_row["routing"]["retrieved_strategy_ids"]
            selected = {hit.strategy_id: hit for hit in memory.retrieve(
                signature,
                position=position,
                top_k=top_k,
                min_similarity=engine.MIN_SIMILARITY,
                min_utility=engine.MIN_UTILITY,
                compatible_width=task["width"],
            )}
            impact_quality = _best_quality(db_row) - _best_quality(cold_row)
            impact_evaluations = cold_row["charged_evaluations"] - db_row["charged_evaluations"]
            for rank, sid in enumerate(selected_ids):
                hit = selected.get(sid)
                if hit is not None:
                    memory.record_usage(
                        task_sha256=db_row["task_sha256"],
                        hit=hit,
                        position=position,
                        rank=rank,
                        impact_quality_milli=impact_quality,
                        impact_evaluations=impact_evaluations,
                    )

            engine.remember(memory, db_row)
            db_rows.append(db_row)
            archive_rows.append(archive_row)
            cold_rows.append(cold_row)

        db_seen, db_windows = _first_discoveries(db_rows)
        archive_seen = {
            semantic
            for row in archive_rows
            for semantic in (
                program["semantic_sha256"]
                for program in row["programs"]
                if program["quality_milli"] == 1000
            )
        }
        cold_seen = {
            semantic
            for row in cold_rows
            for semantic in (
                program["semantic_sha256"]
                for program in row["programs"]
                if program["quality_milli"] == 1000
            )
        }
        result = {
            "schema": "mira-genesis-v51-structured-memory-development-v1",
            "seed": seed,
            "tasks": len(tasks),
            "top_k": top_k,
            "population_scope": "PROJECT_AUTHORED_FINITE_DEVELOPMENT",
            "db": engine.summary(db_rows),
            "archive": v32.summary(archive_rows),
            "cold": v32.summary(cold_rows),
            "distinct_solved_semantics": {
                "db": len(db_seen),
                "archive": len(archive_seen),
                "cold": len(cold_seen),
            },
            "db_first_discoveries_by_window": {
                str(window): db_windows.get(window, 0)
                for window in sorted({task["window"] for task in tasks})
            },
            "memory_contribution": memory.contribution(),
            "memory_counts": memory.counts(),
        }
        result["predicates"] = {
            "db_retrieval_exercised": result["db"]["memory_routes"] > 0,
            "db_no_more_evaluations_than_cold": result["db"]["evaluations"] <= result["cold"]["evaluations"],
            "db_solved_at_least_cold": result["db"]["solved"] >= result["cold"]["solved"],
            "archive_grows": result["memory_counts"]["strategies"] > 1,
            "memory_usage_instrumented": result["memory_contribution"]["uses"] > 0,
            "all_observed_windows_retained": len(result["db_first_discoveries_by_window"]) == len(
                {task["window"] for task in tasks}
            ),
        }
        result["structured_memory_development_passed"] = all(result["predicates"].values())
        # A finite, project-authored benchmark cannot establish open-endedness.
        result["l9_general_open_ended_passed"] = False
        result["l10_independent_passed"] = False
        return result
    finally:
        memory.close()


def aggregate(results):
    if not results:
        raise ValueError("At least one V51 result is required")
    return {
        "schema": "mira-genesis-v51-structured-memory-development-aggregate-v1",
        "seeds": [row["seed"] for row in results],
        "tasks": sum(row["tasks"] for row in results),
        "db_solved": sum(row["db"]["solved"] for row in results),
        "archive_solved": sum(row["archive"]["solved"] for row in results),
        "cold_solved": sum(row["cold"]["solved"] for row in results),
        "db_evaluations": sum(row["db"]["evaluations"] for row in results),
        "archive_evaluations": sum(row["archive"]["evaluations"] for row in results),
        "cold_evaluations": sum(row["cold"]["evaluations"] for row in results),
        "structured_memory_development_passed": all(
            row["structured_memory_development_passed"] for row in results
        ),
        "l9_general_open_ended_passed": False,
        "l10_independent_passed": False,
    }
