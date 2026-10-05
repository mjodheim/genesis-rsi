"""Content-addressed G8 scheduler descendants of exact qualified G7."""
from __future__ import annotations

from collections import deque
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes

G7_PATH = ROOT / "results/rsi-v30/target-20261001/G7_SELECTED_POLICY.py"
G7_SHA256 = "2e43fde55b4d17f9ab48be14322acb3d7f65dec8d3663cde068837d6d68b9ff4"

AXES = {
    "strategy": ("inherited", "weighted"),
    "repeat_weight": (0, 1, 2),
    "new_axes_weight": (0, 1, 2, 3),
    "axis_count_weight": (0, 1, 2),
    "mechanism_weight": (0, 1, 2),
    "commit_depth": (1, 2),
    "commit_quality": (400, 500, 700, 900),
}
ROOT_PARAMS = {
    "strategy": "inherited",
    "repeat_weight": 1,
    "new_axes_weight": 1,
    "axis_count_weight": 1,
    "mechanism_weight": 0,
    "commit_depth": 2,
    "commit_quality": 900,
}


def parent_source():
    raw = G7_PATH.read_bytes()
    if digest_bytes(raw) != G7_SHA256:
        raise ValueError("Exact qualified G7 source changed")
    return raw.decode()


def validate(params):
    if set(params) != set(AXES):
        raise ValueError("G8 scheduler params outside frozen schema")
    out = {}
    for axis, values in AXES.items():
        value = params[axis]
        if value not in values or type(value) is not type(values[0]):
            raise ValueError(f"Invalid G8 axis {axis}={value!r}")
        out[axis] = value
    return out


def render_source(params):
    p = validate(params)
    source = parent_source()
    if p == ROOT_PARAMS:
        return source

    commitment = 'if int(lead["lineage_depth"]) >= 2 and quality >= 900 and quality > int(previous["outcome"]["quality_milli"]):'
    replacement_commitment = (
        f'if int(lead["lineage_depth"]) >= {p["commit_depth"]} '
        f'and quality >= {p["commit_quality"]} '
        'and quality > int(previous["outcome"]["quality_milli"]):'
    )
    if source.count(commitment) != 1:
        raise ValueError("Qualified G7 commitment boundary changed")
    source = source.replace(commitment, replacement_commitment)

    if p["strategy"] == "inherited":
        return source

    start = source.index("def order_candidates(")
    end = source.index("\ndef select_target(", start)
    replacement = f'''def order_candidates(view, parent_id, candidates):
    parent = next(row for row in view["revealed_nodes"] if row["node_id"] == parent_id)
    previous = set(parent["action"].get("target_axes", []))
    seen = set(row["action"].get("structure_sha256", "") for row in view["revealed_nodes"])
    ranked = []
    for index, row in enumerate(candidates):
        action = row["action"]
        axes = set(action.get("target_axes", []))
        repeated = int(action.get("structure_sha256", row["source_sha256"]) in seen)
        mechanism = int(action.get("mechanism_rank", 0))
        score = (
            {p["repeat_weight"]} * 1000 * repeated
            - {p["new_axes_weight"]} * 100 * len(axes - previous)
            - {p["axis_count_weight"]} * 10 * len(axes)
            - {p["mechanism_weight"]} * mechanism
        )
        ranked.append((score, index, row["source_sha256"]))
    ranked.sort()
    return [row[2] for row in ranked]

'''
    return source[:start] + replacement + source[end + 1:]


def source_sha256(params):
    return digest_bytes(render_source(params).encode())


def neighbors(params):
    p = validate(params)
    rows = []
    for axis, values in AXES.items():
        current = p[axis]
        if axis == "strategy":
            targets = [value for value in values if value != current]
        else:
            index = values.index(current)
            targets = [
                values[i] for i in (index - 1, index + 1)
                if 0 <= i < len(values)
            ]
        for target in targets:
            child = {**p, axis: target}
            rows.append({
                "axis": axis,
                "from": current,
                "to": target,
                "params": child,
                "params_sha256": digest(child),
                "source_sha256": source_sha256(child),
            })
    return tuple(sorted(rows, key=lambda row: (
        row["axis"], str(row["to"]), row["source_sha256"]
    )))


def universe(max_depth=2):
    seen = {digest(ROOT_PARAMS): (dict(ROOT_PARAMS), 0)}
    queue = deque([(dict(ROOT_PARAMS), 0)])
    while queue:
        parent, depth = queue.popleft()
        if depth >= max_depth:
            continue
        for row in neighbors(parent):
            key = row["params_sha256"]
            if key in seen:
                continue
            seen[key] = (dict(row["params"]), depth + 1)
            queue.append((dict(row["params"]), depth + 1))
    return tuple(sorted((
        {
            "params": params,
            "params_sha256": key,
            "source_sha256": source_sha256(params),
            "mutation_depth": depth,
        }
        for key, (params, depth) in seen.items()
    ), key=lambda row: (row["mutation_depth"], row["params_sha256"])))


def ablations(params):
    p = validate(params)
    return tuple(
        {**p, axis: ROOT_PARAMS[axis]}
        for axis in AXES
        if p[axis] != ROOT_PARAMS[axis]
    )
