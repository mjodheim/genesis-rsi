"""Host-side application of externally decided cognitive architecture transitions.

The lineage may hold and execute an architecture, but it does not decide whether a proposed
architecture is better. This controller accepts only content-addressed external adoption/rollback
evidence and records the resulting state transition without exposing grader, measurements or
decision authority to mutable search machinery.
"""
from __future__ import annotations

from typing import Any, Mapping

from genesis import cognitive_architecture
from genesis import cognitive_adoption
from genesis import state as lineage_state
from genesis.trust_root import provenance

ARCHITECTURE_TOOL_NAME = "cognitive_architecture"
ARCHITECTURE_ROLE = "lineage_cognitive_architecture"


class CognitiveLineageAdoptionError(RuntimeError):
    """Raised when external evidence cannot authorize the requested lineage transition."""


def _architecture_tool(genesis) -> Mapping[str, Any] | None:
    matches = [
        tool for tool in genesis.state.get("tools", [])
        if tool.get("name") == ARCHITECTURE_TOOL_NAME and tool.get("role") == ARCHITECTURE_ROLE
    ]
    if len(matches) > 1:
        raise CognitiveLineageAdoptionError("lineage carries duplicate cognitive architectures")
    return matches[0] if matches else None


def held_architecture(genesis) -> dict[str, Any] | None:
    tool = _architecture_tool(genesis)
    if tool is None:
        return None
    try:
        architecture = cognitive_architecture.canonical_architecture(tool.get("artifact"))
    except cognitive_architecture.CognitiveArchitectureError as exc:
        raise CognitiveLineageAdoptionError(str(exc)) from exc
    recorded = tool.get("architecture_digest")
    actual = cognitive_architecture.architecture_digest(architecture)
    if recorded != actual:
        raise CognitiveLineageAdoptionError("held cognitive architecture identity does not reproduce")
    return architecture


def _replace_architecture(genesis, architecture: Any, *, evidence_digest: str) -> dict[str, Any]:
    canonical = cognitive_architecture.canonical_architecture(architecture)
    digest = cognitive_architecture.architecture_digest(canonical)
    tools = [
        tool for tool in genesis.state.get("tools", [])
        if not (tool.get("name") == ARCHITECTURE_TOOL_NAME and tool.get("role") == ARCHITECTURE_ROLE)
    ]
    tools.append({
        "name": ARCHITECTURE_TOOL_NAME,
        "role": ARCHITECTURE_ROLE,
        "artifact": canonical,
        "architecture_digest": digest,
        "evidence_digest": str(evidence_digest),
        "provenance": provenance(
            "external",
            produced_by="external cognitive adoption authority",
            detail="transition evidence %s" % evidence_digest,
        ),
    })
    genesis.state = lineage_state.create_state(
        body_digest=genesis.state["body_digest"],
        components=genesis.state["components"],
        vocabulary=genesis.state["vocabulary"],
        tools=tools,
        acquisitions=genesis.state["acquisitions"],
        observations=genesis.state["observations"],
        generation=genesis.state["generation"],
    )
    return canonical


def admit_seed_architecture(genesis, architecture: Any) -> bool:
    """Install the prospective seed architecture; replacement requires external adoption evidence."""
    canonical = cognitive_architecture.canonical_architecture(architecture)
    current = held_architecture(genesis)
    if current is not None:
        if current != canonical:
            raise CognitiveLineageAdoptionError(
                "lineage already holds a different cognitive architecture"
            )
        return False
    digest = cognitive_architecture.architecture_digest(canonical)
    _replace_architecture(genesis, canonical, evidence_digest="seed:" + digest)
    genesis.journal.append(
        "observation",
        genesis.state["generation"],
        {
            "arm": "cognitive_architecture_seed_admission",
            "architecture_digest": digest,
            "new_state_digest": genesis.state["state_digest"],
        },
    )
    return True


def apply_external_adoption(
    genesis, candidate_architecture: Any, *, adoption_record: Mapping[str, Any]
) -> dict[str, Any]:
    """Apply an externally supplied *adopt* record to the exact held parent architecture."""
    try:
        adoption = cognitive_adoption.validate_adoption_record(adoption_record)
    except cognitive_adoption.CognitiveAdoptionError as exc:
        raise CognitiveLineageAdoptionError(str(exc)) from exc
    if adoption["decision"] != "adopt":
        raise CognitiveLineageAdoptionError("a rejection record cannot mutate lineage architecture")
    current = held_architecture(genesis)
    if current is None:
        raise CognitiveLineageAdoptionError("lineage has no parent cognitive architecture")
    parent_digest = cognitive_architecture.architecture_digest(current)
    if parent_digest != adoption["parent_architecture_digest"]:
        raise CognitiveLineageAdoptionError("external adoption was decided against another parent")
    candidate = cognitive_architecture.canonical_architecture(candidate_architecture)
    candidate_digest = cognitive_architecture.architecture_digest(candidate)
    if candidate_digest != adoption["candidate_architecture_digest"]:
        raise CognitiveLineageAdoptionError("candidate architecture does not match external adoption")
    _replace_architecture(genesis, candidate, evidence_digest=adoption["adoption_digest"])
    return genesis.journal.append(
        "candidate_accepted",
        genesis.state["generation"],
        {
            "kind": "cognitive_architecture",
            "parent_architecture_digest": parent_digest,
            "architecture_digest": candidate_digest,
            "adoption_digest": adoption["adoption_digest"],
            "proposal_digest": adoption["proposal_digest"],
            "new_state_digest": genesis.state["state_digest"],
        },
    )


def apply_external_rollback(
    genesis,
    parent_architecture: Any,
    *,
    adoption_record: Mapping[str, Any],
    rollback_record: Mapping[str, Any],
) -> dict[str, Any]:
    """Restore the exact parent named by externally validated rollback evidence."""
    try:
        rollback = cognitive_adoption.validate_rollback_record(
            rollback_record, adoption_record=adoption_record
        )
    except cognitive_adoption.CognitiveAdoptionError as exc:
        raise CognitiveLineageAdoptionError(str(exc)) from exc
    current_tool = _architecture_tool(genesis)
    current = held_architecture(genesis)
    if current is None or current_tool is None:
        raise CognitiveLineageAdoptionError("lineage has no cognitive architecture to roll back")
    if cognitive_architecture.architecture_digest(current) != rollback["from_architecture_digest"]:
        raise CognitiveLineageAdoptionError("rollback does not start from the held architecture")
    if current_tool.get("evidence_digest") != rollback["adoption_digest"]:
        raise CognitiveLineageAdoptionError(
            "rollback does not target the adoption that installed the held architecture"
        )
    parent = cognitive_architecture.canonical_architecture(parent_architecture)
    parent_digest = cognitive_architecture.architecture_digest(parent)
    if parent_digest != rollback["restore_architecture_digest"]:
        raise CognitiveLineageAdoptionError("rollback payload is not the exact recorded parent")
    _replace_architecture(genesis, parent, evidence_digest=rollback["rollback_digest"])
    return genesis.journal.append(
        "rollback",
        genesis.state["generation"],
        {
            "kind": "cognitive_architecture",
            "rollback_digest": rollback["rollback_digest"],
            "adoption_digest": rollback["adoption_digest"],
            "restored_architecture_digest": parent_digest,
            "new_state_digest": genesis.state["state_digest"],
        },
    )
