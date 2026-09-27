"""External-control transitions for lineage-held cognitive mutation machinery.

A lineage may carry a search policy and produce bounded descendants of that policy, but it cannot
select or install those descendants by itself. Installation requires a content-addressed external
adoption record that binds the exact held parent, exact candidate and exact meta-mutation record.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from genesis import cognitive_meta_mutation
from genesis import cognitive_search
from genesis import cognitive_search_controller
from genesis.trust_root import provenance

POLICY_ADOPTION_SCHEMA = "genesis-cognitive-policy-adoption-v1"


class CognitivePolicyEvolutionError(RuntimeError):
    """Raised when mutation-machinery evolution crosses its external-control boundary."""


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def create_external_policy_adoption(
    *,
    parent_policy: Mapping[str, Any],
    candidate_policy: Mapping[str, Any],
    mutation_record: Mapping[str, Any],
    decision: str,
    authority_digest: str,
    rule_digest: str,
) -> dict[str, Any]:
    """Create an externally authored decision over one exact mutation-machinery descendant."""
    parent = cognitive_search.validate_policy(parent_policy)
    child, reproduced = cognitive_meta_mutation.validate_policy_mutation_record(
        mutation_record, parent_policy=parent
    )
    if cognitive_search.validate_policy(candidate_policy) != child:
        raise CognitivePolicyEvolutionError("candidate policy does not reproduce from meta-mutation")
    if decision not in {"adopt", "reject"}:
        raise CognitivePolicyEvolutionError("external policy decision must be adopt or reject")
    if not authority_digest or not rule_digest:
        raise CognitivePolicyEvolutionError("external authority and prospective rule identities are required")
    payload = {
        "schema": POLICY_ADOPTION_SCHEMA,
        "decision": decision,
        "authority_digest": str(authority_digest),
        "rule_digest": str(rule_digest),
        "parent_policy_digest": parent["policy_digest"],
        "candidate_policy_digest": child["policy_digest"],
        "mutation_record_digest": reproduced["mutation_record_digest"],
    }
    return {**payload, "adoption_digest": _digest(payload)}


def validate_external_policy_adoption(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != POLICY_ADOPTION_SCHEMA:
        raise CognitivePolicyEvolutionError("policy adoption uses an unrecognized schema")
    payload = {key: value for key, value in record.items() if key != "adoption_digest"}
    if record.get("adoption_digest") != _digest(payload):
        raise CognitivePolicyEvolutionError("policy adoption identity does not reproduce")
    if record.get("decision") not in {"adopt", "reject"}:
        raise CognitivePolicyEvolutionError("policy adoption carries an invalid external decision")
    return dict(record)


def apply_external_policy_adoption(
    genesis,
    candidate_policy: Mapping[str, Any],
    *,
    mutation_record: Mapping[str, Any],
    adoption_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Install a mutation-machinery descendant only after exact external adoption."""
    adoption = validate_external_policy_adoption(adoption_record)
    if adoption["decision"] != "adopt":
        raise CognitivePolicyEvolutionError("a rejected policy descendant cannot mutate lineage state")
    parent = cognitive_search_controller.bound_policy(genesis)
    if parent is None:
        raise CognitivePolicyEvolutionError("lineage has no mutation machinery to evolve")
    if adoption["parent_policy_digest"] != parent["policy_digest"]:
        raise CognitivePolicyEvolutionError("external adoption was decided against another held policy")
    child, reproduced = cognitive_meta_mutation.validate_policy_mutation_record(
        mutation_record, parent_policy=parent
    )
    if reproduced["mutation_record_digest"] != adoption["mutation_record_digest"]:
        raise CognitivePolicyEvolutionError("external adoption names another meta-mutation")
    if child["policy_digest"] != adoption["candidate_policy_digest"]:
        raise CognitivePolicyEvolutionError("external adoption names another candidate policy")
    if cognitive_search.validate_policy(candidate_policy) != child:
        raise CognitivePolicyEvolutionError("supplied candidate policy does not reproduce")

    cognitive_search_controller._replace_or_add_policy(
        genesis,
        child,
        provenance_record=provenance(
            "external",
            produced_by="external cognitive mutation-machinery adoption authority",
            detail="policy adoption %s" % adoption["adoption_digest"],
        ),
    )
    return genesis.journal.append(
        "candidate_accepted",
        genesis.state["generation"],
        {
            "kind": "cognitive_mutation_machinery",
            "parent_policy_digest": parent["policy_digest"],
            "policy_digest": child["policy_digest"],
            "mutation_record_digest": reproduced["mutation_record_digest"],
            "adoption_digest": adoption["adoption_digest"],
            "new_state_digest": genesis.state["state_digest"],
        },
    )
