"""Build a one-hop counterfactual replay world from consumed V53 failures."""
from __future__ import annotations

import argparse
import json

from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.store import ExperienceStore
from experiment.rsi_v31 import engine as v31, programs


def expand_one_hop(store, *, code_sha, max_tasks=None):
    improver = ImproverGenome()
    improver_sha = store.upsert_improver(improver, generation=0)
    run_id = store.create_run(
        code_sha=code_sha,
        scope="CONSUMED_V53_ONE_HOP_COUNTERFACTUAL_WORLD",
        metadata={
            "fresh_evidence": False,
            "tuning_allowed": True,
            "expansion_depth": 1,
            "meaning": (
                "Counterfactual candidate evaluations for offline policy replay only"
            ),
        },
    )

    tasks = store.fetchall(
        """SELECT task_sha256,payload_json,task_window
           FROM oe_tasks ORDER BY task_window,task_sha256"""
    )

    summary = {
        "run_id": run_id,
        "tasks_considered": 0,
        "tasks_expanded": 0,
        "tasks_skipped_solved": 0,
        "tasks_skipped_existing": 0,
        "candidates_added": 0,
        "onehop_solutions": 0,
        "onehop_improvements": 0,
    }

    for task_row in tasks:
        if max_tasks is not None and summary["tasks_expanded"] >= max_tasks:
            break

        task_sha = task_row["task_sha256"]
        task = json.loads(task_row["payload_json"])
        rows = store.task_graph(task_sha)
        summary["tasks_considered"] += 1

        observed = [
            row for row in rows
            if row["origin"] != "counterfactual"
        ]
        if any(int(row["solved"]) for row in observed):
            summary["tasks_skipped_solved"] += 1
            continue
        if any(row["origin"] == "counterfactual" for row in rows):
            summary["tasks_skipped_existing"] += 1
            continue

        observed_shas = {
            row["candidate_sha256"] for row in observed
        }
        best_observed = max(
            int(row["quality_milli"]) for row in observed
        )
        position = min(int(row["position"]) for row in observed)
        host = v31.Host(task, {}, "cold", isolated=False)

        unseen = {}
        for parent in observed:
            parent_sha = parent["candidate_sha256"]
            genome = json.loads(parent["genome_json"])
            for child in programs.neighbors(genome):
                child_row = host.row(child)
                child_sha = child_row["source_sha256"]
                if child_sha in observed_shas:
                    continue
                record = unseen.setdefault(
                    child_sha,
                    {
                        "candidate_sha256": child_sha,
                        "candidate": child,
                        "parent_shas": set(),
                    },
                )
                record["parent_shas"].add(parent_sha)

        records = []
        task_solved = False
        task_improved = False
        for record in unseen.values():
            child_row = host.row(record["candidate"])
            quality = host.evaluate(child_row)["quality_milli"]
            task_solved = task_solved or quality == 1000
            task_improved = task_improved or quality > best_observed
            records.append({
                "candidate_sha256": record["candidate_sha256"],
                "candidate": record["candidate"],
                "parent_shas": sorted(record["parent_shas"]),
                "quality_milli": quality,
                "descriptor": {
                    "counterfactual": True,
                    "expansion_depth": 1,
                    "task_family": task.get("family"),
                    "width": task.get("width"),
                    "window": task.get("window"),
                },
            })

        store.record_counterfactual_batch(
            run_id=run_id,
            task_sha256=task_sha,
            improver_sha256=improver_sha,
            position=position,
            window=task.get("window"),
            records=records,
        )
        summary["tasks_expanded"] += 1
        summary["candidates_added"] += len(records)
        summary["onehop_solutions"] += int(task_solved)
        summary["onehop_improvements"] += int(task_improved)

    return summary


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--max-tasks", type=int)
    args = parser.parse_args(argv)

    store = ExperienceStore(args.dsn)
    try:
        print(json.dumps(
            expand_one_hop(
                store,
                code_sha=args.code_sha,
                max_tasks=args.max_tasks,
            ),
            indent=2,
            sort_keys=True,
        ))
    finally:
        store.close()


if __name__ == "__main__":
    main()
