"""Dream-style offline replay over previously observed discovery graphs."""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import json


@dataclass(frozen=True)
class PreparedGraph:
    nodes: dict
    children: dict
    roots: tuple
    depth: dict
    features: dict


def _genome(row):
    value = row.get("genome_json", {})
    return json.loads(value) if isinstance(value, str) else dict(value or {})


def _feature(row):
    genome = _genome(row)
    return (
        max(1, int(genome.get("width", 1))),
        int(genome.get("rotation", 0)),
        int(genome.get("mask", 0)),
    )


def _structural_distance_features(a, b):
    """Target-blind distance between candidate programs known before evaluation."""
    width = max(1, a[0], b[0])
    mask_distance = (a[2] ^ b[2]).bit_count() / width
    ar = a[1] % width
    br = b[1] % width
    raw = abs(ar - br)
    rotation_distance = min(raw, width - raw) / max(1, width // 2)
    return min(1.0, 0.65 * mask_distance + 0.35 * rotation_distance)


def prepare_graph(graph):
    """Compile DB rows once so many improvers can replay the graph cheaply."""
    if isinstance(graph, PreparedGraph):
        return graph
    if isinstance(graph, dict):
        rows = graph.get("nodes", ())
        extra_edges = graph.get("edges", ())
    else:
        rows = graph
        extra_edges = ()

    nodes = {}
    for row in rows:
        nodes.setdefault(row["candidate_sha256"], row)

    child_sets = defaultdict(set)
    parent_sets = defaultdict(set)
    for sha, row in nodes.items():
        parent = row.get("parent_candidate_sha256")
        if parent and parent in nodes:
            child_sets[parent].add(sha)
            parent_sets[sha].add(parent)

    for edge in extra_edges:
        parent = edge["parent_candidate_sha256"]
        child = edge["child_candidate_sha256"]
        if parent in nodes and child in nodes:
            child_sets[parent].add(child)
            parent_sets[child].add(parent)

    children = {
        parent: tuple(sorted(values))
        for parent, values in child_sets.items()
    }
    roots = tuple(sorted(sha for sha in nodes if not parent_sets.get(sha)))

    depth = {}
    queue = deque((sha, 0) for sha in roots)
    while queue:
        sha, d = queue.popleft()
        if sha in depth and depth[sha] <= d:
            continue
        depth[sha] = d
        queue.extend((child, d + 1) for child in children.get(sha, ()))

    features = {
        sha: _feature(row)
        for sha, row in nodes.items()
    }
    return PreparedGraph(nodes, children, roots, depth, features)


def prepare_suite(task_graphs):
    return {
        task_sha: prepare_graph(graph)
        for task_sha, graph in task_graphs.items()
    }


def _candidate_novelty(candidate_sha, evaluated, prepared):
    if not evaluated:
        return 1.0
    candidate = prepared.features[candidate_sha]
    distances = sorted(
        _structural_distance_features(candidate, prepared.features[other_sha])
        for other_sha in evaluated
    )
    nearest = distances[: min(3, len(distances))]
    return sum(nearest) / len(nearest)


def _origin_priority(origin, genome):
    return {
        "exact": genome.replay_exact_priority,
        "scaffold": genome.replay_scaffold_priority,
        "abstract": genome.replay_abstract_priority,
        "search": genome.replay_search_priority,
        "counterfactual": genome.replay_search_priority,
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
    return (
        _origin_priority(row.get("origin", "search"), genome)
        + genome.replay_parent_quality_weight * (parent_quality / 1000.0)
        - genome.replay_depth_penalty * depth
        + genome.replay_candidate_novelty_weight * candidate_novelty
    )


def replay_task(graph, genome, *, budget=None):
    """Replay one recorded graph under a new target-blind search policy."""
    prepared = prepare_graph(graph)
    budget = genome.replay_budget if budget is None else budget

    evaluated = set()
    quality = {}
    best = 0
    solved = False

    for sha in prepared.roots:
        evaluated.add(sha)
        q = int(prepared.nodes[sha]["quality_milli"])
        quality[sha] = q
        best = max(best, q)
        solved = solved or q == 1000

    spent = 0
    order = []
    while spent < budget and not solved:
        frontier = {}
        for parent_sha in evaluated:
            parent_quality = quality[parent_sha]
            for child_sha in prepared.children.get(parent_sha, ()):
                if child_sha in evaluated:
                    continue
                child = prepared.nodes[child_sha]
                novelty = _candidate_novelty(child_sha, evaluated, prepared)
                score = _policy_score(
                    child,
                    parent_quality=parent_quality,
                    depth=prepared.depth.get(child_sha, 1),
                    candidate_novelty=novelty,
                    genome=genome,
                )
                frontier[child_sha] = max(
                    frontier.get(child_sha, float("-inf")),
                    score,
                )

        if not frontier:
            break

        chosen = min(frontier, key=lambda sha: (-frontier[sha], sha))
        evaluated.add(chosen)
        order.append(chosen)
        q = int(prepared.nodes[chosen]["quality_milli"])
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
    for task_sha, graph in task_graphs.items():
        outcome = replay_task(graph, genome)
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
    prepared = prepare_suite(task_graphs)
    candidates = []
    for genome in parent_genome.mutate_one():
        result = replay_suite(prepared, genome)
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
