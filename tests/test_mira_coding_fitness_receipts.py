"""Receipt aggregation and McNemar tests for coding fitness.

Split from tests/test_mira_coding_fitness.py so each file stays below the
40,000-character limit of a targeted code step. Same assertions, unchanged.
"""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from genesis.mira_coding_fitness import (
    _aggregate_attested_receipts,
    _count_attested_mcnemar_pairs,
    Counts,
    TaskContext,
    aggregate_receipts,
    aggregate_synthetic_receipts,
    count_mcnemar_pairs,
    count_synthetic_mcnemar_pairs,
    mcnemar_exact_pvalue,
)
from genesis.mira_policy_contract import BankExternalReceipt, CodingPolicy


@pytest.mark.parametrize(
    "left_only,right_only,expected",
    [
        (0, 0, 1.0),
        (3, 3, 1.0),
        (0, 5, 0.0625),
        (5, 0, 0.0625),
        (1, 5, 0.21875),
    ],
)
def test_mcnemar_exact_pvalue(left_only, right_only, expected):
    assert mcnemar_exact_pvalue(left_only, right_only) == expected

@pytest.mark.parametrize("left_only,right_only", [(-1, 0), (0, -1)])
def test_mcnemar_exact_pvalue_rejects_negative_counts(left_only, right_only):
    with pytest.raises(ValueError):
        mcnemar_exact_pvalue(left_only, right_only)

@pytest.mark.parametrize(
    "left_only,right_only",
    [
        (True, 0),
        (False, 0),
        (1.0, 0),
        (0, True),
        (0, False),
        (0, 1.0),
    ],
)
def test_mcnemar_exact_pvalue_rejects_non_integer_counts(left_only, right_only):
    with pytest.raises(ValueError):
        mcnemar_exact_pvalue(left_only, right_only)

@pytest.fixture(params=["objects", "envelopes"])
def real_receipts(request):
    policy = CodingPolicy.create(
        localization="task-context",
        tool_order=["inspect", "edit", "test"],
        trial_and_repair_strategy="At most 10 trials with repair",
        task_budget={
            "models": ["offline-test-model", "another-offline-test-model"],
            "tokens": 1000,
            "proposals": 10,
            "time_seconds": 60,
        },
    )
    budget = {
        "models": ["offline-test-model"],
        "tokens": 100,
        "proposals": 1,
        "time_seconds": 2,
    }
    contexts = [
        TaskContext(
            task_id,
            language,
            judge,
            "a" * 64,
            deepcopy(budget),
            policy,
        )
        for task_id, language, judge in [
            ("a", "python", "judge-a"),
            ("b", "rust", "judge-b"),
            ("c", "python", "judge-a"),
        ]
    ]

    def make_receipt(context, result, **changes):
        fields = {
            "policy_sha256": context.policy.sha256,
            "bank_sha256": context.bank_fingerprint,
            "task_id": context.task_id,
            "judge_id": context.judge,
            "consumed_budget": deepcopy(context.consumed_budget),
            "declared_result": result,
        }
        fields.update(changes)
        receipt = BankExternalReceipt.create(**fields)
        return receipt.to_dict() if request.param == "envelopes" else receipt

    receipts = [
        make_receipt(context, result)
        for context, result in zip(contexts, (True, True, False))
    ]
    return receipts, contexts, make_receipt


def attestation_key(run_id, context):
    return (
        run_id, context.judge, context.bank_fingerprint, context.policy.sha256,
        context.task_id,
    )

def expected_attestations(contexts, verdicts=None, *, run_id="left"):
    if verdicts is None:
        verdicts = {"a": True, "b": True, "c": False}
    attestations = {}
    for context in contexts:
        key = attestation_key(run_id, context)
        attestations[key] = BankExternalReceipt.create(
            policy_sha256=context.policy.sha256,
            bank_sha256=context.bank_fingerprint,
            task_id=context.task_id,
            judge_id=context.judge,
            consumed_budget=deepcopy(context.consumed_budget),
            declared_result=verdicts[context.task_id],
        ).envelope.sha256
    return attestations


def aggregate_attested(receipts, *, contexts, attestations, run_id="left"):
    return _aggregate_attested_receipts(
        receipts, contexts=contexts, attestations=attestations, run_id=run_id
    )

def count_attested(
    *arms, attestations, left_run_id="left", right_run_id="right"
):
    return _count_attested_mcnemar_pairs(
        *arms, attestations=attestations, left_run_id=left_run_id,
        right_run_id=right_run_id,
    )

