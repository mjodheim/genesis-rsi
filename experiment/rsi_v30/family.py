"""Finite target selectors appended to the byte-exact qualified G6 policy."""
from itertools import product

from experiment.rsi_v25.commitments import ROOT, digest_bytes
from experiment.rsi_v30.pipeline_contexts import PARTS

PARENT = ROOT / "results/rsi-v28/chain-20261001/G6_SELECTED_POLICY.py"
PARENT_SHA256 = "154745c2f306c4e7ece2fd5bf4ce9fa8916e27df741711ec343d26ac653ca172"
ROOT_FLAGS = (0, 0, 0)


def validate(flags):
    if len(flags) != 3 or any(type(x) is not int or x not in (0, 1) for x in flags):
        raise ValueError("Unknown target selector genotype")
    return tuple(flags)


def parent():
    source = PARENT.read_text()
    if digest_bytes(source.encode()) != PARENT_SHA256:
        raise ValueError("Qualified G6 source changed")
    return source


def render(flags):
    flags = validate(flags)
    source = parent()
    if flags == ROOT_FLAGS:
        return source
    return source + (
        '\n\ndef select_target(diagnostics, targets):\n'
        f'    enabled = {flags!r}\n'
        f'    parts = {PARTS!r}\n'
        '    best, score = "identity", 0\n'
        '    for index, part in enumerate(parts):\n'
        '        value = enabled[index] * int(diagnostics[part])\n'
        '        if part in targets and value > score:\n'
        '            best, score = part, value\n'
        '    return best\n')


def fixed(target):
    from experiment.rsi_v30.pipeline_contexts import TARGETS
    if target not in TARGETS:
        raise ValueError("Unknown fixed target")
    return parent() + f'\n\ndef select_target(diagnostics, targets):\n    return {target!r}\n'


def universe():
    return tuple({"flags": flags, "source_sha256": digest_bytes(render(flags).encode())}
                 for flags in product((0, 1), repeat=3))


def neighbors(flags):
    flags = validate(flags)
    return tuple(tuple(1 if i == index else x for i, x in enumerate(flags))
                 for index in range(3) if not flags[index])
