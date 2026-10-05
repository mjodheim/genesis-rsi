"""Offline OE1 meta-search over the persistent discovery graph."""
from __future__ import annotations

import argparse
import json
from hashlib import sha256

from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.qd import BehaviorProfile, QDArchive
from experiment.l9_oe1.replay import rank_mutations, replay_suite
from experiment.l9_oe1.store import ExperienceStore


def _task_metadata(store):
    rows = store.fetchall(
        "SELECT task_sha256,family,width,task_window FROM oe_tasks"
    )
    return {row["task_sha256"]: row for row in rows}


def _profile(store, replay_result):
    meta = _task_metadata(store)
    solved = frozenset(
        task_sha
        for task_sha, outcome in replay_result["results"].items()
        if outcome["solved"]
    )
    tasks = list(replay_result["results"])
    mean_cost = (
        replay_result["evaluations"] / len(tasks) if tasks else 0.0
    )
    max_window = max(
        (meta[t]["task_window"] for t in tasks if t in meta),
        default=0,
    )
    late = [
        t for t in tasks
        if t in meta and meta[t]["task_window"] >= max(0, max_window - 2)
    ]
    late_rate = (
        sum(replay_result["results"][t]["solved"] for t in late) / len(late)
        if late else 0.0
    )
    trajectory_tokens = frozenset(
        task_sha + ":" + sha256(
            "|".join(replay_result["results"][task_sha]["evaluated_candidates"]).encode()
        ).hexdigest()[:16]
        for task_sha in tasks
    )
    solve_rate = len(solved) / len(tasks) if tasks else 0.0
    quality = solve_rate + 0.05 / max(1.0, mean_cost) + 0.10 * late_rate
    return BehaviorProfile(
        solved, mean_cost, late_rate, quality,
        trajectory_tokens=trajectory_tokens,
    )


def load_graphs(store):
    graphs = {}
    for task_sha in store.all_task_ids():
        graph = store.replay_graph(task_sha)
        if graph["nodes"]:
            graphs[task_sha] = graph
    return graphs


def search(store, *, top_k=8):
    graphs = load_graphs(store)
    root = ImproverGenome()
    root_sha = store.upsert_improver(root, generation=0)
    baseline = replay_suite(graphs, root)
    root_profile = _profile(store, baseline)

    archive = QDArchive(max_size=64)
    archive.add(root_sha, root_profile, learning_progress=0.0)

    ranked = rank_mutations(graphs, root, top_k=top_k)
    rows = []
    for genome, score in ranked:
        result = replay_suite(graphs, genome)
        profile = _profile(store, result)
        progress = profile.quality - root_profile.quality
        sha = store.upsert_improver(
            genome, parent_sha256=root_sha, generation=1
        )
        accepted, elite = archive.add(
            sha, profile, learning_progress=progress
        )
        rows.append({
            "improver_sha256": sha,
            "genome": genome.canonical(),
            "solved": result["solved"],
            "evaluations": result["evaluations"],
            "quality_milli": result["quality_milli"],
            "profile_quality": profile.quality,
            "novelty": elite.novelty,
            "learning_progress": progress,
            "archive_accepted": accepted,
        })

    archive.persist(store)
    parents = archive.parents(root, count=min(4, len(archive.elites)))
    return {
        "tasks": len(graphs),
        "baseline": {
            "improver_sha256": root_sha,
            "solved": baseline["solved"],
            "evaluations": baseline["evaluations"],
            "quality_milli": baseline["quality_milli"],
            "profile_quality": root_profile.quality,
        },
        "mutations_tested": len(root.mutate_one()),
        "top_mutations": rows,
        "archive_size": len(archive.elites),
        "next_parents": [
            {
                "improver_sha256": elite.improver_sha256,
                "quality": elite.profile.quality,
                "novelty": elite.novelty,
                "learning_progress": elite.learning_progress,
                "children": elite.children,
            }
            for elite in parents
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args(argv)
    store = ExperienceStore(args.dsn)
    try:
        print(json.dumps(search(store, top_k=args.top_k), indent=2, sort_keys=True))
    finally:
        store.close()


if __name__ == "__main__":
    main()
