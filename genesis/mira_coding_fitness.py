"""Inert receipt aggregation.

Fingerprints and consistency checks do not establish authenticity.
McNemar, non-inferiority and lineage verification are outside this module.

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


def aggregate_receipts(
    receipts: Iterable[Any],
    contexts: Iterable[TaskContext],
) -> Fitness:
    """Validate real receipts with the contract before counting their results.

    All expectations passed to the contract come from detached external
    contexts. Caller-provided validators are deliberately unsupported.
    """
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
        task_id = receipt.task_id
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
        declared_result = receipt.declared_result
        if type(declared_result) is not bool:
            raise ValueError("declared_result must have exact bool type")
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
