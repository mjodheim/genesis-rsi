"""Bounded V25 exploration-mechanism grammar and auditable decision traces.

Only parent-selection/exploration choices are mutable here. Evaluators, task
populations, budgets, trust root, evidence ledger, credentials and adoption
authority remain external to this module.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

STRATEGIES = ("fifo", "quality_first", "depth_first")
NOVELTY_WEIGHTS = (0, 1, 2)
DEPTH_WEIGHTS = (0, 1, 2)
_REQUIRED_FEATURES = ("candidate_id", "source_sha256", "quality_milli", "lineage_depth", "novelty")


class V25GrammarError(ValueError):
    pass


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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

    def payload(self) -> dict[str, Any]:
        self.validate()
        return {
            "depth_weight": self.depth_weight,
            "novelty_weight": self.novelty_weight,
            "strategy": self.strategy,
        }

    def digest(self) -> str:
        return _digest(self.payload())


ROOT = ExplorationMechanism("fifo", 0, 0)


def universe() -> tuple[ExplorationMechanism, ...]:
    return tuple(
        ExplorationMechanism(strategy, novelty, depth)
        for strategy in STRATEGIES
        for novelty in NOVELTY_WEIGHTS
        for depth in DEPTH_WEIGHTS
    )


def _candidate(row: Mapping[str, Any]) -> dict[str, Any]:
    if set(row) != set(_REQUIRED_FEATURES):
        raise V25GrammarError("candidate view must contain only frozen observable features")
    candidate = {
        "candidate_id": str(row["candidate_id"]),
        "source_sha256": str(row["source_sha256"]),
        "quality_milli": int(row["quality_milli"]),
        "lineage_depth": int(row["lineage_depth"]),
        "novelty": int(row["novelty"]),
    }
    if not candidate["candidate_id"] or len(candidate["source_sha256"]) != 64:
        raise V25GrammarError("invalid candidate identity")
    return candidate


def _key(mechanism: ExplorationMechanism, index: int, row: Mapping[str, Any]) -> tuple[int, int, int, int]:
    quality = int(row["quality_milli"])
    depth = int(row["lineage_depth"])
    novelty = int(row["novelty"])
    if mechanism.strategy == "fifo":
        primary = -index
    elif mechanism.strategy == "quality_first":
        primary = quality
    else:
        primary = depth
    return (
        primary,
        mechanism.novelty_weight * novelty,
        mechanism.depth_weight * depth,
        -index,
    )


def decision_record(
    mechanism: ExplorationMechanism,
    candidates: Sequence[Mapping[str, Any]],
    *,
    round_index: int,
) -> dict[str, Any]:
    mechanism.validate()
    if isinstance(round_index, bool) or not isinstance(round_index, int) or round_index < 0:
        raise V25GrammarError("round_index must be a non-negative integer")
    frozen = tuple(_candidate(row) for row in candidates)
    if not frozen:
        raise V25GrammarError("cannot select from empty candidates")
    ids = [row["candidate_id"] for row in frozen]
    if len(ids) != len(set(ids)):
        raise V25GrammarError("candidate identities must be unique")
    selected_index = max(range(len(frozen)), key=lambda i: _key(mechanism, i, frozen[i]))
    selected = frozen[selected_index]
    return {
        "schema": "mira-genesis-rsi-v25-decision-trace-v1",
        "round_index": round_index,
        "mechanism": mechanism.payload(),
        "mechanism_sha256": mechanism.digest(),
        "observable_features": list(_REQUIRED_FEATURES),
        "tie_break": "stable-input-order-last-key=-index",
        "candidate_set_sha256": _digest(frozen),
        "candidate_ids": ids,
        "candidate_source_sha256": [row["source_sha256"] for row in frozen],
        "selected_index": selected_index,
        "selected_candidate_id": selected["candidate_id"],
        "selected_source_sha256": selected["source_sha256"],
    }


def choose_parent(mechanism: ExplorationMechanism, candidates: Sequence[Mapping[str, Any]]) -> int:
    return int(decision_record(mechanism, candidates, round_index=0)["selected_index"])


def decision_trace(
    mechanism: ExplorationMechanism,
    rounds: Iterable[Sequence[Mapping[str, Any]]],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        decision_record(mechanism, candidates, round_index=index)
        for index, candidates in enumerate(rounds)
    )


def behaviorally_distinct(
    a: ExplorationMechanism,
    b: ExplorationMechanism,
    rounds: Iterable[Sequence[Mapping[str, Any]]],
) -> bool:
    frozen = tuple(tuple(dict(row) for row in candidates) for candidates in rounds)
    a_selected = tuple(row["selected_candidate_id"] for row in decision_trace(a, frozen))
    b_selected = tuple(row["selected_candidate_id"] for row in decision_trace(b, frozen))
    return a_selected != b_selected