def assert_real_refusal_without_mutation(receipts, contexts):
    before = deepcopy((receipts, contexts))
    with pytest.raises(ValueError):
        aggregate_attested(
            receipts, contexts=contexts, attestations=expected_attestations(contexts)
        )
    assert (receipts, contexts) == before

def test_real_requires_external_context_registry(real_receipts):
    receipts, _, _ = real_receipts
    with pytest.raises(TypeError, match="contexts"):
        aggregate_receipts(receipts)

def test_real_rejects_positional_contexts(real_receipts):
    receipts, contexts, _ = real_receipts
    with pytest.raises(TypeError, match="positional"):
        aggregate_receipts(receipts, contexts)

def test_real_rejects_missing_task_context(real_receipts):
    receipts, contexts, _ = real_receipts
    with pytest.raises(ValueError, match="missing or additional tasks"):
        aggregate_attested(
            receipts, contexts=contexts[:-1], attestations=expected_attestations(contexts)
        )

def test_real_exact_counts_and_all_permutations(real_receipts):
    receipts, contexts, _ = real_receipts
    before = deepcopy((receipts, contexts))
    attestations = expected_attestations(contexts)
    expected = aggregate_attested(
        receipts, contexts=contexts, attestations=attestations
    )
    assert expected.overall == Counts(2, 3)
    assert expected.by_language == {
        "python": Counts(1, 2),
        "rust": Counts(1, 1),
    }
    for receipt_order in permutations(receipts):
        for context_order in permutations(contexts):
            assert aggregate_attested(
                receipt_order, contexts=context_order, attestations=attestations
            ) == expected
    assert (receipts, contexts) == before

@pytest.mark.parametrize("side", ["receipts", "contexts"])
def test_real_duplicates_rejected(real_receipts, side):
    receipts, contexts, _ = real_receipts
    if side == "receipts":
        receipts.append(deepcopy(receipts[0]))
    else:
        contexts.append(deepcopy(contexts[0]))
    assert_real_refusal_without_mutation(receipts, contexts)

@pytest.mark.parametrize("change", ["missing", "additional"])
def test_real_task_set_mismatch(real_receipts, change):
    receipts, contexts, make_receipt = real_receipts
    if change == "missing":
        receipts.pop()
    else:
        receipts.append(make_receipt(contexts[0], True, task_id="extra"))
    assert_real_refusal_without_mutation(receipts, contexts)

@pytest.mark.parametrize(
    "field,value",
    [
        ("bank_sha256", "b" * 64),
        ("judge_id", "different-judge"),
    ],
)
def test_real_context_divergences(real_receipts, field, value):
    receipts, contexts, make_receipt = real_receipts
    receipts[0] = make_receipt(contexts[0], True, **{field: value})
    assert_real_refusal_without_mutation(receipts, contexts)

def test_real_language_attribution_comes_from_external_contexts(real_receipts):
    receipts, contexts, _ = real_receipts
    before = deepcopy((receipts, contexts))
    attestations = expected_attestations(contexts)
    original = aggregate_attested(
        receipts, contexts=contexts, attestations=attestations
    )
    assert original.overall == Counts(2, 3)
    assert original.by_language == {
        "python": Counts(1, 2),
        "rust": Counts(1, 1),
    }
    changed_contexts = [
        replace(context, language="rust" if context.task_id == "a" else context.language)
        for context in contexts
    ]
    changed_before = deepcopy(changed_contexts)
    changed = aggregate_attested(
        receipts, contexts=changed_contexts, attestations=attestations
    )
    assert changed.overall == Counts(2, 3)
    assert changed.by_language == {
        "python": Counts(0, 1),
        "rust": Counts(2, 2),
    }
    assert (receipts, contexts) == before
    assert changed_contexts == changed_before

def test_real_policy_divergence(real_receipts):
    receipts, contexts, make_receipt = real_receipts
    receipts[0] = make_receipt(
        contexts[0],
        True,
        policy_sha256="b" * 64 if contexts[0].policy.sha256 != "b" * 64 else "c" * 64,
    )
    assert_real_refusal_without_mutation(receipts, contexts)

@pytest.mark.parametrize(
    "component", ["models", "tokens", "proposals", "time_seconds"]
)
def test_real_budget_component_divergences(real_receipts, component):
    receipts, contexts, make_receipt = real_receipts
    budget = deepcopy(contexts[0].consumed_budget)
    if component == "models":
        budget[component] = ["different-offline-model"]
    else:
        budget[component] += 1
    receipts[0] = make_receipt(contexts[0], True, consumed_budget=budget)
    assert_real_refusal_without_mutation(receipts, contexts)

