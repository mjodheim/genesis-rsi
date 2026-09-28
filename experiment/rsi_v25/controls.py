"""Prospective V25 L5 control identities and externally enforced budgets.

This module defines only pre-holdout experimental structure. It contains no
final holdout tasks, outcomes, evaluator secrets or adoption authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from exploration_grammar import ExplorationMechanism, ROOT

REPRESENTED_REQUEST_BUDGET: Final = 9
ROUND_BUDGET: Final = 8
MAX_PARALLELISM: Final = 2
MUTATION_DEPTH: Final = 2

ARMS: Final = ("successor_meta", "exact_predecessor", "mechanism_ablation", "no_meta")


@dataclass(frozen=True)
class ExternalBudget:
    represented_requests: int = REPRESENTED_REQUEST_BUDGET
    rounds: int = ROUND_BUDGET
    max_parallelism: int = MAX_PARALLELISM
    mutation_depth: int = MUTATION_DEPTH

    def validate(self) -> "ExternalBudget":
        if self != ExternalBudget():
            raise ValueError("V25 external budget differs from prospective frozen caps")
        return self


@dataclass(frozen=True)
class ControlArm:
    name: str
    mechanism: ExplorationMechanism | None
    may_evolve_mechanism: bool

    def validate(self) -> "ControlArm":
        if self.name not in ARMS:
            raise ValueError("unknown V25 control arm")
        if self.name == "successor_meta" and not self.may_evolve_mechanism:
            raise ValueError("successor arm must exercise bounded mechanism evolution")
        if self.name != "successor_meta" and self.may_evolve_mechanism:
            raise ValueError("control arm may not evolve exploration mechanism")
        if self.name == "no_meta" and self.mechanism is not None:
            raise ValueError("no-meta arm must not carry a meta mechanism")
        if self.name in ("exact_predecessor", "mechanism_ablation") and self.mechanism != ROOT:
            raise ValueError("predecessor controls must begin at exact V25 root mechanism")
        return self


def prospective_arms() -> tuple[ControlArm, ...]:
    return (
        ControlArm("successor_meta", ROOT, True),
        ControlArm("exact_predecessor", ROOT, False),
        ControlArm("mechanism_ablation", ROOT, False),
        ControlArm("no_meta", None, False),
    )


def consume_budget(*, requests: int, rounds: int, parallelism: int, depth: int) -> None:
    budget = ExternalBudget().validate()
    values = (requests, rounds, parallelism, depth)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise ValueError("budget counters must be non-negative integers")
    if requests > budget.represented_requests:
        raise RuntimeError("external represented-request budget exceeded")
    if rounds > budget.rounds:
        raise RuntimeError("external round budget exceeded")
    if parallelism > budget.max_parallelism:
        raise RuntimeError("external parallelism budget exceeded")
    if depth > budget.mutation_depth:
        raise RuntimeError("external mutation-depth budget exceeded")
