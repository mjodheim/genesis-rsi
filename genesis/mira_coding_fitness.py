"""Inert receipt aggregation and ablation policy resolution.

Fingerprints and consistency checks do not establish authenticity.
This module produces paired counts and assesses non-inferiority using
parameters set by the external protocol. External judge integration, registry
authentication, and freezing before evaluation remain unverified.
Evidence 66dcca637bf1470bb8a4337d1be558ab covers the baseline only.

Initial negative evidence 425f5272292041f0a9aba16188c5fc8f: exit code 1,
TypeError: aggregate_receipts() got an unexpected keyword argument
'validate_task_receipt_consistency'.

Evidence 00874e07781f4881a6ad62584478df61 reports 153 passing fitness tests,
including the Python development bank test. Its scope is the reported
fitness run. The development bank uses nonempty lists for max and min.
Fresh verification requires a pytest run without network access or model
use, with exit code 0 and 153 passing fitness tests.
Consistency alone proves neither truth, authenticity, nor judge independence.

Evidence 508b49fef5e74d0e866f83aa98221b8d records that cryptography was absent
from the image used. The image rebuild remains to be confirmed.
Eight-language calibration and Ed25519 validation remain open.
Milestone 2 still requires verification of an established signature
primitive in the offline container and of the applicable publication terms.
The production channel for the independent counter remains unconfirmed.
Receipt authentication has not been implemented.
"""

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from fractions import Fraction
from math import comb, inf, nextafter
from typing import Any

from genesis import mira_policy_contract


def resolve_ablation_parent(
    child: mira_policy_contract.CodingPolicy,
    lineage_by_child_sha256: Mapping[str, str],
    validated_policies_by_sha256: Mapping[str, mira_policy_contract.CodingPolicy],
) -> mira_policy_contract.CodingPolicy:
    """Resolve the parent for the external caller before it invokes the judge.

    The caller supplies judge-side registries authenticated and frozen before
    evaluation, outside the candidate's control.
    """
    validated_child = _validate_ablation_policy(child, "child")

    parent_sha256 = lineage_by_child_sha256.get(validated_child.sha256)
    if parent_sha256 is None:
        raise ValueError("missing ablation lineage")
    if parent_sha256 == validated_child.sha256:
        raise ValueError("ablation parent must differ from child")
    parent = validated_policies_by_sha256.get(parent_sha256)
    if parent is None:
        raise ValueError("ablation parent policy not found")
    validated_parent = _validate_ablation_policy(parent, "parent")
    if validated_parent.sha256 != parent_sha256:
        raise ValueError("ablation parent fingerprint mismatch")
    return validated_parent


def _validate_ablation_policy(
    policy: mira_policy_contract.CodingPolicy, side: str,
) -> mira_policy_contract.CodingPolicy:
    if type(policy) is not mira_policy_contract.CodingPolicy:
        raise TypeError(f"expected {side} CodingPolicy")
    envelope = policy.envelope
    if type(envelope) is not mira_policy_contract.JsonObjectEnvelope:
        raise TypeError(f"expected {side} JsonObjectEnvelope")
    validated_envelope = mira_policy_contract.JsonObjectEnvelope(
        version=envelope.version,
        canonical_utf8=envelope.canonical_utf8,
        sha256=envelope.sha256,
    )
    return mira_policy_contract.CodingPolicy(
        version=policy.version, envelope=validated_envelope
    )

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

    @property
    def success_rate_difference_by_language(self) -> dict[str, float]:
        """Return the descriptive paired success rate difference (left minus right)."""
        differences = {}
        for language, (both, left_only, right_only, neither) in self.by_language.items():
            differences[language] = (left_only - right_only) / (
                both + left_only + right_only + neither
            )
        return differences


@dataclass(frozen=True)
class LanguageNonInferiority:
    difference: float
    lower_bound: float

    def passes(self, delta: float) -> bool:
        return self.lower_bound > -delta

