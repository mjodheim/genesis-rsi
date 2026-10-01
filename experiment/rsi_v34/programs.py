"""Four pure, project-authored grammars; observe behavior without semantic overclaim."""
import ast
from functools import lru_cache

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import GUARD
from experiment.rsi_v31.programs import PARENT_SHA256, parent

DOMAINS = ("arithmetic", "text", "sequence", "records")
MAX_STEPS = 128
EXPRESSIONS = {
    "arithmetic": ("value + 1", "value * 2", "value + 3", "-value"),
    "text": ('value + "a"', '"x" + value', 'value[::-1]', 'value.replace("ab", "ba")'),
    "sequence": ("value[::-1]", "value[1:] + value[:1]", "[item + 1 for item in value]", "value + [0]"),
    "records": ('{key: item for key, item in value.items() if key != "noise"}',
                '{("b" if key == "a" else key): item for key, item in value.items()}',
                "{key: item + 1 for key, item in value.items()}",
                '{**value, "field_" + str(len(value)): 0}'),
}
WITNESSES = {
    "arithmetic": (-7, -2, 0, 1, 3, 11),
    "text": ("", "ab", "ba", "xyz", "aabb", "caba"),
    "sequence": ([], [0], [1, -1], [3, 0, 2], [-4, 5, -2, 8]),
    "records": ({}, {"a": 1}, {"a": -1, "b": 2}, {"noise": 3, "c": 0}, {"field_1": 8}),
}


def validate(genome):
    if (type(genome) is not dict or set(genome) != {"domain", "steps"}
            or genome["domain"] not in DOMAINS or type(genome["steps"]) is not list
            or len(genome["steps"]) > MAX_STEPS
            or any(type(step) is not int or not 0 <= step < 4 for step in genome["steps"])):
        raise ValueError("Invalid pure grammar or resource capacity")
    return {"domain": genome["domain"], "steps": list(genome["steps"])}


def identity(domain):
    return validate({"domain": domain, "steps": []})


@lru_cache(maxsize=4096)
def source(domain, steps):
    validate({"domain": domain, "steps": list(steps)})
    body = '\n\ndef transform(value):\n    """Pure ' + domain + ' grammar."""\n'
    for step in steps:
        body += "    value = " + EXPRESSIONS[domain][step] + "\n"
    body += "    return value\n"
    value = parent() + body
    if GUARD.guard_source(value, []):
        raise ValueError("Generated grammar violates inherited pure-source guard")
    return value


def render(genome):
    row = validate(genome)
    return source(row["domain"], tuple(row["steps"]))


@lru_cache(maxsize=4096)
def describe(domain, steps):
    value = source(domain, steps)
    return {"source_sha256": digest_bytes(value.encode()), "genotype_sha256": digest({"domain": domain, "steps": list(steps)}),
            "structure_sha256": digest_bytes(ast.dump(ast.parse(value)).encode()),
            "target_axes": [f"step-{index}-op-{step}" for index, step in enumerate(steps)]}


def descriptor(genome):
    row = validate(genome)
    return describe(row["domain"], tuple(row["steps"]))


def neighbors(genome):
    row = validate(genome)
    steps = row["steps"]
    if steps:
        yield {**row, "steps": steps[:-1]}
        for op in range(4):
            if op != steps[-1]:
                yield {**row, "steps": [*steps[:-1], op]}
    if len(steps) < MAX_STEPS:
        for op in range(4):
            yield {**row, "steps": [*steps, op]}


def valid_value(domain, value):
    if domain == "arithmetic":
        return type(value) is int and abs(value) < 2 ** 256
    if domain == "text":
        return type(value) is str and len(value) <= 1024
    if domain == "sequence":
        return type(value) is list and len(value) <= 256 and all(type(x) is int and abs(x) < 2 ** 256 for x in value)
    return (type(value) is dict and len(value) <= 256 and all(type(k) is str and len(k) <= 64
            and type(v) is int and abs(v) < 2 ** 256 for k, v in value.items()))
