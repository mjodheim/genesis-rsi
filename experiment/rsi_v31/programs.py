"""Behaviorally distinct, bounded bit transducers around an unchanged G7 policy."""
import ast
from functools import lru_cache

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v25.search_engine import GUARD

PARENT = ROOT / "results/rsi-v30/target-20261001/G7_SELECTED_POLICY.py"
PARENT_SHA256 = "2e43fde55b4d17f9ab48be14322acb3d7f65dec8d3663cde068837d6d68b9ff4"


def parent():
    source = PARENT.read_text()
    if digest_bytes(source.encode()) != PARENT_SHA256:
        raise ValueError("Qualified G7 changed")
    return source


def validate(genome):
    if type(genome) is not dict or set(genome) != {"width", "rotation", "mask"}:
        raise ValueError("Invalid transducer genome")
    width, rotation, mask = (genome[key] for key in ("width", "rotation", "mask"))
    if (any(type(x) is not int for x in (width, rotation, mask)) or not 2 <= width <= 64
            or not 0 <= rotation < width or not 0 <= mask < 1 << width):
        raise ValueError("Transducer exceeds the fixed domain")
    return dict(genome)


def identity(width):
    return validate({"width": width, "rotation": 0, "mask": 0})


def render(genome):
    row = validate(genome)
    width, rotation, mask = (row[key] for key in ("width", "rotation", "mask"))
    source = parent() + (
        '\n\ndef transform(value):\n'
        f'    width, rotation, mask = {width}, {rotation}, {mask}\n'
        '    limit = (1 << width) - 1\n'
        '    return (((value << rotation) | (value >> (width - rotation))) & limit) ^ mask\n')
    if GUARD.guard_source(source, []):
        raise ValueError("Generated source violates the inherited guard")
    return source


def transform(genome, value):
    row = validate(genome)
    width, rotation, mask = (row[key] for key in ("width", "rotation", "mask"))
    return (((value << rotation) | (value >> (width - rotation))) & ((1 << width) - 1)) ^ mask


def neighbors(genome):
    row = validate(genome)
    for bit in range(row["width"]):
        yield {**row, "mask": row["mask"] ^ (1 << bit)}
    for step in (-1, 1):
        yield {**row, "rotation": (row["rotation"] + step) % row["width"]}


@lru_cache(maxsize=4096)
def describe(width, rotation, mask):
    row = validate({"width": width, "rotation": rotation, "mask": mask})
    source = render(row)
    axes = ["xor-bit-" + str(bit) for bit in range(width) if mask & (1 << bit)]
    if rotation:
        axes.append("rotation")
    return {"source_sha256": digest_bytes(source.encode()), "semantic_sha256": digest(row),
            "structure_sha256": digest_bytes(ast.dump(ast.parse(source)).encode()), "target_axes": axes}


def descriptor(genome):
    row = validate(genome)
    return describe(*(row[key] for key in ("width", "rotation", "mask")))
