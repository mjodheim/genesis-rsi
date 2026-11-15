"""Inert receipt aggregation.

Fingerprints and consistency checks do not establish authenticity.
McNemar, non-inferiority and lineage verification are outside this module.
"""

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TaskContext:
    """Externally supplied expectations for one task.

    ``policy`` is the caller's CodingPolicy instance. The validator supplied to
    aggregate_receipts must delegate to validate_task_receipt_consistency,
    adapting its existing interface without changing that interface.
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

def aggregate_receipts(
    receipts: Iterable[Mapping[str, Any]],
    contexts: Iterable[TaskContext],
    *,
    validate_task_receipt_consistency: Callable[
        [Mapping[str, Any], TaskContext], None
    ],
) -> Fitness:
    """Validate every receipt before computing counts.

    The required validator receives detached copies, must raise on inconsistent
    policy or receipt data, and must return None on success. No banks or judges
    are accessed here, and consumed budgets are only compared, never accounted.
    """
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
            raise TypeError("expected receipt mapping")
        receipt = deepcopy(dict(receipt))
        task_id = receipt.get("task_id")
        if type(task_id) is not str:
            raise ValueError("invalid task identifier")
        if task_id in received:
            raise ValueError("duplicate receipt")
        received[task_id] = receipt
    if received.keys() != expected.keys():
        raise ValueError("missing or additional tasks")

    for task_id, context in expected.items():
        receipt = received[task_id]
        if type(receipt.get("declared_result")) is not bool:
            raise ValueError("declared_result must have exact bool type")
        for name in (
            "task_id", "language", "judge", "bank_fingerprint", "consumed_budget"
        ):
            if name not in receipt:
                raise ValueError(f"missing receipt field: {name}")
            actual = receipt[name]
            wanted = getattr(context, name)
            if type(actual) is not type(wanted) or actual != wanted:
                raise ValueError(f"receipt context mismatch: {name}")
        outcome = validate_task_receipt_consistency(
            deepcopy(receipt), deepcopy(context)
        )
        if outcome is not None:
            raise ValueError("validator must raise on failure and return None")

    totals = {}
    for task_id, context in expected.items():
        previous = totals.get(context.language, Counts(0, 0))
        totals[context.language] = Counts(
            previous.successes + int(received[task_id]["declared_result"]),
            previous.tasks + 1,
        )
    return Fitness(
        Counts(sum(item.successes for item in totals.values()), len(expected)),
        dict(sorted(totals.items())),
    )
