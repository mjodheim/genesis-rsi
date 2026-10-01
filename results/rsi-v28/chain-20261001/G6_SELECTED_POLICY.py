"""Generated Genesis DreamPolicy executable.

State-based V19 search policy: follow promising continuations, keep opening the
root while early leaves look like decoys, and stop once a strong result is seen.
"""

def policy_metadata():
    return (10, 6, 3, 5, 5, 4, 8, 2, 8, 7)

def select_parent_batch(view, max_parallelism):
    rows = list(view["revealed_nodes"])
    eligible = list(view["eligible_parent_ids"])
    if not eligible:
        return []

    by_id = {row["node_id"]: row for row in rows}
    root = view["root_node_id"]
    best = max(int(row["outcome"]["quality_milli"]) for row in rows)

    if best >= 1000:
        return []

    ranked = []
    for index, row in enumerate(rows):
        if row["node_id"] in eligible and row["node_id"] != root:
            quality = int(row["outcome"]["quality_milli"])
            parent = by_id.get(row.get("parent_node_id", root), by_id[root])
            gain = quality - int(parent["outcome"]["quality_milli"])
            penalty = 400 if int(row["lineage_depth"]) >= 2 and quality > 0 and gain == 0 else 0
            signature = tuple(sorted(row["action"]["target_axes"]))
            repetitions = sum(tuple(sorted(other["action"]["target_axes"])) == signature for other in rows)
            memory_penalty = 150 * repetitions
            ranked.append((-quality + penalty + memory_penalty, -int(row["lineage_depth"]), index, row["node_id"]))
    ranked.sort()
    parents = [ranked[0][3]] if ranked else []
    if root in eligible:
        parents.append(root)
    if root not in eligible:
        parents = [row[3] for row in ranked[:2]]
    if len(parents) > 1 and root in parents:
        lead = by_id[parents[0]]
        previous = by_id.get(lead.get("parent_node_id", root), by_id[root])
        quality = int(lead["outcome"]["quality_milli"])
        if int(lead["lineage_depth"]) >= 2 and quality >= 900 and quality > int(previous["outcome"]["quality_milli"]):
            parents = parents[:1]
    return parents[:min(2, max(1, int(max_parallelism)))]

    leaves = [
        by_id[node_id]
        for node_id in eligible
        if node_id != root
    ]
    deep = [row for row in leaves if int(row["lineage_depth"]) >= 2]
    if deep:
        ranked = sorted([
            (-int(row["lineage_depth"]), -int(row["outcome"]["quality_milli"]), row["node_id"])
            for row in deep
        ])
        return [ranked[0][2]]

    promising = [
        row for row in leaves
        if int(row["outcome"]["quality_milli"]) <= 710
        or int(row["outcome"]["evolver_profile_generation"]) > 0
    ]
    if promising:
        ranked = sorted([
            (int(row["outcome"]["quality_milli"]), row["node_id"])
            for row in promising
        ])
        return [ranked[0][1]]

    if root in eligible:
        return [root]
    return []


def order_candidates(view, parent_id, candidates):
    parent = next(row for row in view["revealed_nodes"] if row["node_id"] == parent_id)
    previous = set(parent["action"]["target_axes"])
    ranked = []
    seen = set(row["action"].get("structure_sha256", "") for row in view["revealed_nodes"])
    for index, row in enumerate(candidates):
        axes = set(row["action"]["target_axes"])
        repeated = int(row["action"].get("structure_sha256", row["source_sha256"]) in seen)
        key = (1 * repeated, -len(axes - previous), -len(axes), index, row["source_sha256"])
        ranked.append(key)
    ranked.sort()
    return [row[4] for row in ranked]
