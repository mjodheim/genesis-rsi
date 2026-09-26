"""Bounded, content-addressed mutations of lineage-held cognitive search machinery.

This module mutates the policy that *produces* architecture mutations. It has no evaluator access,
cannot adopt its own descendants, and cannot widen the host's external candidate ceiling.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from genesis import cognitive_search

META_MUTATION_SCHEMA = "genesis-cognitive-search-policy-mutation-v1"


class CognitiveMetaMutationError(ValueError):
    """Raised when mutation machinery attempts to mutate outside admitted bounds."""


def _digest(value: Any) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise CognitiveMetaMutationError("policy mutation contains non-canonical data") from exc
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def apply_policy_mutation(
    parent_policy: Mapping[str, Any],
    proposal: Mapping[str, Any],
    *,
    max_candidate_limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply one bounded meta-mutation and return the descendant plus its exact mutation record."""
    try:
        parent = cognitive_search.validate_policy(parent_policy)
    except cognitive_search.CognitiveSearchError as exc:
        raise CognitiveMetaMutationError(str(exc)) from exc
    if max_candidate_limit < 1:
        raise CognitiveMetaMutationError("external candidate ceiling must be positive")
    if not isinstance(proposal, Mapping):
        raise CognitiveMetaMutationError("policy mutation proposal is not a record")
    kind = str(proposal.get("kind") or "")
    kinds = list(parent["mutation_kinds"])
    primitives = list(parent["primitive_order"])
    limit = parent["candidate_limit"]

    if kind == "swap_mutation_kinds":
        left, right = int(proposal.get("left", -1)), int(proposal.get("right", -1))
        if left == right or min(left, right) < 0 or max(left, right) >= len(kinds):
            raise CognitiveMetaMutationError("mutation-kind swap indices are invalid")
        kinds[left], kinds[right] = kinds[right], kinds[left]
    elif kind == "swap_primitives":
        left, right = int(proposal.get("left", -1)), int(proposal.get("right", -1))
        if left == right or min(left, right) < 0 or max(left, right) >= len(primitives):
            raise CognitiveMetaMutationError("primitive swap indices are invalid")
        primitives[left], primitives[right] = primitives[right], primitives[left]
    elif kind == "set_candidate_limit":
        limit = int(proposal.get("candidate_limit", 0))
        if limit < 1 or limit > max_candidate_limit:
            raise CognitiveMetaMutationError("candidate limit exceeds external admitted bounds")
    else:
        raise CognitiveMetaMutationError("unsupported policy mutation kind")

    child = cognitive_search.create_policy(
        mutation_kinds=kinds,
        primitive_order=primitives,
        candidate_limit=limit,
        parent_policy_digest=parent["policy_digest"],
    )
    if child["policy_digest"] == parent["policy_digest"]:
        raise CognitiveMetaMutationError("policy mutation produced no descendant")
    canonical_proposal = dict(proposal)
    payload = {
        "schema": META_MUTATION_SCHEMA,
        "parent_policy_digest": parent["policy_digest"],
        "child_policy_digest": child["policy_digest"],
        "proposal": canonical_proposal,
        "proposal_digest": _digest(canonical_proposal),
        "external_max_candidate_limit": int(max_candidate_limit),
    }
    return child, {**payload, "mutation_record_digest": _digest(payload)}
