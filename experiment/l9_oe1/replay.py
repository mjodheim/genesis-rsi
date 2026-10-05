"""Dream-style offline replay over previously observed discovery graphs."""
from __future__ import annotations

from collections import defaultdict
import json


def _descriptor(row):
    value = row.get("descriptor_json", {})
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _genome(row):
    value = row.get("genome_json", {})
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _structural_distance(a, b):
    """Target-blind distance between candidate programs known before evaluation."""
    width = max(1, int(a.get("width") or b.get("width") or 1))
    amask = int(a.get("mask", 0))
    bmask = int(b.get("mask", 0))
    mask_distance = (amask ^ bmask).bit_count() / width

    ar = int(a.get("rotation", 0)) % width
    br = int(b.get("rotation", 0)) % width
    raw = abs(ar - br)
    rotation_distance = min(raw, width - raw) / max(1, width // 2)
    return min(1.0, 0.65 * mask_distance + 0.35 * rotation_distance)


def _candidate_novelty(row, evaluated_rows):
    if not evaluated_rows:
        return 1.0
    genome = _genome(row)
    distances = sorted(
        _structural_distance(genome, _genome(other))
        for other in evaluated_rows
    )
    nearest = distances[: min(3, len(distances))]
    return sum(nearest) / len(nearest)


def _origin_priority(origin, genome):
    return {
        "exact": genome.replay_exact_priority,
        "scaffold": genome.replay_scaffold_priority,
        "abstract": genome.replay_abstract_priority,
        "search": genome.replay_search_priority,
    }.get(origin, genome.replay_search_priority)


def _policy_score(
    row,
    *,
    parent_quality,
    depth,
    candidate_novelty,
    genome,
):
    """Score without inspecting the candidate's own hidden evaluation."""
    origin = row.get("origin", "search")
    return (
        _origin_priority(origin, genome)
        + genome.replay_parent_quality_weight * (parent_quality / 1000.0)
        - genome.replay_depth_penalty * depth
        + genome.replay_candidate_novelty_weight * candidate_novelty
    )


def replay_task(rows, genome, *, budget=None):
    """Replay one recorded graph under a new target-blind search policy.

    Candidate quality is revealed only after the candidate is selected. The policy may
    use the already-observed quality of its evaluated parent, plus candidate source
    structure that is available before execution.
    """
    budget = genome.replay_budget if budget is None else budget
    unique = {}
    for row in rows:
        unique.setdefault(row["candidate_sha256"], row)
    nodes = unique

    children = defaultdict(list)
    roots = []
    depth = {}
    for sha, row in nodes.items():
        parent = row.get("parent_candidate_sha256")
        if parent and parent in nodes:
            children[parent].append(sha)
        else:
            roots.append(sha)

    # Compute structural depth only from graph topology, never candidate quality.
    queue = [(sha, 0) for sha in roots]
    while queue:
        sha, d = queue.pop(0)
        if sha in depth and depth[sha] <= d:
            continue
        depth[sha] = d
        queue.extend((child, d + 1) for child in children.get(sha, ()))

    evaluated = set()
    quality = {}
    best = 0
    solved = False

    for sha in roots:
        evaluated.add(sha)
        q = int(nodes[sha]["quality_milli"])
        quality[sha] = q
        best = max(best, q)
        solved = solved or q == 1000

    spent = 0
    order = []
    while spent < budget and not solved:
        evaluated_rows = [nodes[sha] for sha in evaluated]
        frontier = []
        for parent_sha in evaluated:
            parent_quality = quality[parent_sha]
            for child_sha in children.get(parent_sha, ()):
                if child_sha in evaluated:
                    continue
                child = nodes[child_sha]
                novelty = _candidate_novelty(child, evaluated_rows)
                frontier.append((
                    _policy_score(
                        child,
                        parent_quality=parent_quality,
                        depth=depth.get(child_sha, 1),
                        candidate_novelty=novelty,
                        genome=genome,
                    ),
                    child_sha,
                ))
        if not frontier:
            break

        frontier.sort(key=lambda item: (-item[0], item[1]))
        _, chosen = frontier[0]
        evaluated.add(chosen)
        order.append(chosen)
        q = int(nodes[chosen]["quality_milli"])
        quality[chosen] = q
        best = max(best, q)
        solved = solved or q == 1000
        spent += 1

    return {
        "solved": solved,
        "best_quality_milli": best,
        "evaluations": spent,
        "evaluated_candidates": order,
    }


def replay_suite(task_graphs, genome):
    results = {}
    solved = evaluations = quality = 0
    for task_sha, rows in task_graphs.items():
        outcome = replay_task(rows, genome)
        results[task_sha] = outcome
        solved += int(outcome["solved"])
        evaluations += outcome["evaluations"]
        quality += outcome["best_quality_milli"]
    return {
        "tasks": len(task_graphs),
        "solved": solved,
        "evaluations": evaluations,
        "quality_milli": quality,
        "results": results,
    }


def rank_mutations(task_graphs, parent_genome, *, top_k=8):
    """Score many improver mutations offline; no evaluator calls are made."""
    candidates = []
    for genome in parent_genome.mutate_one():
        result = replay_suite(task_graphs, genome)
        candidates.append((
            result["solved"],
            -result["evaluations"],
            result["quality_milli"],
            genome,
        ))
    candidates.sort(
        key=lambda row: (-row[0], -row[1], -row[2], row[3].sha256())
    )
    return tuple((
        genome,
        {
            "solved": solved,
            "evaluations": -neg_evals,
            "quality_milli": quality,
        },
    ) for solved, neg_evals, quality, genome in candidates[:top_k])
