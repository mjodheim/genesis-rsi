"""Finite executable descendants of the byte-exact L4-qualified G2.

Only the declared parent-selection/stopping components change. The actual G2
source is the identity element, not a replacement synthetic FIFO controller.
"""
from __future__ import annotations

from collections import deque
from typing import Any, Mapping

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes

G2_PATH = ROOT / "experiment/rsi_v22/policies/g2_search_policy.py"
G1_PATH = ROOT / "experiment/rsi_v22/policies/g1_search_policy.py"
G2_SHA256 = "69d0d725601cd32adff27379dbb25f5c7be29946f9e9c6ac4858a0634cbd5fdf"
G1_SHA256 = "3354f887a93a08d9f00e9c54ccb097003f727ba77c1e1b4e9997adf676d35434"
AXES = {
    "depth_weight": (0, 1, 2),
    "novelty_weight": (0, 1, 2),
    "stall_rounds": (3, 5, 8),
    "stop_quality": (780, 900, 1000),
    "strategy": ("inherited", "quality_first", "fifo", "depth_first"),
}
ROOT_PARAMS = {
    "depth_weight": 0, "novelty_weight": 0, "stall_rounds": 3,
    "stop_quality": 780, "strategy": "inherited",
}


def exact_source(path, expected: str) -> str:
    raw = path.read_bytes()
    if digest_bytes(raw) != expected:
        raise ValueError("Preserved executable predecessor identity changed")
    return raw.decode()


def predecessor_source() -> str:
    return exact_source(G2_PATH, G2_SHA256)


def baseline_source() -> str:
    return exact_source(G1_PATH, G1_SHA256)


def predecessor_ablation_source() -> str:
    block = "    if best >= 780:\n        return []\n\n"
    source = predecessor_source()
    if source.count(block) != 1:
        raise ValueError("The preserved acquired G2 stopping component changed")
    return source.replace(block, "")


def validate_params(params: Mapping[str, Any]) -> dict[str, Any]:
    if set(params) != set(AXES):
        raise ValueError("Executable candidate does not match the declared grammar")
    result = {}
    for axis, values in AXES.items():
        value = params[axis]
        if type(value) is not type(values[0]) or value not in values:
            raise ValueError(f"Executable parameter outside the bounded grammar: {axis}")
        result[axis] = value
    return result


