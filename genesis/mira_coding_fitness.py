"""Inert receipt aggregation.

Fingerprints and consistency checks do not establish authenticity.
McNemar, non-inferiority and lineage verification are outside this module.

This synthetic interface does not validate real CodingPolicy or
BankExternalReceipt objects; their integration remains to be established.
Initial negative evidence 425f5272292041f0a9aba16188c5fc8f: exit code 1,
TypeError: aggregate_receipts() got an unexpected keyword argument
'validate_task_receipt_consistency'.
No new execution results or capability gains are claimed.

Integration remains blocked: the supplied files do not include the contract's
import path, CodingPolicy.create and BankExternalReceipt.create signatures,
receipt envelope schema, or validate_task_receipt_consistency signature.
No tools or execution were authorized, so this diff has not been applied and
pytest has not been run; no output or return code is available.
Consistency alone proves neither truth, authenticity, nor judge independence.
"""

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class TaskContext:
    """Externally supplied expectations for one task.

    The synthetic validator receives a deep copy of this context and receipt.
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

    The required synthetic validator receives independent deep copies and must
    return None. Exceptions propagate. Languages come from external contexts.
    No banks or judges are accessed; budgets are compared, never accounted.
    """
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
        if type(receipt.get("declared_result")) is not bool:
            raise ValueError("declared_result must have exact bool type")

    for task_id, context in expected.items():
        result = validate_task_receipt_consistency(
            deepcopy(received[task_id]), deepcopy(context)
        )
        if result is not None:
            raise ValueError("consistency validator must return None")

    totals = {}
    for task_id, context in expected.items():
        previous = totals.get(context.language, Counts(0, 0))
        totals[context.language] = Counts(
            previous.successes
            + int(received[task_id]["declared_result"]),
            previous.tasks + 1,
        )
    return Fitness(
        Counts(sum(item.successes for item in totals.values()), len(expected)),
        dict(sorted(totals.items())),
    )
