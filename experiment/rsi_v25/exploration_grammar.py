"""Bounded V25 exploration-mechanism grammar.

This module deliberately mutates only parent-selection/exploration choices.
Evaluator identity, task populations, external budgets, trust root, evidence
ledger and adoption authority remain outside this grammar.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

STRATEGIES = ("fifo", "quality_first", "depth_first")
NOVELTY_WEIGHTS = (0, 1, 2)
DEPTH_WEIGHTS = (0, 1, 2)

class V25GrammarError(ValueError):
    pass

@dataclass(frozen=True)
class ExplorationMechanism:
    strategy: str
    novelty_weight: int
    depth_weight: int

    def validate(self) -> "ExplorationMechanism":
        if self.strategy not in STRATEGIES:
            raise V25GrammarError("strategy outside frozen grammar")
        if self.novelty_weight not in NOVELTY_WEIGHTS:
            raise V25GrammarError("novelty_weight outside frozen grammar")
        if self.depth_weight not in DEPTH_WEIGHTS:
            raise V25GrammarError("depth_weight outside frozen grammar")
        return self

    def digest(self) -> str:
        self.validate()
        payload={"depth_weight":self.depth_weight,"novelty_weight":self.novelty_weight,"strategy":self.strategy}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()

ROOT = ExplorationMechanism("fifo", 0, 0)

def universe() -> tuple[ExplorationMechanism, ...]:
    return tuple(
        ExplorationMechanism(s,n,d)
        for s in STRATEGIES for n in NOVELTY_WEIGHTS for d in DEPTH_WEIGHTS
    )

def choose_parent(mechanism: ExplorationMechanism, candidates: Sequence[Mapping[str, int]]) -> int:
    mechanism.validate()
    if not candidates:
        raise V25GrammarError("cannot select from empty candidates")
    def key(item: tuple[int, Mapping[str,int]]) -> tuple[int,int,int,int]:
        i,row=item
        quality=int(row["quality_milli"])
        depth=int(row["lineage_depth"])
        novelty=int(row["novelty"])
        if mechanism.strategy=="fifo":
            primary=-i
        elif mechanism.strategy=="quality_first":
            primary=quality
        else:
            primary=depth
        return (primary, mechanism.novelty_weight*novelty, mechanism.depth_weight*depth, -i)
    return max(enumerate(candidates), key=key)[0]

def decision_trace(mechanism: ExplorationMechanism, rounds: Iterable[Sequence[Mapping[str,int]]]) -> tuple[int,...]:
    return tuple(choose_parent(mechanism, candidates) for candidates in rounds)

def behaviorally_distinct(a: ExplorationMechanism, b: ExplorationMechanism, rounds: Iterable[Sequence[Mapping[str,int]]]) -> bool:
    frozen=tuple(tuple(dict(row) for row in r) for r in rounds)
    return decision_trace(a,frozen) != decision_trace(b,frozen)
