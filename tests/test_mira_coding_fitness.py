"""Boundary and factory-based tests for coding receipt aggregation.

Real receipts use the policy contract factories and contractual validator.
Language attribution comes from external task contexts.

Negative evidence reference: e7b532ca80d94a168cf7b09eb34669aa.
Previous failed run reference: 8ae05181d4e64d39b80f2a900bcfb70c.
No corrected execution result or capability gain is attested.
"""

from copy import deepcopy
from dataclasses import replace
from itertools import permutations
from math import isfinite, sqrt, ulp

import pytest

from genesis.mira_coding_fitness import (
    Counts,
    LanguageNonInferiority,
    McNemarPairs,
    TaskContext,
    aggregate_receipts,
    aggregate_synthetic_receipts,
    assess_paired_non_inferiority,
    count_mcnemar_pairs,
    count_synthetic_mcnemar_pairs,
    mcnemar_exact_pvalue,
    resolve_ablation_parent,
)
from genesis.mira_policy_contract import BankExternalReceipt, CodingPolicy, JsonObjectEnvelope


@pytest.mark.parametrize("extra", [{}, {"rust": (0, 0, 0, 0)}])
def test_non_inferiority_requires_evaluable_languages(extra):
    pairs = McNemarPairs((0, 10, 0, 0), {"python": (0, 10, 0, 0), **extra})
    passed, results = assess_paired_non_inferiority(
        pairs, ["python", "rust"], delta=0.10, alpha=0.05
    )
    assert not passed
    assert results["python"].passes(0.10)
    assert results["rust"] is None

@pytest.mark.parametrize("delta", [0.10, 0.975])
def test_non_inferiority_one_concordant_pair(delta):
    pairs = McNemarPairs((1, 0, 0, 0), {"python": (1, 0, 0, 0)})
    passed, results = assess_paired_non_inferiority(
        pairs, ["python"], delta=delta, alpha=0.05
    )
    assert not passed
    assert results["python"].difference == 0
    assert results["python"].lower_bound == pytest.approx(-0.975)

def test_non_inferiority_rejects_bound_equal_to_negative_margin():
    assert not LanguageNonInferiority(0.0, -0.975).passes(0.975)

def test_non_inferiority_with_subnormal_alpha():
    counts = (1, 1, 0, 0)
    pairs = McNemarPairs(counts, {"python": counts})
    passed, results = assess_paired_non_inferiority(
        pairs, ["python"], delta=0.10, alpha=1e-320
    )
    result = results["python"]
    assert not passed
    assert result is not None
    assert isfinite(result.lower_bound)
    assert not result.passes(0.10)

def test_non_inferiority_rejects_inconsistent_overall_counts():
    pairs = McNemarPairs((0, 0, 1, 0), {"python": (0, 10, 0, 0)})
    with pytest.raises(ValueError, match="overall pair counts"):
        assess_paired_non_inferiority(pairs, ["python"], delta=0.10, alpha=0.05)

def test_non_inferiority_bound_with_one_favorable_pair_out_of_two():
    counts = (1, 1, 0, 0)
    pairs = McNemarPairs(counts, {"python": counts})
    _, results = assess_paired_non_inferiority(
        pairs, ["python"], delta=0.10, alpha=0.05
    )
    result = results["python"]
    assert result is not None
    assert result.lower_bound == pytest.approx(sqrt(0.025) - sqrt(0.975))

def test_non_inferiority_preserves_half_tail_at_smallest_positive_alpha():
    counts = (0, 32, 0, 0)
    pairs = McNemarPairs(counts, {"python": counts})
    _, results = assess_paired_non_inferiority(
        pairs, ["python"], delta=0.10, alpha=2**-1074
    )
    result = results["python"]
    assert result is not None
    assert result.lower_bound > -1.0
    assert result.lower_bound == pytest.approx(
        2 * 2**(-1075 / 32) - 1, rel=0, abs=ulp(-1.0)
    )

@pytest.mark.parametrize("size,expected", [(21, False), (22, True)])
def test_non_inferiority_with_all_favorable_pairs_near_margin(size, expected):
    delta = 0.5
    counts = (0, size, 0, 0)
    pairs = McNemarPairs(counts, {"python": counts})
    passed, results = assess_paired_non_inferiority(
        pairs, ["python"], delta=delta, alpha=2**-41
    )
    result = results["python"]
    assert result is not None
    assert result.passes(delta) is expected
    assert passed is expected

