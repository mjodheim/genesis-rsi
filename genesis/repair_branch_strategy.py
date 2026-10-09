"""Authored evidence-driven branch playbook; no bug-specific solution supplied."""
from copy import deepcopy

from genesis.repair_lineage import checked_genome

STRATEGY = """Repair decision protocol:
Before proposing edits, inspect the actual relevant source. Do not assume that a
class lacks an interface or that a mechanism is absent: check its declaration,
callers and existing configuration paths. Search/replace must quote inspected
source exactly, including implemented interfaces.
When graded attempts exist, choose an archived parent explicitly. Prefer extending
a compiling partial candidate when evidence supports retaining its changes; read
its changed source with read_file(branch=<archive digest>) and submit only the new
delta with parent=<same digest>. Do not copy inherited edits again. A changed
exception alone does not prove improvement. If the earlier hypothesis was wrong,
use parent="" explicitly and explain which observation falsified it.
After repeated failures in a chain of objects, investigate why the wrong objects
or configuration enter that chain. Check existing selection/configuration logic
before making successive failing classes conform to the desired property.
In hypothesis state: observation, causal explanation, chosen parent or reset and
what test outcome would refute the explanation. Every candidate must contain the
required parent field, hypothesis and files. Check the chosen source and exact
edits before the final submission; failed parents remain unverified hypotheses.
"""


def strategy_genome(parent):
    child = deepcopy(checked_genome(parent))
    child['playbook'] = STRATEGY + '\nExisting guidance:\n' + child['playbook']
    return checked_genome(child)
