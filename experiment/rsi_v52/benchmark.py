"""Matched V52 development: abstractions vs V51 exact DB vs archive vs cold."""
from __future__ import annotations

from collections import defaultdict

from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import bank, engine as v51
from experiment.rsi_v51.memory import ExperimentalMemory
from experiment.rsi_v52 import engine
from experiment.rsi_v52.abstractions import AbstractionMemory, instantiate


def _best(row):
    return row["search"]["best_quality_milli"]


def _discoveries(rows):
    seen = set()
    per_window = defaultdict(int)
    for row in rows:
        for semantic in row["new_solutions"]:
            if semantic not in seen:
                seen.add(semantic)
                per_window[row["window"]] += 1
    return seen, dict(per_window)


def _record_v51_usage(memory, row, cold, task):
    signature = memory.observed_signature(row["root_evaluation"]["quality_milli"])
    selected_ids = row["routing"]["retrieved_strategy_ids"]
    selected = {hit.strategy_id: hit for hit in memory.retrieve(
        signature, position=row["position"], top_k=row["routing"]["top_k"],
        min_similarity=v51.MIN_SIMILARITY, min_utility=v51.MIN_UTILITY,
        compatible_width=task["width"],
    )}
    quality_delta = _best(row) - _best(cold)
    evaluation_delta = cold["charged_evaluations"] - row["charged_evaluations"]
    for rank, sid in enumerate(selected_ids):
        hit = selected.get(sid)
        if hit is not None:
            memory.record_usage(
                task_sha256=row["task_sha256"], hit=hit, position=row["position"],
                rank=rank, impact_quality_milli=quality_delta,
                impact_evaluations=evaluation_delta,
            )


