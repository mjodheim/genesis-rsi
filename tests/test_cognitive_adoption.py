from __future__ import annotations

import pytest

from genesis.cognitive_adoption import (
    CognitiveAdoptionError,
    create_adoption_record,
    create_causal_ablation_record,
    create_rollback_record,
)
from genesis.cognitive_measurement import ExternalBudget, create_measurement


BUDGET = ExternalBudget(case_limit=2, max_node_executions_per_case=4)


def measurement(architecture: str, passed: tuple[bool, bool], *, cpu: int = 10):
    return create_measurement(
        architecture_digest=architecture,
        evaluator_digest="eval-v1",
        case_set_digest="cases-v1",
        budget=BUDGET,
        case_results=[
            {"case_digest": "case-a", "passed": passed[0], "node_executions": 2},
            {"case_digest": "case-b", "passed": passed[1], "node_executions": 3},
        ],
        cpu_process_time_ns=cpu,
    )


def test_adoption_binds_external_authority_rule_proposal_and_matched_evidence():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    record = create_adoption_record(
        parent_measurement=parent,
        candidate_measurement=child,
        decision="adopt",
        authority_digest="authority-v1",
        rule_digest="prospective-rule-v1",
        proposal_digest="proposal-v1",
    )
    assert record["decision"] == "adopt"
    assert record["parent_architecture_digest"] == "parent"
    assert record["candidate_architecture_digest"] == "child"
    assert len(record["adoption_digest"]) == 64


def test_adoption_refuses_unmatched_evidence():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    child["case_set_digest"] = "other"
    with pytest.raises(CognitiveAdoptionError, match="case_set_digest"):
        create_adoption_record(
            parent_measurement=parent,
            candidate_measurement=child,
            decision="adopt",
            authority_digest="authority",
            rule_digest="rule",
            proposal_digest="proposal",
        )


def test_rollback_restores_exact_parent_and_requires_prior_adoption():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    adopted = create_adoption_record(
        parent_measurement=parent,
        candidate_measurement=child,
        decision="adopt",
        authority_digest="authority",
        rule_digest="rule",
        proposal_digest="proposal",
    )
    rollback = create_rollback_record(
        adoption_record=adopted,
        authority_digest="rollback-authority",
        reason_evidence_digest="regression-evidence",
    )
    assert rollback["from_architecture_digest"] == "child"
    assert rollback["restore_architecture_digest"] == "parent"

    rejected = create_adoption_record(
        parent_measurement=parent,
        candidate_measurement=child,
        decision="reject",
        authority_digest="authority",
        rule_digest="rule",
        proposal_digest="proposal",
    )
    with pytest.raises(CognitiveAdoptionError, match="only an adopted"):
        create_rollback_record(
            adoption_record=rejected,
            authority_digest="rollback-authority",
            reason_evidence_digest="evidence",
        )


def test_causal_ablation_is_paired_and_descriptive_only():
    parent = measurement("parent", (True, False), cpu=20)
    child = measurement("child", (True, True), cpu=25)
    ablated = measurement("child-ablated", (True, False), cpu=21)
    record = create_causal_ablation_record(
        parent_measurement=parent,
        candidate_measurement=child,
        ablated_measurement=ablated,
        proposal_digest="proposal-v1",
        ablation_digest="remove-change-v1",
    )
    assert record["candidate_capability_delta_passed"] == 1
    assert record["ablated_capability_delta_passed"] == 0
    assert record["capability_attenuation_under_ablation"] == 1
    assert record["causal_verdict"] is None


def test_causal_ablation_requires_three_distinct_architectures():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    with pytest.raises(CognitiveAdoptionError, match="must be distinct"):
        create_causal_ablation_record(
            parent_measurement=parent,
            candidate_measurement=child,
            ablated_measurement=child,
            proposal_digest="proposal",
            ablation_digest="ablation",
        )
