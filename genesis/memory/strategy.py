"""Outcome-derived strategy memory for the autonomous RSI software track.

A3 must distinguish retaining experience from merely hard-coding another
repair rule. This module stores only strategy features present in a prior
winning candidate's provenance and uses them to rank a fresh candidate set.
It does not inspect the new task's expected answer and does not create new
mutation operators.

The first retained feature is the successful generator operator identity.
Future memory versions may retain richer learned features, but they must remain
outcome-derived and auditable.
"""
from __future__ import annotations

from pathlib import Path
import json
from typing import Any, Mapping, Sequence

from genesis.trust_root import digest_of

STRATEGY_MEMORY_SCHEMA = "genesis-outcome-strategy-memory-v1"
RANKING_SCHEMA = "genesis-outcome-strategy-ranking-v1"


def _operator_from_record(record: Mapping[str, Any]) -> str:
    label = str(record.get("label", ""))
    if ":" not in label:
        raise ValueError("winning candidate label does not expose an operator")
    operator = label.split(":", 1)[0].strip()
    if not operator:
        raise ValueError("winning candidate operator is empty")
    return operator


def learn_from_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Create strategy memory strictly from a prior positive result artifact."""
    if not bool(result.get("passed")):
        raise ValueError("strategy memory requires a passing prior result")
    winners = list(result.get("passing_candidates") or [])
    if len(winners) != 1:
        raise ValueError("strategy memory requires exactly one winning candidate")

    winner = winners[0]
    operator = _operator_from_record(winner)
    payload: dict[str, Any] = {
        "schema": STRATEGY_MEMORY_SCHEMA,
        "source_result_schema": result.get("schema"),
        "source_report_digest": result.get("report_digest"),
        "source_claim": result.get("claim"),
        "successful_operator_counts": {operator: 1},
        "successful_candidate_ids": [winner.get("id")],
        "external_model_calls_in_source": int(result.get("external_model_calls", 0)),
        "memory_generation_external_model_calls": 0,
        "scope": "candidate-ranking-prior-only",
    }
    return {**payload, "memory_digest": digest_of(payload)}


def load_result(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def learn_from_result_file(path: str | Path) -> dict[str, Any]:
    return learn_from_result(load_result(path))


def score_candidate(candidate: Mapping[str, Any], memory: Mapping[str, Any]) -> int:
    provenance = candidate.get("provenance") or {}
    operator = str(provenance.get("operator", ""))
    counts = memory.get("successful_operator_counts") or {}
    try:
        return int(counts.get(operator, 0))
    except (TypeError, ValueError):
        return 0


def rank_candidates(
    candidates: Sequence[Mapping[str, Any]],
    memory: Mapping[str, Any],
) -> dict[str, Any]:
    """Stable-sort candidates by retained prior success, preserving base-order ties."""
    ranked = sorted(
        enumerate(candidates),
        key=lambda pair: (-score_candidate(pair[1], memory), pair[0]),
    )
    records = [
        {
            "base_index": base_index,
            "memory_score": score_candidate(candidate, memory),
            "candidate": dict(candidate),
        }
        for base_index, candidate in ranked
    ]
    payload: dict[str, Any] = {
        "schema": RANKING_SCHEMA,
        "memory_digest": memory.get("memory_digest"),
        "candidate_count": len(candidates),
        "positive_score_count": sum(1 for item in records if item["memory_score"] > 0),
        "records": records,
        "external_model_calls": 0,
    }
    return {**payload, "ranking_digest": digest_of(payload)}
