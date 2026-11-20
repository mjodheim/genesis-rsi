"""Boundary and factory-based tests for coding receipt aggregation.

Real receipts use the policy contract factories and contractual validator.
Language attribution comes from external task contexts.

Negative evidence reference: e7b532ca80d94a168cf7b09eb34669aa.
Previous failed run reference: 8ae05181d4e64d39b80f2a900bcfb70c.
Evidence reference for step 4948: 04d5c7765f5848fe98bd3fc476a54606.
Evidence 00874e07781f4881a6ad62584478df61 recorded 153 passing fitness tests,
including the development bank test.
The last attested success applies to the commit before the Ed25519 test removal.
The development bank used original, public Python stdlib tasks and examples.
Review covered provenance, nominal and boundary cases, and fixture-only execution.
The delegated decision for these tasks was PUBLIC_AGPL_COMMERCIAL_OPTION.
Fixture scores were 12/20 and 15/20. Mira's coding ability remains unmeasured.
Fresh verification requires pytest exit code 0 for both targeted suites,
tests/test_mira_coding_fitness.py and tests/test_mira_coding_fitness_receipts.py,
in the offline container without network access or model use. Record each
observed exit code and pass count and the evidence ID for the new commit.
After publishing the new commit on mira/genesis-99660ab004f9, verify the
title and description of PR #486. Use the commit title as the PR title.
The description must state that receipt task identifiers must exactly match
the external registry and that each receipt is checked for consistency before
counting. Authentication of verdict origin remains open. Report separately if
automatic publication retains the previous PR metadata. Merge requires independent
attestation provenance, fresh approval, and a passing CI run on the new head.
Evidence 508b49fef5e74d0e866f83aa98221b8d records that cryptography was absent
from the image used. The image rebuild remains to be confirmed.
Eight-language calibration and Ed25519 validation remain open.
The receipt aggregation and McNemar tests now live in
tests/test_mira_coding_fitness_receipts.py. The historical 153 passes span both suites.
"""

from math import isfinite, sqrt, ulp

import pytest

from genesis.mira_coding_fitness import (
    LanguageNonInferiority,
    McNemarPairs,
    aggregate_synthetic_receipts,
    assess_paired_non_inferiority,
    resolve_ablation_parent,
)
from genesis.mira_policy_contract import CodingPolicy, JsonObjectEnvelope


def synthetic_validator(receipt, context):
    if receipt["policy"] != context.policy:
        raise ValueError("synthetic policy mismatch")


def aggregate(receipts, contexts, validator=synthetic_validator):
    return aggregate_synthetic_receipts(
        receipts, contexts, validate_task_receipt_consistency=validator
    )


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
    resolved = resolve_ablation_parent(
        child, {child.sha256: parent.sha256}, {parent.sha256: parent}
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
