"""Inert receipt aggregation.

Fingerprints and consistency checks do not establish authenticity.
This module produces the four paired counts for McNemar's test.
Non-inferiority and lineage verification are outside this module.

Initial negative evidence 425f5272292041f0a9aba16188c5fc8f: exit code 1,
TypeError: aggregate_receipts() got an unexpected keyword argument
'validate_task_receipt_consistency'.
No new execution results or capability gains are claimed.

Compatibility with the receipt contract and the results of this correction
remain unverified. Targeted offline tests require execution and launch evidence;
neither is attested here.
Consistency alone proves neither truth, authenticity, nor judge independence.
"""

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from genesis import mira_policy_contract

@dataclass(frozen=True)
class TaskContext:
    """Externally supplied expectations for one task.

    Real aggregation requires a CodingPolicy. Synthetic aggregation is separate.
    """

    task_id: str
    language: str
    judge: str
    bank_fingerprint: str
    consumed_budget: Any
    policy: Any

@dataclass(frozen=True)
class Counts:
    successes: int
    tasks: int

@dataclass(frozen=True)
class Fitness:
    overall: Counts
    by_language: Mapping[str, Counts]


@dataclass(frozen=True)
class McNemarPairs:
    overall: tuple[int, ...]
    by_language: Mapping[str, tuple[int, ...]]

def count_mcnemar_pairs(
    left_receipts: Iterable[Any],
    left_contexts: Iterable[TaskContext],
    right_receipts: Iterable[Any],
    right_contexts: Iterable[TaskContext],
) -> McNemarPairs:
    """Count contractual pairs in the order both, left only, right only, neither."""
    left, left_results = _index_receipts(left_receipts, left_contexts)
    right, right_results = _index_receipts(right_receipts, right_contexts)
    for arm, contexts in (("left", left), ("right", right)):
        if len({context.policy.sha256 for context in contexts.values()}) != 1:
            raise ValueError(f"{arm} arm must have exactly one policy fingerprint")

    left_budget = next(iter(left.values())).policy.payload["task_budget"]
    right_budget = next(iter(right.values())).policy.payload["task_budget"]
    for component in ("models", "tokens", "proposals", "time_seconds"):
        if left_budget[component] != right_budget[component]:
            raise ValueError(f"paired allocated task_budget {component} mismatch")
    return _count_mcnemar_pairs(left, left_results, right, right_results)

def count_synthetic_mcnemar_pairs(
    left_receipts: Iterable[Mapping[str, Any]],
    left_contexts: Iterable[TaskContext],
    right_receipts: Iterable[Mapping[str, Any]],
    right_contexts: Iterable[TaskContext],
    *,
    validate_task_receipt_consistency: Callable[
        [Mapping[str, Any], TaskContext], None
    ],
) -> McNemarPairs:
    """Count synthetic pairs in the order both, left only, right only, neither."""
    left, left_results = _index_synthetic_receipts(
        left_receipts, left_contexts, validate_task_receipt_consistency
    )
    right, right_results = _index_synthetic_receipts(
        right_receipts, right_contexts, validate_task_receipt_consistency
    )
    return _count_mcnemar_pairs(left, left_results, right, right_results)


def _count_mcnemar_pairs(
    left: Mapping[str, TaskContext],
    left_results: Mapping[str, bool],
    right: Mapping[str, TaskContext],
    right_results: Mapping[str, bool],
) -> McNemarPairs:
    if left.keys() != right.keys():
        raise ValueError("paired task sets differ")
    for task_id, left_context in left.items():
        right_context = right[task_id]
        for name in ("bank_fingerprint", "judge", "language", "consumed_budget"):
            first = getattr(left_context, name)
            second = getattr(right_context, name)
            if type(first) is not type(second) or first != second:
                raise ValueError(f"paired {name} mismatch for task {task_id}")

    totals = {}
    overall = [0, 0, 0, 0]
    for task_id, context in left.items():
        index = 2 * int(not left_results[task_id]) + int(not right_results[task_id])
        totals.setdefault(context.language, [0, 0, 0, 0])[index] += 1
        overall[index] += 1
    return McNemarPairs(tuple(overall), {
        language: tuple(counts) for language, counts in sorted(totals.items())
    })

def aggregate_receipts(
    receipts: Iterable[Any],
    contexts: Iterable[TaskContext],
) -> Fitness:
    """Validate real receipts with the contract before counting their results.

    All expectations passed to the contract come from detached external
    contexts. Caller-provided validators are deliberately unsupported.
    """
    return _fitness(*_index_receipts(receipts, contexts))

