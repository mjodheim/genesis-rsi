"""Prospective self-experiment design for Genesis G5.

G5 turns an observed, attributed limitation into a frozen matched-budget
experiment plan. It does not inspect hidden cases, execute candidates, grade
itself, or promote a descendant. Those powers remain outside mutable Genesis.

When G4 identifies several plausible internal components, G5 preserves that
uncertainty and creates discriminating candidate arms instead of silently
selecting one.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from genesis.core import self_model as self_model_module
from genesis.trust_root import digest_of

PLAN_SCHEMA = "genesis-self-experiment-plan-v1"
ARM_SCHEMA = "genesis-self-experiment-arm-v1"


class ExperimentDesignError(RuntimeError):
    pass


def _arm(
    name: str,
    *,
    kind: str,
    component_id: str | None,
    intervention: str,
    budget: Mapping[str, Any],
) -> dict[str, Any]:
    payload = {
        "schema": ARM_SCHEMA,
        "name": name,
        "kind": kind,
        "component_id": component_id,
        "intervention": intervention,
        "budget": dict(budget),
    }
    return {**payload, "arm_digest": digest_of(payload)}


def _validate_budget(budget: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {
        "candidate_executions",
        "wall_time_seconds",
        "external_model_calls",
        "cpu_time_seconds",
        "memory_bytes",
    }
    cleaned: dict[str, Any] = {}
    for key, value in budget.items():
        if key not in allowed:
            raise ExperimentDesignError(f"unsupported budget axis: {key}")
        numeric = int(value)
        if numeric < 0:
            raise ExperimentDesignError(f"budget axis may not be negative: {key}")
        cleaned[key] = numeric
    if "candidate_executions" not in cleaned:
        raise ExperimentDesignError("candidate_executions budget is required")
    if "external_model_calls" not in cleaned:
        cleaned["external_model_calls"] = 0
    return cleaned


def _hypothesis(
    failure_class: str,
    component_ids: Sequence[str],
    interventions: Sequence[str],
) -> str:
    components = ", ".join(component_ids)
    choices = ", ".join(interventions)
    return (
        f"The observed {failure_class} limitation is causally influenced by one "
        f"or more of [{components}]; matched interventions among [{choices}] "
        "will discriminate the limiting machinery and may improve fresh "
        "matched-budget capability or preserve capability while reducing "
        "resource cost relative to the unchanged parent."
    )


def validate_plan(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != PLAN_SCHEMA:
        raise ExperimentDesignError("unsupported experiment-plan schema")
    value = dict(record)
    recorded = str(value.pop("plan_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise ExperimentDesignError("experiment plan does not reproduce its digest")

    target_ids = {str(item) for item in list(record.get("target_component_ids") or [])}
    if not target_ids:
        raise ExperimentDesignError("experiment has no target component")

    arms = list(record.get("arms") or [])
    if len(arms) < 2 or arms[0].get("kind") != "control":
        raise ExperimentDesignError("experiment requires control plus candidate arm")
    budgets = []
    names: set[str] = set()
    candidate_components: set[str] = set()
    for arm in arms:
        item = dict(arm)
        digest = str(item.pop("arm_digest", ""))
        if arm.get("schema") != ARM_SCHEMA or not digest or digest != digest_of(item):
            raise ExperimentDesignError("experiment arm does not reproduce its digest")
        if arm.get("name") in names:
            raise ExperimentDesignError("duplicate experiment arm name")
        names.add(str(arm.get("name")))
        budgets.append(dict(arm.get("budget") or {}))
        if arm.get("kind") == "candidate":
            component_id = str(arm.get("component_id") or "")
            if component_id not in target_ids:
                raise ExperimentDesignError("candidate arm targets undeclared component")
            candidate_components.add(component_id)
    if any(item != budgets[0] for item in budgets[1:]):
        raise ExperimentDesignError("all experiment arms must use identical budgets")
    if not candidate_components:
        raise ExperimentDesignError("experiment has no candidate component arm")
    if not record.get("evaluator_id") or not record.get("fresh_case_set_id"):
        raise ExperimentDesignError("external evaluator and fresh case-set identities are required")
    if bool(record.get("mutable_lineage_owns_verdict")):
        raise ExperimentDesignError("mutable lineage may not own experiment verdict")
    return dict(record)


def design_experiment(
    self_model: Mapping[str, Any],
    failure_record: Mapping[str, Any],
    *,
    evaluator_id: str,
    fresh_case_set_id: str,
    budget: Mapping[str, Any],
    metrics: Sequence[str] = (
        "task_success",
        "charged_candidate_executions",
        "wall_time",
        "peak_memory",
        "external_model_calls",
    ),
    max_candidate_arms: int = 6,
) -> dict[str, Any]:
    """Generate a prospective matched-budget experiment from G3/G4 evidence."""
    if max_candidate_arms < 1 or max_candidate_arms > 32:
        raise ExperimentDesignError("max_candidate_arms must be in [1, 32]")
    held = self_model_module.validate_self_model(self_model)
    failure_class = str(failure_record.get("primary_failure_class", "unknown"))
    if failure_class in {"unknown", "underdetermined"}:
        raise ExperimentDesignError(
            "failure attribution is not specific enough for a machinery experiment"
        )
    if failure_class == "evaluation":
        raise ExperimentDesignError(
            "evaluation failure belongs to the trust boundary; mutable Genesis may not redesign it as a self-experiment"
        )

    target = self_model_module.choose_intervention_target(held, failure_record)
    component_ids = [
        str(item) for item in list(target.get("candidate_component_ids") or []) if str(item)
    ]
    if not component_ids:
        raise ExperimentDesignError("no mutable self-model component is available for this failure")

    interventions = [
        str(item)
        for item in list(failure_record.get("recommended_interventions") or [])
        if str(item)
    ]
    if not interventions:
        raise ExperimentDesignError("failure record contains no candidate interventions")

    common_budget = _validate_budget(budget)
    arms = [
        _arm(
            "control-parent",
            kind="control",
            component_id=None,
            intervention="no_change",
            budget=common_budget,
        )
    ]
    candidate_pairs = [
        (component_id, intervention)
        for component_id in component_ids
        for intervention in interventions
    ][:max_candidate_arms]
    for index, (component_id, intervention) in enumerate(candidate_pairs, start=1):
        arms.append(_arm(
            f"candidate-{index}",
            kind="candidate",
            component_id=component_id,
            intervention=intervention,
            budget=common_budget,
        ))

    metrics_clean = sorted({str(metric) for metric in metrics if str(metric)})
    if not metrics_clean:
        raise ExperimentDesignError("at least one metric is required")

    component_by_id = {
        str(item["component_id"]): item
        for item in held["components"]
    }
    target_digests = {
        component_id: component_by_id[component_id]["component_digest"]
        for component_id in component_ids
    }

    payload = {
        "schema": PLAN_SCHEMA,
        "self_model_digest": held["self_model_digest"],
        "failure_model_digest": failure_record.get("failure_model_digest"),
        "failure_class": failure_class,
        "target_component_ids": component_ids,
        "target_component_digests": target_digests,
        "selected_component_id": (
            component_ids[0] if len(component_ids) == 1 else None
        ),
        "component_ambiguity": len(component_ids) > 1,
        "hypothesis": _hypothesis(failure_class, component_ids, interventions),
        "arms": arms,
        "evaluator_id": str(evaluator_id),
        "fresh_case_set_id": str(fresh_case_set_id),
        "fresh_case_contents_visible_to_lineage": False,
        "metrics": metrics_clean,
        "decision_objective": "pareto_capability_resource_frontier",
        "matched_budget": common_budget,
        "frozen_before_execution": True,
        "mutable_lineage_owns_verdict": False,
        "promotion_authority": "external_trust_root",
        "external_model_calls_for_design": 0,
    }
    return {**payload, "plan_digest": digest_of(payload)}
