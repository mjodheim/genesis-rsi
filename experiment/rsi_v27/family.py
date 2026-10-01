"""Finite pipeline descendants of the byte-exact qualified V26 G3.

This is public DEVELOPMENT apparatus until a separate scientific freeze exists.
"""
from itertools import product

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes

PARENT = ROOT / "results/rsi-v26/frontier-20261001/G2_META_SELECTED_POLICY.py"
PARENT_SHA256 = "b0544067ae4fa93533d3b49f7e7cd9de0b101af4a9359c1bbca0760dae32bafa"
AXES = {"plateau": (0, 1, 2), "ordering": (0, 1, 2),
        "scheduling": (0, 1, 2), "persistence": (0, 1, 2)}
ROOT_PARAMS = dict.fromkeys(AXES, 0)
LAYOUTS = (0, 1, 2, 3)
# Metadata region precedes selector and appended proposal-ordering region in G3.
REGION_ORDER = ("persistence", "plateau", "scheduling", "ordering")


def validate(params):
    if set(params) != set(AXES) or any(type(params[k]) is not int or params[k] not in v
                                      for k, v in AXES.items()):
        raise ValueError("Unknown V27 pipeline genotype")
    return dict(params)


def render(params):
    p = validate(params)
    source = PARENT.read_text()
    if digest_bytes(source.encode()) != PARENT_SHA256:
        raise ValueError("Qualified V26 G3 identity changed")
    if p == ROOT_PARAMS:
        return source
    if p["persistence"]:
        stall = (3, 7, 8)[p["persistence"]]
        source = source.replace("return (10, 6, 3, 5, 5, 4, 8, 2, 8, 3)",
                                f"return (10, 6, 3, 5, 5, 4, 8, 2, 8, {stall})")
    if p["plateau"] or p["persistence"]:
        old = '            ranked.append((-int(row["outcome"]["quality_milli"]), -int(row["lineage_depth"]), index, row["node_id"]))'
        new = (
            '            quality = int(row["outcome"]["quality_milli"])\n'
            '            parent = by_id.get(row.get("parent_node_id", root), by_id[root])\n'
            '            gain = quality - int(parent["outcome"]["quality_milli"])\n'
            f'            penalty = {400 * p["plateau"]} if int(row["lineage_depth"]) >= 2 and quality > 0 and gain == 0 else 0\n'
            '            signature = tuple(sorted(row["action"]["target_axes"]))\n'
            '            repetitions = sum(tuple(sorted(other["action"]["target_axes"])) == signature for other in rows)\n'
            f'            memory_penalty = {150 * p["persistence"]} * repetitions\n'
            '            ranked.append((-quality + penalty + memory_penalty, -int(row["lineage_depth"]), index, row["node_id"]))')
        if source.count(old) != 1:
            raise ValueError("Qualified selector mutation anchor changed")
        source = source.replace(old, new)
    if p["scheduling"]:
        marker = '    return parents[:min(2, max(1, int(max_parallelism)))]'
        threshold = (1000, 900, 750)[p["scheduling"]]
        code = (
            '    if len(parents) > 1 and root in parents:\n'
            '        lead = by_id[parents[0]]\n'
            '        previous = by_id.get(lead.get("parent_node_id", root), by_id[root])\n'
            '        quality = int(lead["outcome"]["quality_milli"])\n'
            f'        if int(lead["lineage_depth"]) >= 2 and quality >= {threshold} and quality > int(previous["outcome"]["quality_milli"]):\n'
            '            parents = parents[:1]\n')
        if source.count(marker) != 1:
            raise ValueError("Qualified batch mutation anchor changed")
        source = source.replace(marker, code + marker)
    if p["ordering"]:
        source += '\n\ndef order_candidates(view, parent_id, candidates):\n'
        source += '    parent = next(row for row in view["revealed_nodes"] if row["node_id"] == parent_id)\n'
        source += '    previous = set(parent["action"]["target_axes"])\n    ranked = []\n'
        source += '    for index, row in enumerate(candidates):\n        axes = set(row["action"]["target_axes"])\n'
        if p["ordering"] == 1:
            source += '        key = (len(axes), -len(axes - previous), index, row["source_sha256"])\n'
        else:
            source += '        key = (-len(axes - previous), -len(axes), index, row["source_sha256"])\n'
        source += '        ranked.append(key)\n    ranked.sort()\n    return [row[3] for row in ranked]\n'
    return source


def components(params, base=ROOT_PARAMS):
    p, b = validate(params), validate(base)
    return tuple(k for k in AXES if p[k] != b[k])


def neighbors(params, *, locked=ROOT_PARAMS):
    p, locked = validate(params), validate(locked)
    rows = []
    for axis, values in AXES.items():
        if locked[axis]:
            continue
        for value in values:
            if abs(value - p[axis]) == 1:
                child = {**p, axis: value}
                rows.append({"axis": axis, "params": child,
                             "source_sha256": digest_bytes(render(child).encode())})
    return tuple(sorted(rows, key=lambda row: (row["axis"], row["params"][row["axis"]],
                                               row["source_sha256"])))


def universe():
    return tuple({"params": dict(zip(AXES, values)),
                  "source_sha256": digest_bytes(render(dict(zip(AXES, values))).encode()),
                  "params_sha256": digest(dict(zip(AXES, values)))}
                 for values in product(*AXES.values()))


def genotype(params, layout=0):
    if type(layout) is not int or layout not in LAYOUTS:
        raise ValueError("Unknown source-layout variant")
    return {"params": validate(params), "layout": layout}


def render_genotype(candidate):
    if set(candidate) != {"params", "layout"}:
        raise ValueError("Invalid pipeline genotype envelope")
    g = genotype(candidate["params"], candidate["layout"])
    source = render(g["params"])
    if g["layout"]:
        source += "\n# Declared source-layout variant: " + str(g["layout"]) + "\n"
    return source


def mutation_neighbors(candidate, *, locked=ROOT_PARAMS):
    g = genotype(candidate["params"], candidate["layout"])
    result = []
    for value in LAYOUTS:
        if abs(value - g["layout"]) == 1:
            result.append({"axis": "layout", "genotype": genotype(g["params"], value)})
    semantic = sorted(neighbors(g["params"], locked=locked), key=lambda row: (
        REGION_ORDER.index(row["axis"]), row["params"][row["axis"]]))
    result.extend({"axis": row["axis"], "genotype": genotype(row["params"], g["layout"])}
                  for row in semantic)
    return tuple(result)


def effective_universe():
    return tuple({"genotype": genotype(row["params"], layout),
                  "source_sha256": digest_bytes(render_genotype(genotype(row["params"], layout)).encode())}
                 for row in universe() for layout in LAYOUTS)