@pytest.mark.parametrize("rust_count,expected", [(1, False), (10, True)])
def test_non_inferiority_requires_every_language_to_pass(rust_count, expected):
    pairs = McNemarPairs(
        (rust_count, 10, 0, 0),
        {"python": (0, 10, 0, 0), "rust": (rust_count, 0, 0, 0)},
    )
    passed, results = assess_paired_non_inferiority(
        pairs, ["python", "rust"], delta=0.40, alpha=0.05
    )
    assert results["python"].passes(0.40)
    assert results["rust"].passes(0.40) is expected
    assert passed is expected

@pytest.mark.parametrize(
    "languages,delta,alpha",
    [
        ([], 0.10, 0.05),
        ([""], 0.10, 0.05),
        (["python", "python"], 0.10, 0.05),
        ("python", 0.10, 0.05),
        (["python"], 0, 0.05),
        (["python"], float("nan"), 0.05),
        (["python"], 0.10, 1),
        (["python"], 0.10, True),
    ],
)
def test_non_inferiority_rejects_invalid_parameters(languages, delta, alpha):
    pairs = McNemarPairs((1, 0, 0, 0), {"python": (1, 0, 0, 0)})
    with pytest.raises(ValueError):
        assess_paired_non_inferiority(pairs, languages, delta=delta, alpha=alpha)

@pytest.mark.parametrize("counts", [(1, 0, 0), (1, -1, 0, 0), (1, True, 0, 0)])
def test_non_inferiority_rejects_invalid_counts(counts):
    pairs = McNemarPairs((1, 0, 0, 0), {"python": counts})
    with pytest.raises(ValueError):
        assess_paired_non_inferiority(pairs, ["python"], delta=0.10, alpha=0.05)

@pytest.fixture
def ablation_policies():
    parent = CodingPolicy.create(
        localization="task-context",
        tool_order=["inspect", "edit", "test"],
        trial_and_repair_strategy="At most 10 trials with repair",
        task_budget={
            "models": ["offline-test-model"],
            "tokens": 1000,
            "proposals": 10,
            "time_seconds": 60,
        },
    )
    child = CodingPolicy.create(
        **dict(parent.payload, localization="child-task-context")
    )
    return child, parent

def test_resolve_ablation_parent_returns_expected_policy(ablation_policies):
    child, parent = ablation_policies
    grandparent = CodingPolicy.create(
        **dict(parent.payload, localization="grandparent-task-context")
    )
    resolved = resolve_ablation_parent(
        child,
        {child.sha256: parent.sha256, parent.sha256: grandparent.sha256},
        {grandparent.sha256: grandparent, parent.sha256: parent},
    )
    assert resolved.to_dict() == parent.to_dict()

def test_resolve_ablation_parent_rejects_child_subclass_with_registered_serialization(
    ablation_policies,
):
    child, parent = ablation_policies
    other_parent = CodingPolicy.create(
        **dict(parent.payload, localization="other-parent-task-context")
    )
    other_child = CodingPolicy.create(
        **dict(child.payload, localization="other-child-task-context")
    )

    class RedirectingChild(CodingPolicy):
        @property
        def sha256(self):
            return child.sha256

        def to_dict(self):
            return other_child.to_dict()

    derived_child = object.__new__(RedirectingChild)
    lineage = {
        child.sha256: parent.sha256,
        other_child.sha256: other_parent.sha256,
    }
    policies = {
        policy.sha256: policy for policy in (child, parent, other_child, other_parent)
    }
    with pytest.raises(TypeError, match="^expected child CodingPolicy$"):
        resolve_ablation_parent(derived_child, lineage, policies)

def test_resolve_ablation_parent_rejects_parent_subclass(ablation_policies):
    child, parent = ablation_policies

    class DerivedParent(CodingPolicy):
        def to_dict(self):
            return parent.to_dict()

    derived_parent = object.__new__(DerivedParent)
    with pytest.raises(TypeError, match="^expected parent CodingPolicy$"):
        resolve_ablation_parent(
            child, {child.sha256: parent.sha256}, {parent.sha256: derived_parent}
        )

