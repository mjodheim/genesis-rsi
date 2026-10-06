"""The integrated Genesis runtime.

Separate from `metamorphosis/`, which holds frozen experiment modules. This package reuses their
validated invariants by construction and edits none of their sources.

The architecture splits in two and the split does not bend:

* `genesis.trust_root` is immutable. It holds isolation, budget, provenance and the final
  accept/reject, imports nothing from the rest of this package, and re-derives every number it
  decides on. Genesis must never be able to become better by modifying the measure that decides it
  is better.
* everything else is mutable Genesis, which may evolve.

Within mutable Genesis, `genesis.controller` owns the architecture state machine. A lineage-owned
mechanism receives the frozen `LineageContext` and returns a declarative intent; it spends no budget,
runs no probe, touches no journal and commits no state. That boundary is why the demonstration script
is a launcher rather than the architecture.
"""

# Genesis v2 architecture surfaces. These imports make the compatibility-first
# namespace explicit while historical flat modules migrate incrementally.
from . import core, evolution, languages, learning, memory, operators, runtime

__all__ = [
    "core",
    "evolution",
    "languages",
    "learning",
    "memory",
    "operators",
    "runtime",
]
