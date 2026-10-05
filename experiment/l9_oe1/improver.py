"""Evolvable improver genomes for OE1."""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
from hashlib import sha256


@dataclass(frozen=True)
class ImproverGenome:
    """A complete search-improver policy rather than one solution recipe."""

    exact_top_k: int = 2
    abstract_top_k: int = 1
    scaffold_top_k: int = 2
    scaffold_pool: int = 8
    scaffold_min_width: int = 10
    scaffold_root_quality_max: int = 799

    parent_quality_weight: float = 1.0
    parent_novelty_weight: float = 0.7
    parent_progress_weight: float = 0.8
    parent_child_penalty: float = 0.5

    replay_budget: int = 12
    frontier_low: float = 0.20
    frontier_high: float = 0.80

    def canonical(self):
        return asdict(self)

    def sha256(self):
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return sha256(payload.encode()).hexdigest()

    def mutate_one(self):
        """Deterministic local neighbourhood used by OE1's meta-search."""
        variants = []
        knobs = {
            "abstract_top_k": (0, 1, 2),
            "scaffold_top_k": (1, 2, 3),
            "scaffold_pool": (4, 8, 12),
            "scaffold_min_width": (8, 10, 12),
            "scaffold_root_quality_max": (699, 749, 799, 849),
            "parent_novelty_weight": (0.3, 0.7, 1.1),
            "parent_progress_weight": (0.4, 0.8, 1.2),
            "parent_child_penalty": (0.25, 0.5, 0.75),
            "replay_budget": (8, 12, 16),
        }
        for field, values in knobs.items():
            current = getattr(self, field)
            for value in values:
                if value != current:
                    variants.append(replace(self, **{field: value}))
        unique = {}
        for variant in variants:
            unique.setdefault(variant.sha256(), variant)
        return tuple(unique.values())
