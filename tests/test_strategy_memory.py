from __future__ import annotations

import pytest

from genesis import strategy_memory


def _result(operator: str = "integer_delta") -> dict:
    return {
        "schema": "example-result",
        "report_digest": "abc",
        "claim": "A2",
        "passed": True,
        "external_model_calls": 0,
        "passing_candidates": [
            {"id": "winner", "label": f"{operator}:src/a.js:12"}
        ],
    }


def test_memory_is_derived_from_unique_prior_winner() -> None:
    memory = strategy_memory.learn_from_result(_result())

    assert memory["successful_operator_counts"] == {"integer_delta": 1}
    assert memory["successful_candidate_ids"] == ["winner"]
    assert memory["memory_generation_external_model_calls"] == 0
    assert len(memory["memory_digest"]) == 64


def test_failed_or_ambiguous_prior_result_fails_closed() -> None:
    failed = _result()
    failed["passed"] = False
    with pytest.raises(ValueError):
        strategy_memory.learn_from_result(failed)

    ambiguous = _result()
    ambiguous["passing_candidates"].append(
        {"id": "other", "label": "boolean_toggle:src/b.js:3"}
    )
    with pytest.raises(ValueError):
        strategy_memory.learn_from_result(ambiguous)


def test_memory_ranking_is_stable_and_operator_only() -> None:
    memory = strategy_memory.learn_from_result(_result("integer_delta"))
    candidates = [
        {"id": "a", "provenance": {"operator": "comparison_boundary"}},
        {"id": "b", "provenance": {"operator": "integer_delta"}},
        {"id": "c", "provenance": {"operator": "boolean_toggle"}},
        {"id": "d", "provenance": {"operator": "integer_delta"}},
    ]

    ranked = strategy_memory.rank_candidates(candidates, memory)

    assert [item["candidate"]["id"] for item in ranked["records"]] == ["b", "d", "a", "c"]
    assert [item["base_index"] for item in ranked["records"]] == [1, 3, 0, 2]
    assert ranked["positive_score_count"] == 2
    assert ranked["external_model_calls"] == 0
