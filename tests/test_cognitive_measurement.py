from __future__ import annotations

import pytest

from genesis.cognitive_measurement import (
    CognitiveMeasurementError,
    ExternalBudget,
    compare_matched,
    create_measurement,
)


BUDGET = ExternalBudget(case_limit=2, max_node_executions_per_case=4)


def measurement(architecture: str, passed: tuple[bool, bool], *, cpu: int = 10):
    return create_measurement(
        architecture_digest=architecture,
        evaluator_digest="eval-v1",
        case_set_digest="cases-v1",
        budget=BUDGET,
        case_results=[
            {"case_digest": "case-b", "passed": passed[1], "node_executions": 3},
            {"case_digest": "case-a", "passed": passed[0], "node_executions": 2},
        ],
        cpu_process_time_ns=cpu,
    )


def test_measurement_is_content_addressed_and_refuses_to_invent_energy():
    record = measurement("parent", (True, False))
    assert record["case_results"][0]["case_digest"] == "case-a"
    assert record["resources"]["energy_joules"] is None
    assert record["resources"]["energy_measurement_available"] is False
    assert record["resources"]["cpu_time_is_compute_proxy"] is True
    assert len(record["measurement_digest"]) == 64


def test_energy_requires_instrument_identity():
    with pytest.raises(CognitiveMeasurementError, match="instrument"):
        create_measurement(
            architecture_digest="a",
            evaluator_digest="e",
            case_set_digest="c",
            budget=BUDGET,
            case_results=[],
            cpu_process_time_ns=0,
            energy_joules=1.0,
        )


def test_external_case_and_execution_budgets_fail_closed():
    with pytest.raises(CognitiveMeasurementError, match="case budget"):
        create_measurement(
            architecture_digest="a", evaluator_digest="e", case_set_digest="c", budget=BUDGET,
            case_results=[
                {"case_digest": "1", "passed": True, "node_executions": 1},
                {"case_digest": "2", "passed": True, "node_executions": 1},
                {"case_digest": "3", "passed": True, "node_executions": 1},
            ], cpu_process_time_ns=1,
        )
    with pytest.raises(CognitiveMeasurementError, match="node-execution"):
        create_measurement(
            architecture_digest="a", evaluator_digest="e", case_set_digest="c", budget=BUDGET,
            case_results=[{"case_digest": "1", "passed": True, "node_executions": 5}],
            cpu_process_time_ns=1,
        )


def test_matched_comparison_reports_capability_and_resource_deltas_without_verdict():
    parent = measurement("parent", (True, False), cpu=20)
    child = measurement("child", (True, True), cpu=25)
    result = compare_matched(parent, child)
    assert result["capability_delta_passed"] == 1
    assert result["node_executions_delta"] == 0
    assert result["cpu_process_time_delta_ns"] == 5
    assert result["energy_delta_joules"] is None
    assert "adopt" not in result
    assert "winner" not in result


def test_comparison_rejects_changed_evaluator_cases_or_budget():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    changed = dict(child)
    changed["case_set_digest"] = "other"
    with pytest.raises(CognitiveMeasurementError, match="case_set_digest"):
        compare_matched(parent, changed)


def test_comparison_rejects_tampered_measurement():
    parent = measurement("parent", (True, False))
    child = measurement("child", (True, True))
    child["capability"]["passed"] = 99
    with pytest.raises(CognitiveMeasurementError, match="does not reproduce"):
        compare_matched(parent, child)


def test_comparison_rejects_different_evaluated_case_identities():
    parent = measurement("parent", (True, False))
    child = create_measurement(
        architecture_digest="child",
        evaluator_digest="eval-v1",
        case_set_digest="cases-v1",
        budget=BUDGET,
        case_results=[
            {"case_digest": "case-a", "passed": True, "node_executions": 2},
            {"case_digest": "case-c", "passed": True, "node_executions": 3},
        ],
        cpu_process_time_ns=10,
    )
    with pytest.raises(CognitiveMeasurementError, match="identical evaluated case identities"):
        compare_matched(parent, child)
