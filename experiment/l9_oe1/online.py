"""Online OE1 search policy.

This executes the same target-blind priority policy used by replay, but candidates are
generated lazily from evaluated nodes and every selected candidate calls the real
evaluator. It therefore validates that replay improvements can exist online.
"""
from __future__ import annotations

from experiment.l9_oe1.improver import ImproverGenome
from experiment.l9_oe1.replay import _origin_priority, _structural_distance_features
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import programs
from experiment.rsi_v53 import engine as v53

MAX_EVALUATIONS = 14
SEARCH_BUDGET = MAX_EVALUATIONS - 2


def _feature(genome):
    width = max(1, int(genome.get("width", 1)))
    return (
        width,
        int(genome.get("rotation", 0)),
        int(genome.get("mask", 0)),
    )


def _novelty(candidate, evaluated):
    if not evaluated:
        return 1.0
    feature = _feature(candidate)
    distances = sorted(
        _structural_distance_features(feature, _feature(row["genome"]))
        for row in evaluated.values()
    )
    nearest = distances[: min(3, len(distances))]
    return sum(nearest) / len(nearest)


def episode(
    task,
    position,
    exact_memory,
    abstract_memory,
    *,
    improver=None,
    isolated=False,
):
    improver = improver or ImproverGenome(replay_budget=SEARCH_BUDGET)
    if improver.replay_budget > SEARCH_BUDGET:
        raise ValueError("OE1 online improver exceeds frozen 14-charge cap")

    host = v53.Host(
        task,
        exact_memory,
        abstract_memory,
        position,
        exact_top_k=improver.exact_top_k,
        abstract_top_k=improver.abstract_top_k,
        scaffold_top_k=improver.scaffold_top_k,
        scaffold_min_width=improver.scaffold_min_width,
        scaffold_root_quality_max=improver.scaffold_root_quality_max,
        isolated=isolated,
    )

    root = host.root_genome
    root_sha = programs.descriptor(root)["source_sha256"]
    evaluated = {
        root_sha: {
            "source_sha256": root_sha,
            "genome": root,
            "semantic_sha256": digest(root),
            "search_parent_source_sha256": None,
            "evaluation": host.initial,
            "quality_milli": host.initial["quality_milli"],
            "candidate_origin": "root",
            "depth": 0,
        }
    }
    frontier = {}

    def offer(genome, *, parent_sha, origin, depth):
        row = host.row(genome)
        sha = row["source_sha256"]
        if sha in evaluated:
            return
        item = frontier.setdefault(
            sha,
            {
                "row": row,
                "genome": genome,
                "parents": set(),
                "origins": set(),
                "depth": depth,
            },
        )
        item["parents"].add(parent_sha)
        item["origins"].add(origin)
        item["depth"] = min(item["depth"], depth)

    for memory_row in host.memory_rows:
        offer(
            memory_row["genome"],
            parent_sha=root_sha,
            origin=memory_row.get("memory_origin", "search"),
            depth=1,
        )
    for child in programs.neighbors(root):
        offer(child, parent_sha=root_sha, origin="search", depth=1)

    spent = 0
    solved = host.initial["quality_milli"] == 1000
    best_quality = host.initial["quality_milli"]
    success_semantics = []
    evaluated_abstract_sources = []
    evaluated_scaffold_sources = []

    while spent < improver.replay_budget and frontier and not solved:
        scored = []
        for sha, item in frontier.items():
            available_parents = [
                parent for parent in item["parents"] if parent in evaluated
            ]
            if not available_parents:
                continue
            parent_quality = max(
                evaluated[parent]["quality_milli"] for parent in available_parents
            )
            origin = max(
                item["origins"],
                key=lambda value: _origin_priority(value, improver),
            )
            novelty = _novelty(item["genome"], evaluated)
            score = (
                _origin_priority(origin, improver)
                + improver.replay_parent_quality_weight * (parent_quality / 1000.0)
                - improver.replay_depth_penalty * item["depth"]
                + improver.replay_candidate_novelty_weight * novelty
            )
            scored.append((score, sha, origin))

        if not scored:
            break
        scored.sort(key=lambda row: (-row[0], row[1]))
        _, chosen_sha, origin = scored[0]
        item = frontier.pop(chosen_sha)
        available_parents = sorted(
            parent for parent in item["parents"] if parent in evaluated
        )
        parent_sha = max(
            available_parents,
            key=lambda parent: (
                evaluated[parent]["quality_milli"],
                parent,
            ),
        )

        evaluation = host.evaluate(item["row"])
        spent += 1
        quality = evaluation["quality_milli"]
        record = {
            "source_sha256": chosen_sha,
            "genome": item["genome"],
            "semantic_sha256": digest(item["genome"]),
            "search_parent_source_sha256": parent_sha,
            "evaluation": evaluation,
            "quality_milli": quality,
            "candidate_origin": origin,
            "depth": item["depth"],
        }
        evaluated[chosen_sha] = record
        best_quality = max(best_quality, quality)

        if origin == "abstract":
            evaluated_abstract_sources.append(chosen_sha)
        if origin == "scaffold":
            evaluated_scaffold_sources.append(chosen_sha)

        if quality == 1000:
            solved = True
            success_semantics.append(record["semantic_sha256"])
            break

        for child in programs.neighbors(item["genome"]):
            offer(
                child,
                parent_sha=chosen_sha,
                origin="search",
                depth=item["depth"] + 1,
            )

    result = {
        "position": position,
        "task_sha256": digest(task),
        "search": {
            "best_quality_milli": best_quality,
            "represented_requests": spent,
        },
        "programs": list(evaluated.values()),
        "root_evaluation": host.initial,
        "routing": host.routing,
        "charged_evaluations": spent + 2,
        "solved": solved,
        "new_solutions": success_semantics,
        "evaluated_abstract_sources": evaluated_abstract_sources,
        "evaluated_scaffold_sources": evaluated_scaffold_sources,
        "oe1": {
            "improver_sha256": improver.sha256(),
            "search_budget": improver.replay_budget,
            "frontier_remaining": len(frontier),
        },
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError("OE1 online search escaped evaluation cap")
    return result


def remember(exact_memory, abstract_memory, row):
    return v53.remember(exact_memory, abstract_memory, row)


def summary(rows):
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "quality_milli": sum(row["search"]["best_quality_milli"] for row in rows),
        "evaluations": sum(row["charged_evaluations"] for row in rows),
        "new_solutions": sum(len(row["new_solutions"]) for row in rows),
    }
