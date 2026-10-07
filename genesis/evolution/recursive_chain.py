"""Causal recursive-successor induction for the Genesis v2 G10 campaign.

The module deliberately separates task solving from successor production.
A generation may advance only when its own evaluated discovery traces contain
sufficient evidence to justify the next machinery capability. The fresh
qualification holdout is never an input to this module and mutable Genesis never
owns the acceptance verdict.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any, Mapping

from genesis.evolution import successor_generation
from genesis.trust_root import digest_of

CHAIN_PROFILE_SCHEMA = "genesis-g10-chain-profile-v1"
CHAIN_PROPOSAL_SCHEMA = "genesis-g10-chain-proposal-v1"
DISCOVERY_SCHEMA = "genesis-g10-discovery-evidence-v1"
CAPABILITY_SCHEMA = "genesis-g10-recursive-capability-v1"


class RecursiveChainError(RuntimeError):
    pass


def _copy(value: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(value), sort_keys=True))


def _digest_record(record: Mapping[str, Any], digest_key: str) -> str:
    payload = {key: value for key, value in record.items() if key != digest_key}
    return digest_of(payload)


def _capability(payload: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(payload)
    return {**value, "capability_digest": digest_of(value)}


def validate_profile(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != CHAIN_PROFILE_SCHEMA:
        raise RecursiveChainError("unsupported G10 chain profile schema")
    if record.get("profile_digest") != _digest_record(record, "profile_digest"):
        raise RecursiveChainError("G10 chain profile digest does not reproduce")
    generation = int(record.get("campaign_generation", -1))
    if generation < 0 or int(record.get("lineage_generation", -1)) < 1:
        raise RecursiveChainError("invalid G10 generation")
    base = successor_generation._validate_profile(record.get("base_system_profile") or {})
    capability = record.get("recursive_capability") or {}
    if capability.get("schema") != CAPABILITY_SCHEMA:
        raise RecursiveChainError("missing G10 recursive capability")
    if capability.get("capability_digest") != _digest_record(capability, "capability_digest"):
        raise RecursiveChainError("recursive capability digest does not reproduce")
    level = int(capability.get("level", -1))
    if level != generation or level not in (0, 1, 2, 3):
        raise RecursiveChainError("capability level and campaign generation disagree")
    if generation == 0:
        if record.get("parent_profile_digest") is not None:
            raise RecursiveChainError("G10 seed may not name a G10 parent")
    elif not str(record.get("parent_profile_digest") or ""):
        raise RecursiveChainError("non-seed G10 profile must name its parent")
    if int(record.get("external_model_calls_for_generation", -1)) != 0:
        raise RecursiveChainError("G10 generation must use zero external model calls")
    if record.get("prospective_holdout_visible") is not False:
        raise RecursiveChainError("G10 profile generation may not see its qualification holdout")
    result = _copy(record)
    result["base_system_profile"] = base
    return result


def build_seed_profile(g9_freeze: Mapping[str, Any]) -> dict[str, Any]:
    freeze_payload = {key: value for key, value in g9_freeze.items() if key != "freeze_digest"}
    if g9_freeze.get("freeze_digest") != digest_of(freeze_payload):
        raise RecursiveChainError("G9 successor freeze digest does not reproduce")
    proposal = successor_generation.validate_proposal(g9_freeze.get("proposal") or {})
    g9_successor = proposal["successor_profile"]
    specialist = (g9_successor.get("active_overrides") or {}).get("local_repair_specialist") or {}
    specialist_digest = str(specialist.get("specialist_digest") or "")
    if not specialist_digest:
        raise RecursiveChainError("G10 seed requires the qualified G8 retained specialist")

    cap = _capability({
        "schema": CAPABILITY_SCHEMA,
        "level": 0,
        "mechanism": "single_site_retained_specialist",
        "base_specialist_digest": specialist_digest,
        "pair_template_digests": [],
        "scope_binding": False,
        "iterate_matching_scopes": False,
        "acquired_from_discovery_digest": None,
    })
    payload = {
        "schema": CHAIN_PROFILE_SCHEMA,
        "campaign_generation": 0,
        "lineage_generation": int(g9_successor["generation"]),
        "parent_profile_digest": None,
        "g9_seed_profile_digest": g9_successor["profile_digest"],
        "base_system_profile": g9_successor,
        "recursive_capability": cap,
        "producer": "genesis-g10-seed-from-qualified-g9-v1",
        "external_model_calls_for_generation": 0,
        "prospective_holdout_visible": False,
    }
    return {**payload, "profile_digest": digest_of(payload)}


def validate_discovery(record: Mapping[str, Any], *, parent_profile_digest: str) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != DISCOVERY_SCHEMA:
        raise RecursiveChainError("unsupported G10 discovery evidence schema")
    if record.get("discovery_digest") != _digest_record(record, "discovery_digest"):
        raise RecursiveChainError("G10 discovery digest does not reproduce")
    if record.get("profile_digest") != parent_profile_digest:
        raise RecursiveChainError("discovery evidence belongs to another profile")
    if int(record.get("external_model_calls", -1)) != 0:
        raise RecursiveChainError("discovery used an external model")
    if int(record.get("candidate_budget_per_case", 0)) < 1:
        raise RecursiveChainError("discovery candidate budget is invalid")
    if int(record.get("solved", -1)) != len(record.get("successful_traces") or []):
        raise RecursiveChainError("discovery solved count and traces disagree")
    return _copy(record)


def _level0_to_level1(parent: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    counts = Counter(
        str(trace.get("base_template_digest") or "")
        for trace in discovery["successful_traces"]
        if str(trace.get("base_template_digest") or "")
    )
    supported = [(count, digest) for digest, count in counts.items() if count >= 2]
    if len(supported) < 2:
        raise RecursiveChainError(
            "level-1 induction requires at least two distinct retained templates with repeated solved evidence"
        )
    selected = [
        digest
        for count, digest in sorted(supported, key=lambda item: (-item[0], item[1]))[:2]
    ]
    return _capability({
        "schema": CAPABILITY_SCHEMA,
        "level": 1,
        "mechanism": "paired_retained_template_composition",
        "base_specialist_digest": parent["recursive_capability"]["base_specialist_digest"],
        "pair_template_digests": sorted(selected),
        "scope_binding": False,
        "iterate_matching_scopes": False,
        "acquired_from_discovery_digest": discovery["discovery_digest"],
    })


def _level1_to_level2(parent: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    qualified = [
        trace
        for trace in discovery["successful_traces"]
        if int(trace.get("capability_level", -1)) >= 1
        and trace.get("mode") == "global_pair"
        and len(trace.get("scope_ids") or []) == 1
    ]
    scopes = {str(trace["scope_ids"][0]) for trace in qualified}
    if len(qualified) < 3 or len(scopes) < 3:
        raise RecursiveChainError(
            "level-2 induction requires repeated successful pair composition in at least three distinct scopes"
        )
    previous = parent["recursive_capability"]
    return _capability({
        "schema": CAPABILITY_SCHEMA,
        "level": 2,
        "mechanism": "scope_bound_pair_search",
        "base_specialist_digest": previous["base_specialist_digest"],
        "pair_template_digests": previous["pair_template_digests"],
        "scope_binding": True,
        "iterate_matching_scopes": False,
        "acquired_from_discovery_digest": discovery["discovery_digest"],
    })


def _level2_to_level3(parent: Mapping[str, Any], discovery: Mapping[str, Any]) -> dict[str, Any]:
    qualified = [
        trace
        for trace in discovery["successful_traces"]
        if int(trace.get("capability_level", -1)) >= 2
        and trace.get("mode") == "scope_bound_pair"
        and len(trace.get("scope_ids") or []) == 1
    ]
    scopes = {str(trace["scope_ids"][0]) for trace in qualified}
    if len(qualified) < 3 or len(scopes) < 3:
        raise RecursiveChainError(
            "level-3 induction requires repeated successful scope-bound composition across distinct scopes"
        )
    previous = parent["recursive_capability"]
    return _capability({
        "schema": CAPABILITY_SCHEMA,
        "level": 3,
        "mechanism": "iterated_scope_pair_composition",
        "base_specialist_digest": previous["base_specialist_digest"],
        "pair_template_digests": previous["pair_template_digests"],
        "scope_binding": True,
        "iterate_matching_scopes": True,
        "acquired_from_discovery_digest": discovery["discovery_digest"],
    })


def induce_successor(parent_profile: Mapping[str, Any], discovery_evidence: Mapping[str, Any]) -> dict[str, Any]:
    parent = validate_profile(parent_profile)
    discovery = validate_discovery(discovery_evidence, parent_profile_digest=parent["profile_digest"])
    level = int(parent["recursive_capability"]["level"])
    if level == 0:
        capability = _level0_to_level1(parent, discovery)
    elif level == 1:
        capability = _level1_to_level2(parent, discovery)
    elif level == 2:
        capability = _level2_to_level3(parent, discovery)
    else:
        raise RecursiveChainError("G10 campaign is capped at generation 3")

    child_payload = {
        "schema": CHAIN_PROFILE_SCHEMA,
        "campaign_generation": int(parent["campaign_generation"]) + 1,
        "lineage_generation": int(parent["lineage_generation"]) + 1,
        "parent_profile_digest": parent["profile_digest"],
        "g9_seed_profile_digest": parent["g9_seed_profile_digest"],
        "base_system_profile": parent["base_system_profile"],
        "recursive_capability": capability,
        "producer": "genesis-g10-evidence-driven-recursive-successor-v1",
        "external_model_calls_for_generation": 0,
        "prospective_holdout_visible": False,
    }
    child = {**child_payload, "profile_digest": digest_of(child_payload)}
    proposal_payload = {
        "schema": CHAIN_PROPOSAL_SCHEMA,
        "parent_profile": parent,
        "successor_profile": child,
        "discovery_digest": discovery["discovery_digest"],
        "material_change": {
            "component_id": "recursive_repair_acquisition_machinery",
            "from_capability_digest": parent["recursive_capability"]["capability_digest"],
            "to_capability_digest": capability["capability_digest"],
            "from_level": level,
            "to_level": level + 1,
        },
        "lineage_produced": True,
        "prospective_holdout_visible": False,
        "mutable_lineage_owns_verdict": False,
        "external_model_calls": 0,
    }
    return {**proposal_payload, "proposal_digest": digest_of(proposal_payload)}


def validate_proposal(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != CHAIN_PROPOSAL_SCHEMA:
        raise RecursiveChainError("unsupported G10 successor proposal schema")
    if record.get("proposal_digest") != _digest_record(record, "proposal_digest"):
        raise RecursiveChainError("G10 successor proposal digest does not reproduce")
    parent = validate_profile(record.get("parent_profile") or {})
    child = validate_profile(record.get("successor_profile") or {})
    if child["parent_profile_digest"] != parent["profile_digest"]:
        raise RecursiveChainError("G10 child does not name supplied parent")
    if int(child["campaign_generation"]) != int(parent["campaign_generation"]) + 1:
        raise RecursiveChainError("G10 campaign generation is not parent + 1")
    if int(child["lineage_generation"]) != int(parent["lineage_generation"]) + 1:
        raise RecursiveChainError("G10 lineage generation is not parent + 1")
    if record.get("lineage_produced") is not True:
        raise RecursiveChainError("G10 proposal is not lineage-produced")
    if record.get("prospective_holdout_visible") is not False:
        raise RecursiveChainError("G10 proposal saw the prospective holdout")
    if record.get("mutable_lineage_owns_verdict") is not False:
        raise RecursiveChainError("mutable lineage may not own G10 verdict")
    return _copy(record)