def run(seed, directory, *, isolated=False, limit=None, abstract_top_k=1,
        abstract_only_without_exact=False, allowed_modes=("low",), tasks=None,
        scope="CONSUMED_V51_PROJECT_AUTHORED_DEVELOPMENT"):
    tasks = bank.stream(seed) if tasks is None else list(tasks)
    if limit is not None:
        tasks = tasks[:limit]
    directory.mkdir(parents=True, exist_ok=True)
    v52_exact = ExperimentalMemory(directory / "v52-exact.db")
    v52_abstract = AbstractionMemory(directory / "v52-abstract.db")
    v51_memory = ExperimentalMemory(directory / "v51.db")
    v52_rows, v51_rows, archive_rows, cold_rows = [], [], [], []
    abstract_helpful = abstract_uses = 0
    try:
        for position, task in enumerate(tasks):
            cold = v32.episode(task, position, {}, "cold", 25, isolated=isolated)

            v51_row = v51.episode(task, position, v51_memory, isolated=isolated)
            v51_row.update({"window": task["window"], "width": task["width"], "task_family": task["family"]})
            _record_v51_usage(v51_memory, v51_row, cold, task)
            v51.remember(v51_memory, v51_row)

            v52_row = engine.episode(
                task, position, v52_exact, v52_abstract,
                abstract_top_k=abstract_top_k,
                abstract_only_without_exact=abstract_only_without_exact,
                allowed_modes=allowed_modes, isolated=isolated,
            )
            v52_row.update({"window": task["window"], "width": task["width"], "task_family": task["family"]})

            # Preserve V51-style feedback for exact memories inside V52.
            signature = v52_exact.observed_signature(v52_row["root_evaluation"]["quality_milli"])
            exact = {hit.strategy_id: hit for hit in v52_exact.retrieve(
                signature, position=position, top_k=2,
                min_similarity=v51.MIN_SIMILARITY, min_utility=v51.MIN_UTILITY,
                compatible_width=task["width"],
            )}
            exact_quality_delta = _best(v52_row) - _best(cold)
            exact_eval_delta = cold["charged_evaluations"] - v52_row["charged_evaluations"]
            for rank, sid in enumerate(v52_row["routing"]["exact_strategy_ids"]):
                hit = exact.get(sid)
                if hit is not None:
                    v52_exact.record_usage(
                        task_sha256=v52_row["task_sha256"], hit=hit, position=position, rank=rank,
                        impact_quality_milli=exact_quality_delta,
                        impact_evaluations=exact_eval_delta,
                    )

            # Attribute abstraction contribution against the matched V51 baseline.
            abstract_hits = v52_abstract.retrieve(
                root_quality_milli=v52_row["root_evaluation"]["quality_milli"],
                width=task["width"], position=position, top_k=abstract_top_k,
                allowed_modes=allowed_modes,
            )
            by_source = {}
            for hit in abstract_hits:
                genome = instantiate(hit.recipe, task["width"])
                from experiment.rsi_v31 import programs
                by_source[programs.descriptor(genome)["source_sha256"]] = hit
            quality_delta = _best(v52_row) - _best(v51_row)
            eval_delta = v51_row["charged_evaluations"] - v52_row["charged_evaluations"]
            evaluated = set(v52_row["evaluated_abstract_sources"])
            for source in evaluated:
                hit = by_source.get(source)
                if hit is None:
                    continue
                v52_abstract.record_usage(
                    task_sha256=v52_row["task_sha256"], hit=hit, position=position,
                    quality_delta_milli=quality_delta, evaluation_delta=eval_delta,
                )
                abstract_uses += 1
                abstract_helpful += int(
                    quality_delta > 0 or (quality_delta == 0 and eval_delta > 0)
                )

            # Recipe-level negative feedback rotates exploration; do not disable
            # the whole width because a later abstraction may still be useful.
            engine.remember(v52_exact, v52_abstract, v52_row)

            archive = v32.episode(
                task, position, v32.history_from(archive_rows), "adaptive", 25,
                isolated=isolated,
            )
            v52_rows.append(v52_row)
            v51_rows.append(v51_row)
            archive_rows.append(archive)
            cold_rows.append(cold)

        v52_seen, v52_windows = _discoveries(v52_rows)
        v51_seen, v51_windows = _discoveries(v51_rows)
        result = {
            "schema": "mira-genesis-v52-abstraction-memory-development-v1",
            "seed": seed, "tasks": len(tasks), "abstract_top_k": abstract_top_k,
            "abstract_only_without_exact": abstract_only_without_exact,
            "allowed_modes": list(allowed_modes) if allowed_modes is not None else None,
            "scope": scope,
            "v52": engine.summary(v52_rows),
            "v51": v51.summary(v51_rows),
            "archive": v32.summary(archive_rows),
            "cold": v32.summary(cold_rows),
            "distinct_solved_semantics": {
                "v52": len(v52_seen), "v51": len(v51_seen),
            },
            "v52_first_discoveries_by_window": {
                str(window): v52_windows.get(window, 0)
                for window in sorted({task["window"] for task in tasks})
            },
            "v51_first_discoveries_by_window": {
                str(window): v51_windows.get(window, 0)
                for window in sorted({task["window"] for task in tasks})
            },
            "abstraction_counts": v52_abstract.counts(),
            "width_policy": v52_abstract.width_policy(),
            "abstraction_contribution": {
                "uses": abstract_uses,
                "helpful_uses": abstract_helpful,
                "helpful_rate": abstract_helpful / abstract_uses if abstract_uses else 0.0,
            },
        }
        result["deltas"] = {
            "solved_vs_v51": result["v52"]["solved"] - result["v51"]["solved"],
            "evaluations_vs_v51": result["v52"]["evaluations"] - result["v51"]["evaluations"],
            "distinct_semantics_vs_v51": (
                result["distinct_solved_semantics"]["v52"]
                - result["distinct_solved_semantics"]["v51"]
            ),
        }
        result["l9_general_open_ended_passed"] = False
        result["l10_independent_passed"] = False
        return result
    finally:
        v52_exact.close()
        v52_abstract.close()
        v51_memory.close()


def aggregate(results):
    return {
        "tasks": sum(row["tasks"] for row in results),
        "v52_solved": sum(row["v52"]["solved"] for row in results),
        "v51_solved": sum(row["v51"]["solved"] for row in results),
        "archive_solved": sum(row["archive"]["solved"] for row in results),
        "cold_solved": sum(row["cold"]["solved"] for row in results),
        "v52_evaluations": sum(row["v52"]["evaluations"] for row in results),
        "v51_evaluations": sum(row["v51"]["evaluations"] for row in results),
        "abstract_candidates_evaluated": sum(
            row["v52"]["abstract_candidates_evaluated"] for row in results
        ),
        "l9_general_open_ended_passed": False,
    }
