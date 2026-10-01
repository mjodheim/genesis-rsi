"""Prospective finite frontier/stopping descendants of exact qualified G2."""
from __future__ import annotations

from itertools import product

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.executable_family import predecessor_source

AXES = {"strategy": ("inherited", "quality_first", "frontier_mix"),
        "stop_quality": (780, 900, 1000), "stall_rounds": (3, 5, 8)}
ROOT_PARAMS = {"strategy": "inherited", "stop_quality": 780, "stall_rounds": 3}


def validate(params):
    if set(params) != set(AXES) or any(type(params[k]) is not type(v[0]) or params[k] not in v
                                      for k, v in AXES.items()):
        raise ValueError("V26 candidate outside the declared finite grammar")
    return dict(params)


def components(params):
    p = validate(params)
    return tuple(k for k in AXES if p[k] != ROOT_PARAMS[k])


def render(params):
    p = validate(params)
    source = predecessor_source()
    if p == ROOT_PARAMS:
        return source
    parallelism = 2 if p["strategy"] == "frontier_mix" else 1
    source = source.replace("if best >= 780:", f"if best >= {p['stop_quality']}:")
    source = source.replace("return (10, 6, 3, 5, 5, 4, 8, 1, 8, 3)",
                            f"return (10, 6, 3, 5, 5, 4, 8, {parallelism}, 8, {p['stall_rounds']})")
    if p["strategy"] == "inherited":
        return source
    marker = "    leaves = [\n"
    rank = (
        "    ranked = []\n"
        "    for index, row in enumerate(rows):\n"
        "        if row[\"node_id\"] in eligible and row[\"node_id\"] != root:\n"
        "            ranked.append((-int(row[\"outcome\"][\"quality_milli\"]), "
        "-int(row[\"lineage_depth\"]), index, row[\"node_id\"]))\n"
        "    ranked.sort()\n"
    )
    if p["strategy"] == "quality_first":
        body = ("    if ranked:\n        return [ranked[0][3]]\n"
                "    return [root] if root in eligible else []\n\n")
    else:
        body = (
            "    parents = [ranked[0][3]] if ranked else []\n"
            "    if root in eligible:\n        parents.append(root)\n"
            "    if root not in eligible:\n"
            "        parents = [row[3] for row in ranked[:2]]\n"
            "    return parents[:min(2, max(1, int(max_parallelism)))]\n\n"
        )
    if source.count(marker) != 1:
        raise ValueError("Exact G2 structural mutation anchor changed")
    return source.replace(marker, rank + body + marker)


def neighbors(params):
    p = validate(params)
    order = ("strategy", "stop_quality", "stall_rounds") if p == ROOT_PARAMS else (
        "stop_quality", "strategy", "stall_rounds")
    result = [{"axis": axis, "params": {**p, axis: value}}
              for axis, values in AXES.items() for value in values if value != p[axis]]
    return tuple(sorted(result, key=lambda row: (order.index(row["axis"]), str(row["params"][row["axis"]]),
                                               digest_bytes(render(row["params"]).encode()))))


def ablations(params):
    p = validate(params)
    return tuple({**p, axis: ROOT_PARAMS[axis]} for axis in components(p))


def universe():
    result = []
    for values in product(*AXES.values()):
        params = dict(zip(AXES, values))
        depth = len(components(params))
        if depth <= 2:
            result.append({"params": params, "source_sha256": digest_bytes(render(params).encode()),
                           "params_sha256": digest(params), "minimum_mutation_depth": depth,
                           "acquired_components": list(components(params))})
    return tuple(sorted(result, key=lambda row: (row["minimum_mutation_depth"], row["source_sha256"])))
