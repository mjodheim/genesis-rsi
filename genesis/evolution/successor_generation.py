"""Evidence-driven whole-successor generation for Genesis v2 G9.

G9 is deliberately stricter than component evolution.  A successor is a
content-addressed architecture profile: it inherits the parent's whole self-model
and may override several active mechanisms only when prior qualified evidence
supports those changes.

The generator never sees the prospective G9 holdout and never owns the verdict.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from genesis.core import self_model as self_model_module
from genesis.learning import distillation
from genesis.trust_root import digest_of

PROFILE_SCHEMA = "genesis-system-profile-v1"
PROPOSAL_SCHEMA = "genesis-whole-successor-proposal-v1"
ROUTING_SCHEMA = "genesis-successor-routing-program-v1"


class SuccessorGenerationError(RuntimeError):
    pass


def _canonical_copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), sort_keys=True))


def _validate_profile(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != PROFILE_SCHEMA:
        raise SuccessorGenerationError("unsupported system profile schema")
    payload = {k: v for k, v in record.items() if k != "profile_digest"}
    if record.get("profile_digest") != digest_of(payload):
        raise SuccessorGenerationError("system profile digest does not reproduce")
    if int(record.get("generation", -1)) < 0:
        raise SuccessorGenerationError("profile generation is invalid")
    if not isinstance(record.get("component_inventory"), list):
        raise SuccessorGenerationError("profile component inventory is missing")
    if not isinstance(record.get("routing_program"), Mapping):
        raise SuccessorGenerationError("profile routing program is missing")
    return _canonical_copy(record)


def build_parent_profile(repository_root: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    model = self_model_module.build_self_model(root)
    held = self_model_module.validate_self_model(model)

    inventory = [
        {
            "component_id": item["component_id"],
            "component_digest": item["component_digest"],
            "source_identity": item["source_identity"],
            "mutable": item["mutable"],
            "trust_boundary": item["trust_boundary"],
        }
        for item in held["components"]
    ]
    inventory.sort(key=lambda item: item["component_id"])

    universal = next(
        item for item in inventory if item["component_id"] == "universal_operator_ir"
    )
    routing_payload = {
        "schema": ROUTING_SCHEMA,
        "order": ["universal_operator_ir"],
        "candidate_budget_is_global": True,
        "stop_after_first_passing_candidate": True,
        "external_model_fallback_enabled": False,
    }
    routing = {**routing_payload, "routing_digest": digest_of(routing_payload)}

    payload = {
        "schema": PROFILE_SCHEMA,
        "generation": 0,
        "parent_profile_digest": None,
        "self_model_digest": held["self_model_digest"],
        "component_inventory": inventory,
        "active_overrides": {
            "universal_operator_ir": {
                "kind": "repository_source",
                "source_sha256": universal["source_identity"]["sha256"],
                "source_path": universal["source_identity"]["path"],
            },
            "local_repair_specialist": None,
        },
        "routing_program": routing,
        "producer": "genesis-parent-profile-builder-v1",
        "external_model_calls_for_generation": 0,
        "hidden_holdout_visible": False,
    }
    return {**payload, "profile_digest": digest_of(payload)}


def _validate_g6(
    result: Mapping[str, Any],
    descendant: Mapping[str, Any],
) -> dict[str, Any]:
    if result.get("verdict") != "G6_SCIENTIFIC_GATE_PASSED" or result.get("gate_passed") is not True:
        raise SuccessorGenerationError("G6 evidence is not a passed qualification")
    parent = result.get("parent") or {}
    child = result.get("descendant") or {}
    if int(child.get("solved", -1)) <= int(parent.get("solved", -1)):
        raise SuccessorGenerationError("G6 descendant does not beat its parent")
    if result.get("requirements", {}).get("descendant_preserves_every_parent_success") is not True:
        raise SuccessorGenerationError("G6 evidence does not preserve parent successes")
    if result.get("requirements", {}).get("reverting_winning_mutation_removes_gain") is not True:
        raise SuccessorGenerationError("G6 causal revert evidence is missing")
    selected = (descendant.get("selection") or {}).get("selected_descendant") or {}
    source_sha = str(descendant.get("selected_source_sha256") or "")
    if not source_sha or source_sha != str(selected.get("source_sha256") or ""):
        raise SuccessorGenerationError("G6 descendant source identity does not reproduce")
    if source_sha != str(result.get("descendant_source_sha256") or ""):
        raise SuccessorGenerationError("G6 result and descendant source disagree")
    return {
        "source_sha256": source_sha,
        "mutation_id": str(result.get("selected_mutation_id") or ""),
        "result_digest": str(result.get("result_digest") or ""),
        "descendant_record_digest": str(descendant.get("descendant_record_digest") or ""),
        "parent_source_sha256": str(result.get("parent_source_sha256") or ""),
        "parent_solved": int(parent.get("solved", 0)),
        "descendant_solved": int(child.get("solved", 0)),
    }


def _validate_g8(
    result: Mapping[str, Any],
    freeze: Mapping[str, Any],
) -> dict[str, Any]:
    if result.get("verdict") != "G8_SCIENTIFIC_GATE_PASSED" or result.get("gate_passed") is not True:
        raise SuccessorGenerationError("G8 evidence is not a passed qualification")
    specialist = distillation.validate_specialist(freeze.get("specialist") or {})
    local = (result.get("local_specialist") or {}).get("aggregate") or {}
    external = (result.get("external_baseline") or {}).get("aggregate") or {}
    ablated = (result.get("empty_specialist_ablation") or {}).get("aggregate") or {}
    if int(local.get("solved", -1)) < int(external.get("solved", -1)):
        raise SuccessorGenerationError("G8 local specialist does not retain baseline success")
    if int(ablated.get("solved", -1)) >= int(local.get("solved", -1)):
        raise SuccessorGenerationError("G8 ablation does not remove specialist gain")
    if int(local.get("external_model_calls", -1)) != 0:
        raise SuccessorGenerationError("G8 local specialist is not local at runtime")
    return {
        "specialist_digest": specialist["specialist_digest"],
        "template_count": int(specialist["template_count"]),
        "result_digest": str(result.get("result_digest") or ""),
        "freeze_digest": str(freeze.get("freeze_digest") or ""),
        "external_solved": int(external.get("solved", 0)),
        "local_solved": int(local.get("solved", 0)),
        "ablation_solved": int(ablated.get("solved", 0)),
        "local_external_model_calls": int(local.get("external_model_calls", 0)),
    }


def generate_successor(
    parent_profile: Mapping[str, Any],
    *,
    g6_result: Mapping[str, Any],
    g6_descendant: Mapping[str, Any],
    g8_result: Mapping[str, Any],
    g8_specialist_freeze: Mapping[str, Any],
) -> dict[str, Any]:
    parent = _validate_profile(parent_profile)
    g6 = _validate_g6(g6_result, g6_descendant)
    g8 = _validate_g8(g8_result, g8_specialist_freeze)

    parent_universal = (
        parent["active_overrides"]["universal_operator_ir"]["source_sha256"]
    )
    if parent_universal != g6["parent_source_sha256"]:
        raise SuccessorGenerationError(
            "G6 qualified parent is not the universal operator active in Genesis N"
        )

    routing_payload = {
        "schema": ROUTING_SCHEMA,
        "order": ["local_repair_specialist", "universal_operator_ir"],
        "candidate_budget_is_global": True,
        "stop_after_first_passing_candidate": True,
        "external_model_fallback_enabled": False,
        "selection_rationale": (
            "prefer zero-model retained specialist when it emits; otherwise use "
            "the independently qualified evolved universal operator"
        ),
    }
    routing = {**routing_payload, "routing_digest": digest_of(routing_payload)}

    successor_payload = {
        "schema": PROFILE_SCHEMA,
        "generation": int(parent["generation"]) + 1,
        "parent_profile_digest": parent["profile_digest"],
        "self_model_digest": parent["self_model_digest"],
        "component_inventory": parent["component_inventory"],
        "active_overrides": {
            "universal_operator_ir": {
                "kind": "qualified_source_descendant",
                "source_sha256": g6["source_sha256"],
                "source_path": "experiment/g6_qualification/descendant/universal.py",
                "mutation_id": g6["mutation_id"],
                "evidence_result_digest": g6["result_digest"],
            },
            "local_repair_specialist": {
                "kind": "qualified_distilled_specialist",
                "specialist_digest": g8["specialist_digest"],
                "artifact_path": "experiment/g8_qualification/SPECIALIST.json",
                "template_count": g8["template_count"],
                "evidence_result_digest": g8["result_digest"],
            },
        },
        "routing_program": routing,
        "producer": "genesis-evidence-driven-successor-generator-v1",
        "external_model_calls_for_generation": 0,
        "hidden_holdout_visible": False,
    }
    successor = {**successor_payload, "profile_digest": digest_of(successor_payload)}

    changes = [
        {
            "component_id": "universal_operator_ir",
            "from": parent_universal,
            "to": g6["source_sha256"],
            "evidence": g6,
        },
        {
            "component_id": "local_repair_specialist",
            "from": None,
            "to": g8["specialist_digest"],
            "evidence": g8,
        },
        {
            "component_id": "candidate_router",
            "from": parent["routing_program"]["routing_digest"],
            "to": routing["routing_digest"],
            "evidence": {
                "rule": "prefer qualified zero-model specialist then qualified universal operator",
                "g6_result_digest": g6["result_digest"],
                "g8_result_digest": g8["result_digest"],
            },
        },
    ]
    proposal_payload = {
        "schema": PROPOSAL_SCHEMA,
        "parent_profile": parent,
        "successor_profile": successor,
        "material_changes": changes,
        "material_change_count": len(changes),
        "generation_evidence": {
            "g6": g6,
            "g8": g8,
        },
        "selection_rule": (
            "adopt only prior qualified causal improvements; compose retained local "
            "specialization before the evolved general operator; preserve every "
            "unmodified self-model component by digest"
        ),
        "lineage_produced": True,
        "prospective_holdout_visible": False,
        "mutable_lineage_owns_verdict": False,
        "external_model_calls": 0,
    }
    return {**proposal_payload, "proposal_digest": digest_of(proposal_payload)}


def ablate_profile(
    proposal: Mapping[str, Any],
    *,
    remove_change: str,
) -> dict[str, Any]:
    """Create a causal ablation of the generated successor without seeing evaluation."""
    held = validate_proposal(proposal)
    parent = held["parent_profile"]
    child = _canonical_copy(held["successor_profile"])

    if remove_change == "g6_universal_operator":
        child["active_overrides"]["universal_operator_ir"] = _canonical_copy(
            parent["active_overrides"]["universal_operator_ir"]
        )
    elif remove_change == "g8_local_specialist":
        child["active_overrides"]["local_repair_specialist"] = None
        route_payload = {
            "schema": ROUTING_SCHEMA,
            "order": ["universal_operator_ir"],
            "candidate_budget_is_global": True,
            "stop_after_first_passing_candidate": True,
            "external_model_fallback_enabled": False,
            "selection_rationale": "G8 local specialist removed for causal ablation",
        }
        child["routing_program"] = {
            **route_payload,
            "routing_digest": digest_of(route_payload),
        }
    else:
        raise SuccessorGenerationError(f"unsupported successor ablation: {remove_change}")

    child.pop("profile_digest", None)
    child["producer"] = f"genesis-g9-causal-ablation:{remove_change}"
    child["profile_digest"] = digest_of(child)
    return child


def validate_proposal(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != PROPOSAL_SCHEMA:
        raise SuccessorGenerationError("unsupported successor proposal schema")
    payload = {k: v for k, v in record.items() if k != "proposal_digest"}
    if record.get("proposal_digest") != digest_of(payload):
        raise SuccessorGenerationError("successor proposal digest does not reproduce")
    parent = _validate_profile(record.get("parent_profile") or {})
    successor = _validate_profile(record.get("successor_profile") or {})
    if successor["parent_profile_digest"] != parent["profile_digest"]:
        raise SuccessorGenerationError("successor does not name the supplied parent")
    if int(successor["generation"]) != int(parent["generation"]) + 1:
        raise SuccessorGenerationError("successor generation is not parent + 1")
    if int(record.get("material_change_count", -1)) < 2:
        raise SuccessorGenerationError("whole successor requires multiple material changes")
    if record.get("lineage_produced") is not True:
        raise SuccessorGenerationError("proposal is not lineage-produced")
    if record.get("prospective_holdout_visible") is not False:
        raise SuccessorGenerationError("successor saw the prospective holdout")
    if record.get("mutable_lineage_owns_verdict") is not False:
        raise SuccessorGenerationError("mutable lineage may not own the verdict")
    return _canonical_copy(record)