def test_resolve_ablation_parent_rejects_missing_lineage(ablation_policies):
    child, parent = ablation_policies
    with pytest.raises(ValueError, match="^missing ablation lineage$"):
        resolve_ablation_parent(child, {}, {parent.sha256: parent})

def test_resolve_ablation_parent_rejects_unknown_parent(ablation_policies):
    child, parent = ablation_policies
    with pytest.raises(ValueError, match="^ablation parent policy not found$"):
        resolve_ablation_parent(child, {child.sha256: parent.sha256}, {})

def test_resolve_ablation_parent_rejects_fingerprint_mismatch(ablation_policies):
    child, parent = ablation_policies
    with pytest.raises(ValueError, match="^ablation parent fingerprint mismatch$"):
        resolve_ablation_parent(
            child, {child.sha256: parent.sha256}, {parent.sha256: child}
        )

def test_resolve_ablation_parent_rejects_self_parent(ablation_policies):
    child, _ = ablation_policies
    with pytest.raises(ValueError, match="^ablation parent must differ from child$"):
        resolve_ablation_parent(
            child, {child.sha256: child.sha256}, {child.sha256: child}
        )

@pytest.mark.parametrize("side", ["child", "parent"])
@pytest.mark.parametrize("version_layer", ["policy", "envelope"])
def test_resolve_ablation_parent_rejects_invalid_versions(
    ablation_policies, side, version_layer
):
    child, parent = ablation_policies
    lineage = {child.sha256: parent.sha256}
    policies = {parent.sha256: parent}
    policy = child if side == "child" else parent
    layer = policy.envelope if version_layer == "envelope" else policy
    object.__setattr__(layer, "version", "unsupported-test-version")
    with pytest.raises(ValueError):
        resolve_ablation_parent(child, lineage, policies)

def test_resolve_ablation_parent_rejects_child_fingerprint_mismatch(
    ablation_policies,
):
    child, parent = ablation_policies
    lineage = {child.sha256: parent.sha256}
    object.__setattr__(child.envelope, "sha256", parent.sha256)
    with pytest.raises(ValueError, match=r"\AInconsistent SHA-256 digest\Z"):
        resolve_ablation_parent(child, lineage, {parent.sha256: parent})

@pytest.mark.parametrize("side", ["child", "parent"])
def test_resolve_ablation_parent_rejects_redirecting_envelope(ablation_policies, side):
    child, parent = ablation_policies
    original = child if side == "child" else parent
    other = CodingPolicy.create(
        **dict(original.payload, localization="other-task-context")
    )
    lineage = {child.sha256: parent.sha256}
    policies = {policy.sha256: policy for policy in (child, parent, other)}
    if side == "child":
        lineage[other.sha256] = parent.sha256
    else:
        lineage[child.sha256] = other.sha256

    assert resolve_ablation_parent(child, lineage, policies) == policies[
        lineage[child.sha256]
    ]

    class RedirectingEnvelope(JsonObjectEnvelope):
        def to_dict(self):
            return other.envelope.to_dict()

    envelope = original.envelope
    replacement = RedirectingEnvelope(
        version=envelope.version,
        canonical_utf8=envelope.canonical_utf8,
        sha256=envelope.sha256,
    )
    object.__setattr__(original, "envelope", replacement)
    assert original.to_dict() == other.to_dict()

    class UnreadableLineage(dict):
        def get(self, key, default=None):
            pytest.fail("looked up lineage before rejecting the child envelope")

    if side == "child":
        lineage = UnreadableLineage(lineage)
    else:
        policies[other.sha256] = original
    with pytest.raises(TypeError, match=rf"\Aexpected {side} JsonObjectEnvelope\Z"):
        resolve_ablation_parent(child, lineage, policies)

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

def test_ablation_receipts_follow_resolved_parent_policy(
    ablation_policies, real_receipts
):
    child, parent = ablation_policies
    _, contexts, make_receipt = real_receipts
    resolved_parent = resolve_ablation_parent(
        child, {child.sha256: parent.sha256}, {parent.sha256: parent}
    )
    context = replace(contexts[0], policy=resolved_parent)
    parent_receipt = make_receipt(context, True, policy_sha256=parent.sha256)
    counts = aggregate_receipts([parent_receipt], [context])
    assert counts.overall == Counts(1, 1)
    assert counts.by_language == {context.language: Counts(1, 1)}

    child_receipt = make_receipt(context, True, policy_sha256=child.sha256)
    with pytest.raises(ValueError, match=r"(?i)\bpolicy\b|policy_sha256"):
        aggregate_receipts([child_receipt], [context])