def _index_receipts(
    receipts: Iterable[Any],
    contexts: Iterable[TaskContext],
) -> tuple[dict[str, TaskContext], dict[str, bool]]:
    contexts = deepcopy(list(contexts))
    receipts = deepcopy(list(receipts))
    expected = {}
    for context in contexts:
        if not isinstance(context, TaskContext):
            raise TypeError("expected TaskContext")
        for name in ("task_id", "language", "judge", "bank_fingerprint"):
            value = getattr(context, name)
            if type(value) is not str or not value:
                raise ValueError(f"explicit nonempty {name} required")
        if not isinstance(context.policy, mira_policy_contract.CodingPolicy):
            raise TypeError("expected CodingPolicy")
        if context.consumed_budget is None:
            raise ValueError("explicit consumed budget required")
        if context.task_id in expected:
            raise ValueError("duplicate task context")
        expected[context.task_id] = context
    if not expected:
        raise ValueError("empty task set")

    received = {}
    for receipt in receipts:
        if isinstance(receipt, Mapping):
            receipt = mira_policy_contract.BankExternalReceipt.from_dict(
                deepcopy(dict(receipt))
            )
        if not isinstance(receipt, mira_policy_contract.BankExternalReceipt):
            raise TypeError("expected BankExternalReceipt or serialized envelope")
        task_id = receipt.payload["task_id"]
        if type(task_id) is not str or not task_id:
            raise ValueError("invalid task identifier")
        if task_id in received:
            raise ValueError("duplicate receipt")
        received[task_id] = receipt
    if received.keys() != expected.keys():
        raise ValueError("missing or additional tasks")

    results = {}
    for task_id, context in expected.items():
        receipt = received[task_id]
        declared_result = _coding_success(receipt.payload)
        result = mira_policy_contract.validate_task_receipt_consistency(
            deepcopy(context.policy),
            deepcopy(receipt),
            context={
                "bank_sha256": deepcopy(context.bank_fingerprint),
                "consumed_budget": deepcopy(context.consumed_budget),
                "task_id": deepcopy(context.task_id),
                "judge_id": deepcopy(context.judge),
            },
        )
        if result is not None:
            raise ValueError("consistency validator must return None")
        results[task_id] = declared_result
    return expected, results


def _coding_success(payload: Mapping[str, Any]) -> bool:
    result = payload.get("declared_result")
    if type(result) is not bool:
        raise ValueError("declared_result must have exact bool type")
    return result

def _fitness(
    expected: Mapping[str, TaskContext], results: Mapping[str, bool],
) -> Fitness:
    totals = {}
    for task_id, context in expected.items():
        previous = totals.get(context.language, Counts(0, 0))
        totals[context.language] = Counts(
            previous.successes + int(results[task_id]),
            previous.tasks + 1,
        )
    return Fitness(
        Counts(sum(item.successes for item in totals.values()), len(expected)),
        dict(sorted(totals.items())),
    )

def aggregate_synthetic_receipts(
    receipts: Iterable[Mapping[str, Any]],
    contexts: Iterable[TaskContext],
    *,
    validate_task_receipt_consistency: Callable[
        [Mapping[str, Any], TaskContext], None
    ],
) -> Fitness:
    """Validate every receipt before computing counts.

    The required synthetic validator receives independent deep copies and must
    return None. Exceptions propagate. Languages come from external contexts.
    No banks or judges are accessed; budgets are compared, never accounted.
    """
    return _fitness(*_index_synthetic_receipts(
        receipts, contexts, validate_task_receipt_consistency
    ))

def _index_synthetic_receipts(
    receipts: Iterable[Mapping[str, Any]],
    contexts: Iterable[TaskContext],
    validate_task_receipt_consistency: Callable[
        [Mapping[str, Any], TaskContext], None
    ],
) -> tuple[dict[str, TaskContext], dict[str, bool]]:
    if not callable(validate_task_receipt_consistency):
        raise TypeError("a callable consistency validator is required")
    expected = {}
    for context in contexts:
        if not isinstance(context, TaskContext):
            raise TypeError("expected TaskContext")
        for name in ("task_id", "language", "judge", "bank_fingerprint"):
            value = getattr(context, name)
            if type(value) is not str or not value:
                raise ValueError(f"explicit nonempty {name} required")
        if context.policy is None or context.consumed_budget is None:
            raise ValueError("explicit policy and consumed budget required")
        if context.task_id in expected:
            raise ValueError("duplicate task context")
        expected[context.task_id] = deepcopy(context)
    if not expected:
        raise ValueError("empty task set")

    received = {}
    for receipt in receipts:
        if not isinstance(receipt, Mapping):
            raise TypeError("expected Mapping receipt")
        receipt = deepcopy(dict(receipt))
        task_id = receipt.get("task_id")
        if type(task_id) is not str or not task_id:
            raise ValueError("invalid task identifier")
        if task_id in received:
            raise ValueError("duplicate receipt")
        received[task_id] = receipt
    if received.keys() != expected.keys():
        raise ValueError("missing or additional tasks")

    results = {}
    for task_id, context in expected.items():
        receipt = received[task_id]
        for name in (
            "task_id", "language", "judge", "bank_fingerprint",
            "consumed_budget",
        ):
            value = getattr(context, name)
            if (
                name not in receipt
                or type(receipt[name]) is not type(value)
                or receipt[name] != value
            ):
                raise ValueError(f"receipt {name} mismatch")
        results[task_id] = _coding_success(receipt)

    for task_id, context in expected.items():
        result = validate_task_receipt_consistency(
            deepcopy(received[task_id]), deepcopy(context)
        )
        if result is not None:
            raise ValueError("consistency validator must return None")
    return expected, results