@pytest.mark.parametrize("value", [0, 1, None, "true", [], {}])
def test_real_non_boolean_results_rejected(real_receipts, value):
    receipts, contexts, make_receipt = real_receipts
    receipts[0] = make_receipt(contexts[0], value)
    before = deepcopy((receipts, contexts))
    with pytest.raises(ValueError, match="^declared_result must have exact bool type$"):
        aggregate_attested(
            receipts, contexts=contexts, attestations=expected_attestations(contexts)
        )
    assert (receipts, contexts) == before

@pytest.mark.parametrize(
    "field,value",
    [
        ("declared_result", False),
        ("bank_sha256", "b" * 64),
        ("judge_id", "tampered-judge"),
    ],
)
def test_real_tampered_envelopes_rejected(real_receipts, field, value):
    receipts, contexts, _ = real_receipts
    envelope = (
        deepcopy(receipts[0])
        if isinstance(receipts[0], dict)
        else receipts[0].to_dict()
    )
    envelope["envelope"]["payload"][field] = value
    receipts[0] = envelope
    assert_real_refusal_without_mutation(receipts, contexts)

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
    return aggregate_synthetic_receipts(
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
    baseline = deepcopy(receipts)
    receipts[0][field] = value
    with pytest.raises(ValueError):
        aggregate(receipts, contexts)
    with pytest.raises(ValueError):
        count_synthetic_mcnemar_pairs(
            baseline, contexts, receipts, contexts,
            validate_task_receipt_consistency=synthetic_validator,
        )

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

def test_real_verification_rejects_synthetic_policy(synthetic):
    receipts, contexts = synthetic
    before = deepcopy(synthetic)
    with pytest.raises(TypeError):
        aggregate_attested(receipts, contexts=contexts, attestations={})
    assert synthetic == before

def test_real_entry_rejects_caller_validator(synthetic):
    receipts, contexts = synthetic
    with pytest.raises(TypeError, match="validate_task_receipt_consistency"):
        aggregate_receipts(
            receipts,
            contexts=contexts,
            validate_task_receipt_consistency=synthetic_validator,
        )

def test_real_mcnemar_rejects_caller_validator(real_receipts):
    receipts, contexts, _ = real_receipts
    with pytest.raises(TypeError, match="validate_task_receipt_consistency"):
        count_mcnemar_pairs(
            receipts, contexts, receipts, contexts,
            validate_task_receipt_consistency=synthetic_validator,
        )


def test_production_refuses_counting_without_independent_source(real_receipts):
    receipts, contexts, _ = real_receipts
    message = "^authenticated independent receipt attestation source required$"
    with pytest.raises(ValueError, match=message):
        aggregate_receipts(receipts, contexts=contexts)
    with pytest.raises(ValueError, match=message):
        count_mcnemar_pairs(receipts, contexts, receipts, contexts)

def test_production_rejects_fingerprints_recomputed_from_receipts(real_receipts):
    receipts, contexts, _ = real_receipts
    attestations = {}
    for context, receipt in zip(contexts, receipts):
        if isinstance(receipt, dict):
            receipt = BankExternalReceipt.from_dict(receipt)
        for run_id in ("left", "right"):
            attestations[attestation_key(run_id, context)] = receipt.envelope.sha256

    message = "unexpected keyword argument 'attestations'"
    with pytest.raises(TypeError, match=message):
        aggregate_receipts(receipts, contexts=contexts, attestations=attestations)
    with pytest.raises(TypeError, match=message):
        count_mcnemar_pairs(
            receipts, contexts, receipts, contexts, attestations=attestations
        )

@pytest.mark.parametrize("arm", ["left", "right"])
def test_real_mcnemar_rejects_mixed_policies(real_receipts, arm):
    receipts, contexts, make_receipt = real_receipts
    other_policy = CodingPolicy.create(
        **dict(contexts[0].policy.payload, localization="mixed-task-context")
    )
    assert other_policy.sha256 != contexts[0].policy.sha256
    mixed_contexts = [replace(contexts[0], policy=other_policy), *contexts[1:]]
    mixed_receipts = [make_receipt(mixed_contexts[0], True), *receipts[1:]]

    attestations = (
        expected_attestations(contexts, run_id="right" if arm == "left" else "left")
        | expected_attestations(mixed_contexts, run_id=arm)
    )
    assert aggregate_attested(
        mixed_receipts, contexts=mixed_contexts, attestations=attestations, run_id=arm
    ) == aggregate_attested(
        receipts, contexts=contexts, attestations=attestations,
        run_id="right" if arm == "left" else "left",
    )
    paired = (
        (mixed_receipts, mixed_contexts, receipts, contexts)
        if arm == "left"
        else (receipts, contexts, mixed_receipts, mixed_contexts)
    )
    before = deepcopy(paired)
    with pytest.raises(ValueError, match=f"{arm} arm.*policy fingerprint"):
        count_attested(*paired, attestations=attestations)
    assert paired == before

@pytest.mark.parametrize("same_policy", [False, True])
def test_real_mcnemar_counts_with_distinct_executions(real_receipts, same_policy):
    receipts, contexts, make_receipt = real_receipts
    other_policy = contexts[0].policy
    if not same_policy:
        other_policy = CodingPolicy.create(
            **dict(contexts[0].policy.payload, localization="paired-task-context")
        )
        assert other_policy.sha256 != contexts[0].policy.sha256
    left_contexts = [
        contexts[0],
        contexts[1],
        contexts[2],
        replace(contexts[2], task_id="d"),
        replace(contexts[1], task_id="e"),
    ]
    right_contexts = [replace(context, policy=other_policy) for context in left_contexts]
    left = receipts + [
        make_receipt(left_contexts[3], False),
        make_receipt(left_contexts[4], False),
    ]
    right = [
        make_receipt(context, result)
        for context, result in zip(right_contexts, (True, False, True, True, False))
    ]
    attestations = expected_attestations(
        left_contexts, {"a": True, "b": True, "c": False, "d": False, "e": False}
    ) | expected_attestations(
        right_contexts, {"a": True, "b": False, "c": True, "d": True, "e": False},
        run_id="right",
    )
    before = deepcopy((left, left_contexts, right, right_contexts))
    counts = count_attested(
        left, reversed(left_contexts), reversed(right), right_contexts,
        attestations=attestations,
    )
    assert counts.overall == (1, 1, 2, 1)
    assert counts.by_language == {
        "python": (1, 0, 2, 0),
        "rust": (0, 1, 0, 1),
    }
    assert counts.success_rate_difference_by_language == {
        "python": -2 / 3,
        "rust": 1 / 2,
    }
    swapped = count_attested(
        right, right_contexts, left, left_contexts, attestations=attestations,
        left_run_id="right", right_run_id="left",
    )
    assert swapped.success_rate_difference_by_language == {
        "python": 2 / 3,
        "rust": -1 / 2,
    }
    assert (left, left_contexts, right, right_contexts) == before


def test_real_mcnemar_success_rate_difference_with_equal_discordant_counts(real_receipts):
    left, contexts, make_receipt = real_receipts
    right_policy = CodingPolicy.create(
        **dict(contexts[0].policy.payload, localization="equal-discordance")
    )
    right_contexts = [replace(context, policy=right_policy) for context in contexts]
    right = [
        make_receipt(context, result)
        for context, result in zip(right_contexts, (False, True, True))
    ]
    attestations = expected_attestations(contexts) | expected_attestations(
        right_contexts, {"a": False, "b": True, "c": True}, run_id="right"
    )
    counts = count_attested(
        left, contexts, right, right_contexts, attestations=attestations
    )
    assert counts.by_language["python"] == (0, 1, 1, 0)
    assert counts.success_rate_difference_by_language == {"python": 0.0, "rust": 0.0}

@pytest.mark.parametrize(
    "component,value",
    [
        ("models", ["offline-test-model", "another-offline-test-model", "third-offline-test-model"]),
        ("tokens", 1001),
        ("proposals", 11),
        ("time_seconds", 61),
    ],
)
def test_real_mcnemar_rejects_allocated_budget_divergences(
    real_receipts, component, value
):
    receipts, contexts, make_receipt = real_receipts
    payload = contexts[0].policy.payload
    budget = dict(payload["task_budget"], **{component: value})
    other_policy = CodingPolicy.create(**dict(payload, task_budget=budget))
    right_contexts = [replace(context, policy=other_policy) for context in contexts]
    right_receipts = [
        make_receipt(context, result)
        for context, result in zip(right_contexts, (True, True, False))
    ]

    attestations = expected_attestations(contexts) | expected_attestations(
        right_contexts, run_id="right"
    )
    assert aggregate_attested(
        right_receipts, contexts=right_contexts, attestations=attestations,
        run_id="right",
    ).overall == Counts(2, 3)
    with pytest.raises(ValueError, match=f"^paired allocated task_budget {component} mismatch$"):
        count_attested(
            receipts, contexts, right_receipts, right_contexts,
            attestations=attestations,
        )

@pytest.mark.parametrize(
    "field,value",
    [
        ("bank_fingerprint", "b" * 64),
        ("judge", "different-judge"),
        ("language", "rust"),
        ("consumed_budget", {"models": ["another-offline-test-model"]}),
        ("consumed_budget", {"tokens": 101}),
        ("consumed_budget", {"proposals": 2}),
        ("consumed_budget", {"time_seconds": 3}),
    ],
)
def test_real_mcnemar_rejects_external_context_divergences(real_receipts, field, value):
    receipts, contexts, make_receipt = real_receipts
    if field == "consumed_budget":
        value = dict(contexts[0].consumed_budget, **value)
    other_policy = CodingPolicy.create(
        **dict(contexts[0].policy.payload, localization="context-divergence")
    )
    changed = [replace(context, policy=other_policy) for context in contexts]
    if field == "bank_fingerprint":
        changed = [replace(context, bank_fingerprint=value) for context in changed]
    else:
        changed[0] = replace(changed[0], **{field: value})
    right = [
        make_receipt(context, result)
        for context, result in zip(changed, (True, True, False))
    ]

    attestations = expected_attestations(contexts) | expected_attestations(
        changed, run_id="right"
    )
    assert aggregate_attested(
        right, contexts=changed, attestations=attestations, run_id="right"
    ).overall == Counts(2, 3)
    with pytest.raises(ValueError, match=f"paired {field} mismatch"):
        count_attested(
            receipts, contexts, right, changed,
            attestations=attestations,
        )


@pytest.mark.parametrize("arm", ["left", "right"])
@pytest.mark.parametrize("failure", ["missing", "flipped", "other_execution"])
def test_real_aggregation_and_mcnemar_require_attested_verdicts(
    real_receipts, arm, failure
):
    receipts, contexts, make_receipt = real_receipts
    left = list(receipts)
    right = [make_receipt(contexts[0], False), *receipts[1:]]
    submitted, original_verdict = (left, True) if arm == "left" else (right, False)
    attestations = expected_attestations(contexts) | expected_attestations(
        contexts, {"a": False, "b": True, "c": False}, run_id="right"
    )
    key = attestation_key(arm, contexts[0])
    if failure == "missing":
        del attestations[key]
        message = "receipt attestation coverage mismatch"
    elif failure == "flipped":
        submitted[0] = make_receipt(contexts[0], not original_verdict)
        message = "receipt attestation fingerprint mismatch"
    else:
        other_arm = "right" if arm == "left" else "left"
        attestations[key] = attestations[attestation_key(other_arm, contexts[0])]
        message = "receipt attestation fingerprint mismatch"

    with pytest.raises(ValueError, match=message):
        aggregate_attested(
            submitted, contexts=contexts, attestations=attestations, run_id=arm
        )
    with pytest.raises(ValueError, match=message):
        count_attested(left, contexts, right, contexts, attestations=attestations)

def test_real_rejects_omitting_registered_failed_task(real_receipts):
    receipts, contexts, _ = real_receipts
    attestations = expected_attestations(contexts) | expected_attestations(
        contexts, run_id="right"
    )
    fitness = aggregate_attested(
        receipts, contexts=contexts, attestations=attestations
    )
    assert fitness.overall == Counts(2, 3)
    assert fitness.by_language == {"python": Counts(1, 2), "rust": Counts(1, 1)}

    full = (receipts, contexts)
    counts = count_attested(*full, *full, attestations=attestations)
    assert counts.overall == (2, 0, 0, 1)
    assert counts.by_language == {"python": (1, 0, 0, 1), "rust": (1, 0, 0, 0)}

    assert contexts[-1].task_id == "c"
    truncated = (receipts[:-1], contexts[:-1])
    message = "receipt attestation coverage mismatch"
    for run_id in ("left", "right"):
        with pytest.raises(ValueError, match=message):
            aggregate_attested(
                truncated[0], contexts=truncated[1], attestations=attestations,
                run_id=run_id,
            )
    for left, right in ((truncated, full), (full, truncated), (truncated, truncated)):
        with pytest.raises(ValueError, match=message):
            count_attested(*left, *right, attestations=attestations)

def test_real_mcnemar_requires_distinct_execution_ids(real_receipts):
    receipts, contexts, _ = real_receipts
    with pytest.raises(ValueError, match="paired execution identifiers must differ"):
        count_attested(
            receipts, contexts, receipts, contexts,
            attestations=expected_attestations(contexts), right_run_id="left",
        )

def test_synthetic_validator_refusal_propagates(synthetic):
    def refusing_validator(receipt, context):
        raise RuntimeError("synthetic refusal")

    with pytest.raises(RuntimeError, match="synthetic refusal"):
        aggregate(*synthetic, validator=refusing_validator)