def test_mcnemar_pairs_follow_resolved_parent_policy(
    ablation_policies, real_receipts
):
    child, parent = ablation_policies
    _, contexts, make_receipt = real_receipts
    resolved_parent = resolve_ablation_parent(
        child, {child.sha256: parent.sha256}, {parent.sha256: parent}
    )
    child_context = replace(contexts[0], policy=child)
    parent_context = replace(contexts[0], policy=resolved_parent)
    child_receipt = make_receipt(child_context, True)
    parent_receipt = make_receipt(parent_context, False)

    counts = count_mcnemar_pairs(
        [child_receipt], [child_context], [parent_receipt], [parent_context]
    )
    assert counts.overall == (0, 1, 0, 0)
    assert counts.by_language == {child_context.language: (0, 1, 0, 0)}

    wrong_parent_receipt = make_receipt(
        parent_context, False, policy_sha256=child.sha256
    )
    with pytest.raises(ValueError, match=r"(?i)\bpolicy\b|policy_sha256"):
        count_mcnemar_pairs(
            [child_receipt], [child_context], [wrong_parent_receipt], [parent_context]
        )

def assert_real_refusal_without_mutation(receipts, contexts):
    before = deepcopy((receipts, contexts))
    with pytest.raises(ValueError):
        aggregate_receipts(receipts, contexts)
    assert (receipts, contexts) == before

def test_real_exact_counts_and_all_permutations(real_receipts):
    receipts, contexts, _ = real_receipts
    before = deepcopy((receipts, contexts))
    expected = aggregate_receipts(receipts, contexts)
    assert expected.overall == Counts(2, 3)
    assert expected.by_language == {
        "python": Counts(1, 2),
        "rust": Counts(1, 1),
    }
    for receipt_order in permutations(receipts):
        for context_order in permutations(contexts):
            assert aggregate_receipts(receipt_order, context_order) == expected
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
    if field == "bank_sha256":
        before = deepcopy((receipts, contexts))
        with pytest.raises(ValueError, match=r"\ABank differs from external context\Z"):
            aggregate_receipts(receipts, contexts)
        assert (receipts, contexts) == before
    else:
        assert_real_refusal_without_mutation(receipts, contexts)

def test_real_language_attribution_comes_from_external_contexts(real_receipts):
    receipts, contexts, _ = real_receipts
    before = deepcopy((receipts, contexts))
    original = aggregate_receipts(receipts, contexts)
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
    changed = aggregate_receipts(receipts, changed_contexts)
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
        aggregate_receipts(receipts, contexts)
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

def test_real_entry_rejects_synthetic_policy(synthetic):
    receipts, contexts = synthetic
    before = deepcopy(synthetic)
    with pytest.raises(TypeError):
        aggregate_receipts(receipts, contexts)
    assert synthetic == before

def test_real_entry_rejects_caller_validator(synthetic):
    receipts, contexts = synthetic
    with pytest.raises(TypeError):
        aggregate_receipts(
            receipts,
            contexts,
            validate_task_receipt_consistency=synthetic_validator,
        )