def assess_paired_non_inferiority(
    pairs: McNemarPairs,
    required_languages: Iterable[str],
    *,
    delta: float,
    alpha: float,
) -> tuple[bool, dict[str, LanguageNonInferiority | None]]:
    """Return the global decision and each required language's assessment.

    Within a language, assume complete, correctly matched binary outcomes and
    independent pairs with common outcome probabilities. Outcomes within a
    pair may be dependent. All pairs contribute to the denominator.
    Bonferroni combines two one-sided Clopper–Pearson bounds per language.
    The intersection-union test controls the global false positive rate at
    alpha without assuming independence across languages or providing
    simultaneous coverage for their bounds. None denotes an unevaluable
    language. The external protocol specifies languages, delta, and alpha.
    """
    if type(delta) not in (int, float) or not 0 < delta <= 1:
        raise ValueError("delta must be in (0, 1]")
    if type(alpha) not in (int, float) or not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    if isinstance(required_languages, (str, bytes)):
        raise ValueError("required_languages must be a collection of languages")
    languages = tuple(required_languages)
    if not languages or any(
        type(language) is not str or not language.strip() for language in languages
    ):
        raise ValueError("required languages must be nonempty strings")
    if len(set(languages)) != len(languages):
        raise ValueError("required languages must be unique")
    _validate_pair_counts(pairs.overall)
    language_counts = tuple(pairs.by_language.values())
    for counts in language_counts:
        _validate_pair_counts(counts)
    totals = tuple(
        sum(counts[index] for counts in language_counts) for index in range(4)
    )
    if pairs.overall != totals:
        raise ValueError("overall pair counts must equal the sum of all language counts")

    tail = Fraction(alpha) / 2
    results: dict[str, LanguageNonInferiority | None] = {}
    for language in languages:
        counts = pairs.by_language.get(language)
        if counts is None or not sum(counts):
            results[language] = None
            continue
        _, left_only, right_only, _ = counts
        size = sum(counts)
        lower_left = _binomial_lower_bound(left_only, size, tail)
        lower_complement = _binomial_lower_bound(size - right_only, size, tail)
        exact_lower_bound = Fraction(lower_left) + Fraction(lower_complement) - 1
        lower_bound = float(exact_lower_bound)
        if Fraction(lower_bound) > exact_lower_bound:
            lower_bound = nextafter(lower_bound, -inf)
        results[language] = LanguageNonInferiority(
            (left_only - right_only) / size, lower_bound
        )
    return all(result is not None and result.passes(delta) for result in results.values()), results

def mcnemar_exact_pvalue(left_only: int, right_only: int) -> float:
    """Return the descriptive two-sided exact p-value for discordant counts."""
    if type(left_only) is not int or type(right_only) is not int:
        raise ValueError("discordant counts must have exact int type")
    if left_only < 0 or right_only < 0:
        raise ValueError("discordant counts must be nonnegative")
    discordant = left_only + right_only
    lower = min(left_only, right_only)
    tail_count = sum(comb(discordant, k) for k in range(lower + 1))
    return min(1.0, (2 * tail_count) / (1 << discordant))


def _validate_pair_counts(counts: tuple[int, ...]) -> None:
    if not isinstance(counts, tuple) or len(counts) != 4 or any(
        type(count) is not int or count < 0 for count in counts
    ):
        raise ValueError("expected four nonnegative integer pair counts")

def _binomial_lower_bound(count: int, size: int, tail: Fraction) -> float:
    if count == 0:
        return 0.0
    weights = [comb(size, k) for k in range(count, size + 1)]
    low, high = 0.0, 1.0
    while True:
        midpoint = (low + high) / 2
        if midpoint == low or midpoint == high:
            return low
        a, b = midpoint.as_integer_ratio()
        numerator = sum(
            weight * a**k * (b - a)**(size - k)
            for k, weight in enumerate(weights, start=count)
        )
        if numerator * tail.denominator >= tail.numerator * b**size:
            high = midpoint
        else:
            low = midpoint

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
    *,
    contexts: Iterable[TaskContext],
) -> Fitness:
    """Validate real receipts with the contract before counting their results.

    Supply the external task registry as contexts. It must contain one context
    per task and must be prepared independently of the receipts.
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
