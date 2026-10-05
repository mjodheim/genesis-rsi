"""Dream-style offline replay over previously observed discovery graphs."""
from __future__ import annotations

from collections import defaultdict
import json


ORIGIN_BASE = {
    "exact": 0.60,
    "scaffold": 0.45,
    "abstract": 0.35,
    "search": 0.10,
}


def _descriptor(row):
    value = row.get("descriptor_json", {})
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _policy_score(row, *, parent_quality, genome):
    """Score without inspecting the candidate's own hidden evaluation."""
    origin = row.get("origin", "search")
    origin_weight = ORIGIN_BASE.get(origin, 0.0)
    if origin == "exact":
        origin_weight += 0.05 * genome.exact_top_k
    elif origin == "abstract":
        origin_weight += 0.05 * genome.abstract_top_k
    elif origin == "scaffold":
        origin_weight += 0.05 * genome.scaffold_top_k

    desc = _descriptor(row)
    depth = max(0, int(desc.get("depth_hint", 1)))
    return origin_weight + 0.35 * (parent_quality / 1000.0) - 0.03 * depth


def replay_task(rows, genome, *, budget=None):
    """Replay one recorded graph under a new target-blind search policy.

    Candidate quality is revealed only after the candidate is selected. The policy may
    use the already-observed quality of its evaluated parent, matching online search.
    """
    budget = genome.replay_budget if budget is None else budget
    unique = {}
    for row in rows:
        unique.setdefault(row["candidate_sha256"], row)
    nodes = unique
    children = defaultdict(list)
    roots = []
    for sha, row in nodes.items():
        parent = row.get("parent_candidate_sha256")
        if parent and parent in nodes:
            children[parent].append(sha)
        else:
            roots.append(sha)

    evaluated = set()
    quality = {}
    best = 0
    solved = False

    # Root observations are context, not replay budget.
    for sha in roots:
        evaluated.add(sha)
        q = int(nodes[sha]["quality_milli"])
        quality[sha] = q
        best = max(best, q)
        solved = solved or q == 1000

    spent = 0
    order = []
    while spent < budget and not solved:
        frontier = []
        for parent_sha in evaluated:
            parent_quality = quality[parent_sha]
            for child_sha in children.get(parent_sha, ()):
                if child_sha in evaluated:
                    continue
                child = nodes[child_sha]
                frontier.append((
                    _policy_score(child, parent_quality=parent_quality, genome=genome),
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
        candidates.append((result["solved"], -result["evaluations"], result["quality_milli"], genome))
    candidates.sort(key=lambda row: (-row[0], -row[1], -row[2], row[3].sha256()))
    return tuple((genome, {
        "solved": solved,
        "evaluations": -neg_evals,
        "quality_milli": quality,
    }) for solved, neg_evals, quality, genome in candidates[:top_k])