def test_real_mcnemar_rejects_caller_validator(real_receipts):
    receipts, contexts, _ = real_receipts
    with pytest.raises(TypeError, match="validate_task_receipt_consistency"):
        count_mcnemar_pairs(
            receipts, contexts, receipts, contexts,
            validate_task_receipt_consistency=synthetic_validator,
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

    assert aggregate_receipts(mixed_receipts, mixed_contexts) == aggregate_receipts(
        receipts, contexts
    )
    paired = (
        (mixed_receipts, mixed_contexts, receipts, contexts)
        if arm == "left"
        else (receipts, contexts, mixed_receipts, mixed_contexts)
    )
    before = deepcopy(paired)
    with pytest.raises(ValueError, match=f"{arm} arm.*policy fingerprint"):
        count_mcnemar_pairs(*paired)
    assert paired == before

def test_count_mcnemar_pairs_rejects_mixed_policies_within_arm(real_receipts):
    receipts, contexts, make_receipt = real_receipts
    right_receipts = receipts[:2]
    right_contexts = contexts[:2]
    payload = right_contexts[1].policy.payload
    budget = dict(payload["task_budget"], tokens=payload["task_budget"]["tokens"] + 1)
    other_policy = CodingPolicy.create(**dict(payload, task_budget=budget))
    left_contexts = [right_contexts[0], replace(right_contexts[1], policy=other_policy)]
    left_receipts = [right_receipts[0], make_receipt(left_contexts[1], True)]

    assert aggregate_receipts(left_receipts, left_contexts) == aggregate_receipts(right_receipts, right_contexts)
    with pytest.raises(ValueError, match="left arm.*policy fingerprint"):
        count_mcnemar_pairs(
            left_receipts, left_contexts, right_receipts, right_contexts
        )

def test_real_mcnemar_counts_with_distinct_policies(real_receipts):
    receipts, contexts, make_receipt = real_receipts
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
    before = deepcopy((left, left_contexts, right, right_contexts))
    counts = count_mcnemar_pairs(
        left, reversed(left_contexts), reversed(right), right_contexts,
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
    swapped = count_mcnemar_pairs(right, right_contexts, left, left_contexts)
    assert swapped.success_rate_difference_by_language == {
        "python": 2 / 3,
        "rust": -1 / 2,
    }
    assert (left, left_contexts, right, right_contexts) == before


def test_real_non_inferiority_rejects_observed_rust_regression(real_receipts):
    _, (python, rust, _), make_receipt = real_receipts
    candidate_policy = CodingPolicy.create(
        **dict(python.policy.payload, localization="candidate-task-context")
    )
    assert candidate_policy.sha256 != python.policy.sha256
    baseline_contexts = [
        replace(python, task_id=f"python-{i}") for i in range(10)
    ] + [rust]
    candidate_contexts = [
        replace(context, policy=candidate_policy) for context in baseline_contexts
    ]
    counts = count_mcnemar_pairs(
        [make_receipt(context, context.language == "python") for context in candidate_contexts],
        candidate_contexts,
        [make_receipt(context, context.language == "rust") for context in baseline_contexts],
        baseline_contexts,
    )
    assert counts.overall == (0, 10, 1, 0)
    assert counts.by_language == {"python": (0, 10, 0, 0), "rust": (0, 0, 1, 0)}
    _, candidate_only, baseline_only, _ = counts.overall
    assert (candidate_only - baseline_only) / sum(counts.overall) == pytest.approx(9 / 11)

    passed, results = assess_paired_non_inferiority(
        counts, ("python", "rust"), delta=0.40, alpha=0.05
    )
    assert results["python"].passes(0.40)
    assert results["rust"].difference == -1
    assert not passed


def test_real_mcnemar_rejects_rust_task_missing_from_candidate(real_receipts):
    baseline_receipts, baseline_contexts, _ = real_receipts
    candidate_receipts = [baseline_receipts[0], baseline_receipts[2]]
    candidate_contexts = [baseline_contexts[0], baseline_contexts[2]]

    candidate = aggregate_receipts(candidate_receipts, candidate_contexts)
    baseline = aggregate_receipts(baseline_receipts, baseline_contexts)
    assert candidate.overall == Counts(1, 2)
    assert candidate.by_language == {"python": Counts(1, 2)}
    assert baseline.overall == Counts(2, 3)
    assert baseline.by_language == {"python": Counts(1, 2), "rust": Counts(1, 1)}

    with pytest.raises(ValueError, match=r"\Apaired task sets differ\Z"):
        count_mcnemar_pairs(
            candidate_receipts, candidate_contexts, baseline_receipts, baseline_contexts
        )

def test_real_mcnemar_success_rate_difference_with_equal_discordant_counts(real_receipts):
    left, contexts, make_receipt = real_receipts
    right = [
        make_receipt(context, result)
        for context, result in zip(contexts, (False, True, True))
    ]
    counts = count_mcnemar_pairs(left, contexts, right, contexts)
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

    assert aggregate_receipts(right_receipts, right_contexts).overall == Counts(2, 3)
    with pytest.raises(ValueError, match=f"^paired allocated task_budget {component} mismatch$"):
        count_mcnemar_pairs(receipts, contexts, right_receipts, right_contexts)

@pytest.mark.parametrize(
    "field,value",
    [
        ("bank_fingerprint", "b" * 64),
        ("judge", "different-judge"),
        ("language", "rust"),
        ("task_id", "different-task"),
    ],
)
def test_real_mcnemar_rejects_external_context_divergences(real_receipts, field, value):
    receipts, contexts, make_receipt = real_receipts
    changed = [replace(contexts[0], **{field: value}), *contexts[1:]]
    right = [make_receipt(changed[0], True), *receipts[1:]]

    assert aggregate_receipts(right, changed).overall == Counts(2, 3)
    message = "paired task sets differ" if field == "task_id" else f"paired {field} mismatch"
    with pytest.raises(ValueError, match=message):
        count_mcnemar_pairs(receipts, contexts, right, changed)

@pytest.mark.parametrize(
    "changes",
    [
        {"models": ["another-offline-test-model"]},
        {"tokens": 101},
        {"proposals": 2},
        {"time_seconds": 3},
        {"tokens": 101, "proposals": 2, "time_seconds": 3},
    ],
)
def test_real_mcnemar_rejects_consumed_budget_divergences(real_receipts, changes):
    receipts, contexts, make_receipt = real_receipts
    budget = dict(contexts[0].consumed_budget, **changes)
    changed = [replace(contexts[0], consumed_budget=budget), *contexts[1:]]
    right = [make_receipt(changed[0], True), *receipts[1:]]

    assert aggregate_receipts(right, changed).overall == Counts(2, 3)
    with pytest.raises(ValueError, match="^paired consumed_budget mismatch for task a$"):
        count_mcnemar_pairs(receipts, contexts, right, changed)

    template = contexts[0]
    matched = [replace(template, task_id=f"matched-{i}") for i in range(20)]
    matched_receipts = [make_receipt(context, True) for context in matched]
    left_defeat = replace(template, task_id="defeat", consumed_budget=budget)
    right_win = replace(template, task_id="defeat")
    parameters = {"delta": 0.20, "alpha": 0.05}

    matched_counts = count_mcnemar_pairs(
        matched_receipts, matched, matched_receipts, matched
    )
    passed, _ = assess_paired_non_inferiority(
        matched_counts, ("python",), **parameters
    )
    assert passed

    with pytest.raises(ValueError, match="^paired consumed_budget mismatch for task defeat$"):
        assess_paired_non_inferiority(
            count_mcnemar_pairs(
                [*matched_receipts, make_receipt(left_defeat, False)],
                [*matched, left_defeat],
                [*matched_receipts, make_receipt(right_win, True)],
                [*matched, right_win],
            ),
            ("python",),
            **parameters,
        )

@pytest.mark.parametrize(
    "right_seconds,right_cap,expected",
    [
        (4, 10, McNemarPairs((1, 0, 0, 0), {"python": (1, 0, 0, 0)})),
        (7, 10, None),
        (4, 11, None),
    ],
)
def test_real_mcnemar_elapsed_time_under_cap(
    real_receipts, right_seconds, right_cap, expected
):
    _, contexts, make_receipt = real_receipts
    context = contexts[0]
    payload = context.policy.payload
    left_policy = CodingPolicy.create(
        **dict(payload, task_budget=dict(payload["task_budget"], time_seconds=10))
    )
    right_policy = CodingPolicy.create(
        **dict(payload, task_budget=dict(payload["task_budget"], time_seconds=right_cap))
    )
    left = replace(
        context, policy=left_policy, consumed_budget=dict(context.consumed_budget, time_seconds=4)
    )
    right = replace(
        context, policy=right_policy,
        consumed_budget=dict(context.consumed_budget, time_seconds=right_seconds),
    )
    args = ([make_receipt(left, True)], [left], [make_receipt(right, True)], [right])
    if expected is None:
        message = (
            "^paired allocated task_budget time_seconds mismatch$"
            if right_cap != 10
            else "^paired consumed_budget mismatch for task a$"
        )
        with pytest.raises(ValueError, match=message):
            count_mcnemar_pairs(*args)
    else:
        assert count_mcnemar_pairs(*args) == expected

def test_synthetic_validator_refusal_propagates(synthetic):
    def refusing_validator(receipt, context):
        raise RuntimeError("synthetic refusal")

    with pytest.raises(RuntimeError, match="synthetic refusal"):
        aggregate(*synthetic, validator=refusing_validator)
