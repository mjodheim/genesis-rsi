"""Synthetic aggregation tests; no execution results are attested here.

The validator below is a synthetic boundary double, not evidence about the
existing CodingPolicy or validate_task_receipt_consistency implementation.
"""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from genesis.mira_coding_fitness import (
    Counts,
    TaskContext,
    aggregate_receipts,
)

@pytest.fixture
def synthetic():
    contexts = [
        TaskContext("a", "python", "judge-a", "synthetic-bank", 3, {"id": "p"}),
        TaskContext("b", "rust", "judge-b", "synthetic-bank", 5, {"id": "p"}),
        TaskContext("c", "python", "judge-a", "synthetic-bank", 2, {"id": "p"}),
    ]
    receipts = [
        {
            "task_id": context.task_id,
            "language": context.language,
            "judge": context.judge,
            "bank_fingerprint": context.bank_fingerprint,
            "consumed_budget": context.consumed_budget,
            "policy": deepcopy(context.policy),
            "declared_result": result,
        }
        for context, result in zip(contexts, (True, True, False))
    ]
    return receipts, contexts

def synthetic_validator(receipt, context):
    if receipt["policy"] != context.policy:
        raise ValueError("synthetic policy mismatch")

def aggregate(receipts, contexts, validator=synthetic_validator):
    return aggregate_receipts(
        receipts, contexts, validate_task_receipt_consistency=validator
    )

def test_synthetic_exact_counts_and_all_permutations(synthetic):
    receipts, contexts = synthetic
    expected = aggregate(receipts, contexts)
    assert expected.overall == Counts(2, 3)
    assert expected.by_language == {
        "python": Counts(1, 2),
        "rust": Counts(1, 1),
    }
    for ordering in permutations(receipts):
        assert aggregate(ordering, reversed(contexts)) == expected

def test_synthetic_empty_set_rejected():
    with pytest.raises(ValueError):
        aggregate([], [])

@pytest.mark.parametrize("side", ["receipts", "contexts"])
def test_synthetic_duplicates_rejected(synthetic, side):
    receipts, contexts = synthetic
    if side == "receipts":
        receipts.append(deepcopy(receipts[0]))
    else:
        contexts.append(contexts[0])
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)

@pytest.mark.parametrize("change", ["missing", "additional"])
def test_synthetic_task_set_mismatch(synthetic, change):
    receipts, contexts = synthetic
    if change == "missing":
        receipts.pop()
    else:
        receipts.append(dict(receipts[0], task_id="extra"))
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)

@pytest.mark.parametrize("value", [0, 1, None, "true", [], {}])
def test_synthetic_malformed_results(synthetic, value):
    receipts, contexts = synthetic
    receipts[-1]["declared_result"] = value
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)

@pytest.mark.parametrize(
    "field,value",
    [
        ("policy", {"id": "different"}),
        ("bank_fingerprint", "different-bank"),
        ("consumed_budget", 99),
        ("consumed_budget", 3.0),
        ("task_id", "different-task"),
        ("judge", "different-judge"),
        ("language", "different-language"),
    ],
)
def test_synthetic_context_divergences(synthetic, field, value):
    receipts, contexts = synthetic
    receipts[0][field] = value
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)

def test_synthetic_missing_result(synthetic):
    receipts, contexts = synthetic
    del receipts[0]["declared_result"]
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)

def test_synthetic_no_mutation_even_by_validator(synthetic):
    receipts, contexts = synthetic
    before = deepcopy(synthetic)

    def mutating_validator(receipt, context):
        synthetic_validator(receipt, context)
        receipt.clear()
        context.policy.clear()

    aggregate(receipts, contexts, mutating_validator)
    assert synthetic == before

def test_synthetic_policy_required(synthetic):
    receipts, contexts = synthetic
    contexts[0] = replace(contexts[0], policy=None)
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)
