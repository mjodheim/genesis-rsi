"""Machine-readable causal self model for Genesis G4.

The self model is not personality, introspection theatre, or permission to alter
the trust root.  It is a content-addressed map of active machinery: what each
component does, which failure classes it can influence, what it consumes and
produces, whether it is mutable, and which source bytes define the current
implementation.

Genesis may use this map to choose *where* to experiment.  It still does not own
the verdict that an experiment improved the lineage.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis.trust_root import digest_of

SELF_MODEL_SCHEMA = "genesis-self-model-v1"
COMPONENT_SCHEMA = "genesis-self-model-component-v1"
TARGET_SCHEMA = "genesis-self-model-intervention-target-v1"

_COMPONENT_SPECS = (
    {
        "component_id": "language_substrate",
        "module_path": "genesis/languages/substrate.py",
        "role": "representation",
        "failure_classes": ["representation", "knowledge"],
        "inputs": ["source_bytes", "repository_metadata"],
        "outputs": ["structural_documents", "documentation_requests"],
        "resource_axes": ["cpu_time", "memory", "bytes_scanned"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "language_toolchains",
        "module_path": "genesis/languages/toolchains.py",
        "role": "environment_interface",
        "failure_classes": ["toolchain"],
        "inputs": ["repository_root", "host_tool_availability"],
        "outputs": ["toolchain_capability_report"],
        "resource_axes": ["tool_invocations"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "universal_operator_ir",
        "module_path": "genesis/operators/universal.py",
        "role": "transformation_representation",
        "failure_classes": ["operator"],
        "inputs": ["validated_before_after_pair", "structural_document"],
        "outputs": ["universal_operator", "candidate_mutations"],
        "resource_axes": ["candidate_count", "cpu_time", "memory"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "structural_operator_engine",
        "module_path": "genesis/operators/structural.py",
        "role": "transformation_learning",
        "failure_classes": ["operator"],
        "inputs": ["validated_patch", "source_text"],
        "outputs": ["structural_operators", "candidate_mutations"],
        "resource_axes": ["candidate_count", "cpu_time"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "strategy_memory",
        "module_path": "genesis/memory/strategy.py",
        "role": "memory_retrieval",
        "failure_classes": ["retrieval"],
        "inputs": ["retained_strategies", "task_context"],
        "outputs": ["ranked_retrievals"],
        "resource_axes": ["bytes_retained", "retrieval_latency"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "candidate_scheduler",
        "module_path": "genesis/runtime/candidate_scheduler.py",
        "role": "planning_and_allocation",
        "failure_classes": ["planner", "search"],
        "inputs": ["candidate_families", "candidate_budget"],
        "outputs": ["scheduled_candidates"],
        "resource_axes": ["candidate_count", "charged_executions"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "failure_model",
        "module_path": "genesis/learning/failure_model.py",
        "role": "failure_attribution",
        "failure_classes": ["unknown", "underdetermined"],
        "inputs": ["run_evidence", "substrate_evidence", "retrieval_evidence"],
        "outputs": ["failure_attribution", "intervention_recommendations"],
        "resource_axes": ["cpu_time"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "local_specialist_distillation",
        "module_path": "genesis/learning/distillation.py",
        "role": "local_specialization",
        "failure_classes": ["retrieval", "search"],
        "inputs": ["validated_expensive_reasoning", "retained_templates"],
        "outputs": ["content_addressed_local_specialist", "local_candidates"],
        "resource_axes": ["candidate_count", "cpu_time", "external_model_calls", "runtime_cost"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "successor_generator",
        "module_path": "genesis/evolution/successor_generation.py",
        "role": "architecture_successor_generation",
        "failure_classes": ["planner", "search", "retrieval"],
        "inputs": ["self_model", "qualified_lineage_evidence", "component_artifacts"],
        "outputs": ["content_addressed_successor_profile", "component_overrides", "routing_program"],
        "resource_axes": ["candidate_count", "cpu_time", "memory"],
        "mutable": True,
        "trust_boundary": "lineage",
    },
    {
        "component_id": "trust_root",
        "module_path": "genesis/trust_root.py",
        "role": "external_authority",
        "failure_classes": ["evaluation"],
        "inputs": ["candidate_evidence", "budgets", "authority_records"],
        "outputs": ["validated_measurement", "accept_reject_boundary"],
        "resource_axes": [],
        "mutable": False,
        "trust_boundary": "root",
    },
)


def _source_identity(root: Path, module_path: str) -> dict[str, str]:
    path = root / module_path
    if not path.is_file():
        return {"path": module_path, "sha256": "", "status": "missing"}
    content = path.read_bytes()
    return {
        "path": module_path,
        "sha256": hashlib.sha256(content).hexdigest(),
        "status": "present",
    }


def build_self_model(root: str | Path) -> dict[str, Any]:
    """Build a content-addressed model of the currently checked-out machinery."""
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"repository root does not exist: {base}")

    components: list[dict[str, Any]] = []
    for raw in _COMPONENT_SPECS:
        source = _source_identity(base, str(raw["module_path"]))
        payload = {
            "schema": COMPONENT_SCHEMA,
            **raw,
            "source_identity": source,
        }
        components.append({**payload, "component_digest": digest_of(payload)})

    payload = {
        "schema": SELF_MODEL_SCHEMA,
        # Keep the identity portable across checkout locations. Individual
        # component paths are already repository-relative and source-addressed.
        "repository_root": ".",
        "components": components,
        "component_count": len(components),
        "mutable_component_ids": sorted(
            item["component_id"] for item in components if item["mutable"]
        ),
        "trust_root_component_ids": sorted(
            item["component_id"] for item in components if not item["mutable"]
        ),
        "external_model_calls": 0,
    }
    return {**payload, "self_model_digest": digest_of(payload)}


def validate_self_model(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != SELF_MODEL_SCHEMA:
        raise ValueError("unsupported self-model schema")
    value = dict(record)
    recorded = str(value.pop("self_model_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise ValueError("self model does not reproduce its digest")
    component_ids: set[str] = set()
    for component in list(record.get("components") or []):
        if component.get("schema") != COMPONENT_SCHEMA:
            raise ValueError("unsupported self-model component schema")
        item = dict(component)
        digest = str(item.pop("component_digest", ""))
        if not digest or digest != digest_of(item):
            raise ValueError("self-model component does not reproduce its digest")
        component_id = str(component.get("component_id"))
        if component_id in component_ids:
            raise ValueError("duplicate self-model component")
        component_ids.add(component_id)
        if component.get("trust_boundary") == "root" and bool(component.get("mutable")):
            raise ValueError("trust-root component may not be mutable")
    return dict(record)


def components_for_failure(
    self_model: Mapping[str, Any],
    failure_class: str,
    *,
    mutable_only: bool = False,
) -> list[dict[str, Any]]:
    held = validate_self_model(self_model)
    result = []
    for component in held["components"]:
        if str(failure_class) not in set(component.get("failure_classes") or []):
            continue
        if mutable_only and not bool(component.get("mutable")):
            continue
        result.append(dict(component))
    return result


def choose_intervention_target(
    self_model: Mapping[str, Any],
    failure_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Choose where Genesis may experiment, never what the evaluator must accept."""
    held = validate_self_model(self_model)
    failure_class = str(failure_record.get("primary_failure_class", "unknown"))
    candidates = components_for_failure(held, failure_class, mutable_only=True)

    reason = "failure_class_to_mutable_component"
    candidates = sorted(candidates, key=lambda item: str(item["component_id"]))
    if not candidates:
        if failure_class == "evaluation":
            reason = "failure_points_to_trust_root; lineage_must_not_modify_it"
        else:
            reason = "no_mutable_component_matches_failure"
        selected = None
    elif len(candidates) == 1:
        selected = candidates[0]
    else:
        # Do not convert coarse failure attribution into fake precision.  G5
        # can design a matched experiment across these candidate components.
        reason = "multiple_mutable_components_match_failure"
        selected = None

    payload = {
        "schema": TARGET_SCHEMA,
        "self_model_digest": held["self_model_digest"],
        "failure_model_digest": failure_record.get("failure_model_digest"),
        "failure_class": failure_class,
        "candidate_component_ids": [
            item["component_id"] for item in candidates
        ],
        "selected_component_id": (
            selected["component_id"] if selected is not None else None
        ),
        "selected_component_digest": (
            selected["component_digest"] if selected is not None else None
        ),
        "reason": reason,
        "trust_root_modification_allowed": False,
        "external_model_calls": 0,
    }
    return {**payload, "target_digest": digest_of(payload)}
