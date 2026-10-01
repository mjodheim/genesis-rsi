"""Generated Genesis DreamPolicy executable.

State-based V19 search policy: follow promising continuations, keep opening the
root while early leaves look like decoys, and stop once a strong result is seen.
"""

def policy_metadata():
    return (10, 6, 3, 5, 5, 4, 8, 2, 8, 3)

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
            ranked.append((-int(row["outcome"]["quality_milli"]), -int(row["lineage_depth"]), index, row["node_id"]))
    ranked.sort()
    parents = [ranked[0][3]] if ranked else []
    if root in eligible:
        parents.append(root)
    if root not in eligible:
        parents = [row[3] for row in ranked[:2]]
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