def render_source(params: Mapping[str, Any]) -> str:
    p = validate_params(params)
    source = predecessor_source()
    if p == ROOT_PARAMS:
        return source
    source = source.replace("if best >= 780:", f"if best >= {p['stop_quality']}:")
    source = source.replace(
        "return (10, 6, 3, 5, 5, 4, 8, 1, 8, 3)",
        f"return (10, 6, 3, 5, 5, 4, 8, 1, 8, {p['stall_rounds']})",
    )
    if p["novelty_weight"]:
        marker = "    leaves = [\n"
        # Only revealed mechanism features enter novelty. No task identifier,
        # source code, unseen child, evaluator case or global bank is accessible.
        block = (
            "    def novelty(row):\n"
            "        seen = set()\n"
            "        for other in rows:\n"
            "            if other[\"node_id\"] != row[\"node_id\"]:\n"
            "                seen = seen | set(other[\"action\"][\"mechanisms\"])\n"
            "        return len(set(row[\"action\"][\"mechanisms\"]) - seen)\n\n"
        )
        source = source.replace(marker, block + marker)
    novelty_term = 'novelty(row)' if p["novelty_weight"] else "0"
    if p["strategy"] == "inherited":
        # New weights change ranking only, preserving the inherited three-way
        # deep/promising/root branch structure and its authority boundary.
        if p["novelty_weight"] or p["depth_weight"]:
            source = source.replace(
                '(-int(row["lineage_depth"]), -int(row["outcome"]["quality_milli"]), row["node_id"])',
                '(-int(row["lineage_depth"]), '
                f'-int(row["outcome"]["quality_milli"]) - {p["novelty_weight"]} * 100 * '
                f'{novelty_term}, row["node_id"])',
            ).replace(
                '(int(row["outcome"]["quality_milli"]), row["node_id"])',
                f'(int(row["outcome"]["quality_milli"]) - {p["depth_weight"]} * 100 * '
                f'int(row["lineage_depth"]) - {p["novelty_weight"]} * 100 * '
                f'{novelty_term}, row["node_id"])',
            )
        return source
    marker = "    leaves = [\n"
    if source.count(marker) != 1:
        raise ValueError("Executable G2 parent-selection boundary changed")
    primary = {
        "quality_first": 'int(row["outcome"]["quality_milli"])',
        "fifo": "-index * 1000",
        "depth_first": 'int(row["lineage_depth"]) * 1000 + int(row["outcome"]["quality_milli"])',
    }[p["strategy"]]
    block = (
        "    ranked = []\n"
        "    for index, row in enumerate(rows):\n"
        "        if row[\"node_id\"] not in eligible:\n"
        "            continue\n"
        f"        score = ({primary})\n"
        f"        score += {p['depth_weight']} * 100 * int(row[\"lineage_depth\"])\n"
        f"        score += {p['novelty_weight']} * 100 * {novelty_term}\n"
        "        ranked.append((-score, index, row[\"node_id\"]))\n"
        "    ranked.sort()\n"
        "    return [ranked[0][2]]\n\n"
    )
    # The original fallback stays present as historical source; the replacement
    # executes before it. No task identity or evaluator literal is introduced.
    return source.replace(marker, block + marker)


def neighbors(params: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    parent = validate_params(params)
    rows = []
    for axis, values in AXES.items():
        index = values.index(parent[axis])
        targets = [x for x in values if x != parent[axis]] if axis == "strategy" else [
            values[i] for i in (index - 1, index + 1) if 0 <= i < len(values)
        ]
        for target in targets:
            child = {**parent, axis: target}
            rows.append({"axis": axis, "from": parent[axis], "to": target,
                         "params": child, "params_sha256": digest(child),
                         "source_sha256": digest_bytes(render_source(child).encode())})
    # The prospective question concerns an exploration component composed with
    # stopping. Open structural strategy branches first at the identity; after
    # a mutation, test stopping compositions before other structural variants.
    # This fixed ordering is shared by all meta arms and never reads outcomes.
    order = (("strategy", "novelty_weight", "depth_weight", "stop_quality", "stall_rounds")
             if parent == ROOT_PARAMS else
             ("stop_quality", "strategy", "novelty_weight", "depth_weight", "stall_rounds"))
    return tuple(sorted(rows, key=lambda row: (order.index(row["axis"]), str(row["to"]), row["source_sha256"])))


def acquired_components(params: Mapping[str, Any]) -> tuple[str, ...]:
    p = validate_params(params)
    return tuple(axis for axis in AXES if p[axis] != ROOT_PARAMS[axis])


def ablations(params: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    p = validate_params(params)
    return tuple({**p, axis: ROOT_PARAMS[axis]} for axis in acquired_components(p))


def universe() -> tuple[dict[str, Any], ...]:
    seen = {digest(ROOT_PARAMS): (dict(ROOT_PARAMS), 0)}
    queue = deque([(dict(ROOT_PARAMS), 0)])
    while queue:
        parent, depth = queue.popleft()
        if depth == 2:
            continue
        for row in neighbors(parent):
            key = row["params_sha256"]
            if key not in seen:
                seen[key] = (row["params"], depth + 1)
                queue.append((row["params"], depth + 1))
    return tuple(sorted((
        {"params": p, "params_sha256": key, "source_sha256": digest_bytes(render_source(p).encode()),
         "minimum_mutation_depth": depth} for key, (p, depth) in seen.items()
    ), key=lambda row: (row["minimum_mutation_depth"], row["params_sha256"])))
