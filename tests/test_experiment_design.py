from pathlib import Path

import pytest

from genesis.core import self_model
from genesis.evolution import experiment_design
from genesis.learning import failure_model


ROOT = Path(__file__).resolve().parents[1]


def _run(*, scheduled: int = 0, charged: int = 0, budget: int = 64, **extra) -> dict:
    value = {
        "report_digest": "prospective-failure",
        "candidate_budget": budget,
        "charged_candidate_executions": charged,
        "winner": None,
        "schedule": {
            "scheduled_count": scheduled,
            "family_input_counts": {"learned": 0, "retained": 0},
            "family_scheduled_counts": {},
        },
    }
    value.update(extra)
    return value


def _operator_failure(tmp_path: Path) -> dict:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    return failure_model.diagnose(
        tmp_path,
        _run(),
        target_prefixes=["logic.py"],
    )


def test_g5_generates_frozen_matched_budget_experiment(tmp_path: Path) -> None:
    model = self_model.build_self_model(ROOT)
    failure = _operator_failure(tmp_path)

    plan = experiment_design.design_experiment(
        model,
        failure,
        evaluator_id="external-evaluator-v1",
        fresh_case_set_id="hidden-holdout-sha256:abc",
        budget={
            "candidate_executions": 64,
            "wall_time_seconds": 120,
            "external_model_calls": 0,
        },
    )

    assert plan["failure_class"] == "operator"
    assert set(plan["target_component_ids"]) == {
        "structural_operator_engine",
        "universal_operator_ir",
    }
    assert plan["selected_component_id"] is None
    assert plan["component_ambiguity"] is True
    assert {
        arm["component_id"]
        for arm in plan["arms"]
        if arm["kind"] == "candidate"
    } == {
        "structural_operator_engine",
        "universal_operator_ir",
    }
    assert plan["frozen_before_execution"] is True
    assert plan["fresh_case_contents_visible_to_lineage"] is False
    assert plan["mutable_lineage_owns_verdict"] is False
    assert plan["promotion_authority"] == "external_trust_root"
    assert plan["external_model_calls_for_design"] == 0
    assert len(plan["arms"]) >= 2
    assert plan["arms"][0]["kind"] == "control"
    budgets = [arm["budget"] for arm in plan["arms"]]
    assert all(item == budgets[0] for item in budgets)
    assert experiment_design.validate_plan(plan) == plan


def test_g5_search_failure_targets_scheduler_experiment(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    model = self_model.build_self_model(ROOT)
    failure = failure_model.diagnose(
        tmp_path,
        _run(scheduled=64, charged=64, budget=64),
        target_prefixes=["logic.py"],
    )

    plan = experiment_design.design_experiment(
        model,
        failure,
        evaluator_id="evaluator-v1",
        fresh_case_set_id="holdout-v1",
        budget={"candidate_executions": 64, "external_model_calls": 0},
    )

    assert failure["primary_failure_class"] == "search"
    assert plan["target_component_ids"] == ["candidate_scheduler"]
    assert plan["selected_component_id"] == "candidate_scheduler"
    assert plan["component_ambiguity"] is False
    assert "search" in plan["hypothesis"]


def test_g5_refuses_to_self_experiment_on_invalid_evaluator(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    model = self_model.build_self_model(ROOT)
    failure = failure_model.diagnose(
        tmp_path,
        _run(evaluator_status="invalid"),
        target_prefixes=["logic.py"],
    )

    with pytest.raises(experiment_design.ExperimentDesignError, match="trust boundary"):
        experiment_design.design_experiment(
            model,
            failure,
            evaluator_id="broken-evaluator",
            fresh_case_set_id="holdout-v1",
            budget={"candidate_executions": 1, "external_model_calls": 0},
        )


def test_g5_refuses_underdetermined_failure(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    model = self_model.build_self_model(ROOT)
    failure = failure_model.diagnose(
        tmp_path,
        _run(
            scheduled=64,
            charged=64,
            budget=64,
            missing_documentation=True,
        ),
        target_prefixes=["logic.py"],
    )
    if failure["primary_failure_class"] != "underdetermined":
        failure = dict(failure)
        failure["primary_failure_class"] = "underdetermined"

    with pytest.raises(experiment_design.ExperimentDesignError, match="not specific enough"):
        experiment_design.design_experiment(
            model,
            failure,
            evaluator_id="evaluator-v1",
            fresh_case_set_id="holdout-v1",
            budget={"candidate_executions": 64, "external_model_calls": 0},
        )


def test_g5_rejects_tampered_plan(tmp_path: Path) -> None:
    model = self_model.build_self_model(ROOT)
    plan = experiment_design.design_experiment(
        model,
        _operator_failure(tmp_path),
        evaluator_id="evaluator-v1",
        fresh_case_set_id="holdout-v1",
        budget={"candidate_executions": 64, "external_model_calls": 0},
    )
    forged = dict(plan)
    forged["evaluator_id"] = "self-evaluator"

    with pytest.raises(experiment_design.ExperimentDesignError, match="does not reproduce"):
        experiment_design.validate_plan(forged)
