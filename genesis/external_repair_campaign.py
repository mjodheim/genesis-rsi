"""Trusted autonomous controller for external repair campaigns.

The mutable Genesis lineage may improve its repair machinery, but it never owns
benchmark selection, hidden evaluators, solution reveal timing, or the
scientific pass criterion.  This controller owns that boundary and persists a
checkpoint after every transition.

A negative result is therefore durably frozen before reveal can occur:

select -> prepare blind -> evaluate -> freeze negative -> diagnose/retain gap
       -> reveal -> learn -> validate machinery -> next fresh case

A positive result is validated and advances without revealing the human patch.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Protocol

from genesis.trust_root import digest_of

STATE_SCHEMA = "genesis-autonomous-external-repair-campaign-v1"
EVENT_SCHEMA = "genesis-autonomous-external-repair-event-v1"


class ExternalRepairCampaignError(RuntimeError):
    """Raised when campaign chronology or evidence boundaries are violated."""


class CampaignAdapter(Protocol):
    def select_case(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def prepare_blind(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def evaluate_blind(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def validate_success(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def diagnose_and_retain(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def reveal_solution(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def learn_from_solution(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...
    def validate_machinery(self, state: Mapping[str, Any]) -> Mapping[str, Any]: ...


def _unsigned_state(state: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(state)
    value.pop("state_digest", None)
    return value


def _state_digest(state: Mapping[str, Any]) -> str:
    return digest_of(_unsigned_state(state))


def validate_state(state: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(state, Mapping) or state.get("schema") != STATE_SCHEMA:
        raise ExternalRepairCampaignError("unsupported external campaign state")
    value = dict(state)
    recorded = str(value.get("state_digest") or "")
    if not recorded or recorded != _state_digest(value):
        raise ExternalRepairCampaignError("campaign state digest does not reproduce")
    if value.get("phase") not in {
        "select",
        "prepare",
        "evaluate",
        "validate_success",
        "diagnose",
        "reveal",
        "learn",
        "validate_machinery",
        "advance",
        "complete",
        "halted",
    }:
        raise ExternalRepairCampaignError("campaign phase is invalid")
    return value


def _with_digest(state: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(state)
    value.pop("state_digest", None)
    return {**value, "state_digest": digest_of(value)}


def _event(state: Mapping[str, Any], kind: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    events = list(state.get("events") or [])
    previous = str(events[-1]["event_digest"]) if events else ""
    unsigned = {
        "schema": EVENT_SCHEMA,
        "index": len(events),
        "kind": str(kind),
        "previous_event_digest": previous,
        "payload": dict(payload),
    }
    return {**unsigned, "event_digest": digest_of(unsigned)}


def _append(
    state: Mapping[str, Any],
    *,
    kind: str,
    payload: Mapping[str, Any],
    **changes: Any,
) -> dict[str, Any]:
    value = dict(state)
    events = list(value.get("events") or [])
    events.append(_event(value, kind, payload))
    value["events"] = events
    value.update(changes)
    return _with_digest(value)


def create_state(
    *,
    campaign_id: str,
    machinery: Mapping[str, Any],
    max_cases: int = 0,
    stop_after_successes: int = 0,
    attempted_case_ids: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    machinery_digest = str(machinery.get("machinery_digest") or "")
    if not campaign_id or not machinery_digest:
        raise ExternalRepairCampaignError("campaign and machinery identities are required")
    if max_cases < 0 or stop_after_successes < 0:
        raise ExternalRepairCampaignError("campaign limits may not be negative")
    payload = {
        "schema": STATE_SCHEMA,
        "campaign_id": str(campaign_id),
        "phase": "select",
        "generation": 0,
        "max_cases": int(max_cases),
        "stop_after_successes": int(stop_after_successes),
        "attempted_case_ids": [str(x) for x in attempted_case_ids],
        "success_count": 0,
        "machinery": dict(machinery),
        "current_case": None,
        "blind_freeze": None,
        "blind_result": None,
        "success_validation": None,
        "pre_reveal_learning": None,
        "solution_reveal": None,
        "learned_machinery": None,
        "machinery_validation": None,
        "events": [],
    }
    return _with_digest(payload)


class CampaignStore:
    """Atomic JSON checkpoint store for the trusted campaign controller."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def exists(self) -> bool:
        return self.path.is_file()

    def load(self) -> dict[str, Any]:
        return validate_state(json.loads(self.path.read_text(encoding="utf-8")))

    def save(self, state: Mapping[str, Any]) -> dict[str, Any]:
        clean = validate_state(state)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.path)
        return clean


def _blind_passed(result: Mapping[str, Any]) -> bool:
    return bool(result.get("scientific_gate_passed")) or result.get("winner") is not None


def _require_blind(record: Mapping[str, Any], *, field: str) -> None:
    if bool(record.get("human_fix_inspected")) or bool(record.get("issue_text_inspected")):
        raise ExternalRepairCampaignError(f"{field} crossed the hidden-solution boundary")


def _require_digest(record: Mapping[str, Any], *, field: str) -> str:
    value = str(record.get(field) or "")
    if not value:
        raise ExternalRepairCampaignError(f"record is missing required digest {field}")
    return value


def transition(state: Mapping[str, Any], adapter: CampaignAdapter) -> dict[str, Any]:
    """Execute exactly one durable campaign state transition."""
    current = validate_state(state)
    phase = str(current["phase"])

    if phase in {"complete", "halted"}:
        return current

    if phase == "select":
        case = dict(adapter.select_case(current))
        case_id = str(case.get("case_id") or "")
        if not case_id:
            raise ExternalRepairCampaignError("selected case has no identity")
        if case_id in set(current["attempted_case_ids"]):
            raise ExternalRepairCampaignError("adapter selected an already attempted case")
        return _append(
            current,
            kind="case_selected",
            payload={"case_id": case_id, "selection_digest": case.get("selection_digest")},
            phase="prepare",
            current_case=case,
        )

    if phase == "prepare":
        freeze = dict(adapter.prepare_blind(current))
        _require_blind(freeze, field="blind freeze")
        _require_digest(freeze, field="freeze_digest")
        return _append(
            current,
            kind="blind_frozen",
            payload={
                "case_id": current["current_case"]["case_id"],
                "freeze_digest": freeze["freeze_digest"],
                "machinery_digest": current["machinery"]["machinery_digest"],
            },
            phase="evaluate",
            blind_freeze=freeze,
        )

    if phase == "evaluate":
        result = dict(adapter.evaluate_blind(current))
        _require_blind(result, field="blind result")
        result_digest = str(result.get("result_digest") or digest_of(result))
        result["result_digest"] = result_digest
        passed = _blind_passed(result)
        return _append(
            current,
            kind="blind_result_frozen",
            payload={
                "case_id": current["current_case"]["case_id"],
                "result_digest": result_digest,
                "passed": passed,
            },
            phase="validate_success" if passed else "diagnose",
            blind_result=result,
        )

    if phase == "validate_success":
        validation = dict(adapter.validate_success(current))
        passed = bool(validation.get("passed"))
        event = _append(
            current,
            kind="positive_validated",
            payload={
                "case_id": current["current_case"]["case_id"],
                "passed": passed,
                "validation_digest": str(validation.get("validation_digest") or digest_of(validation)),
            },
            phase="advance" if passed else "halted",
            success_validation=validation,
            success_count=int(current["success_count"]) + (1 if passed else 0),
        )
        return event

    if phase == "diagnose":
        learning = dict(adapter.diagnose_and_retain(current))
        if bool(learning.get("solution_visible")):
            raise ExternalRepairCampaignError("pre-reveal diagnosis claims the solution was visible")
        memory = learning.get("machinery")
        if not isinstance(memory, Mapping) or not memory.get("machinery_digest"):
            raise ExternalRepairCampaignError("pre-reveal learning did not return durable machinery state")
        return _append(
            current,
            kind="negative_diagnosed_pre_reveal",
            payload={
                "case_id": current["current_case"]["case_id"],
                "result_digest": current["blind_result"]["result_digest"],
                "learning_digest": str(learning.get("learning_digest") or digest_of(learning)),
                "machinery_digest": memory["machinery_digest"],
            },
            phase="reveal",
            pre_reveal_learning=learning,
            machinery=dict(memory),
        )

    if phase == "reveal":
        if current.get("blind_result") is None or _blind_passed(current["blind_result"]):
            raise ExternalRepairCampaignError("solution reveal requires a frozen negative result")
        if current.get("pre_reveal_learning") is None:
            raise ExternalRepairCampaignError("solution reveal requires a retained pre-reveal diagnosis")
        reveal = dict(adapter.reveal_solution(current))
        _require_digest(reveal, field="solution_digest")
        return _append(
            current,
            kind="solution_revealed_after_negative",
            payload={
                "case_id": current["current_case"]["case_id"],
                "negative_result_digest": current["blind_result"]["result_digest"],
                "solution_digest": reveal["solution_digest"],
            },
            phase="learn",
            solution_reveal=reveal,
        )

    if phase == "learn":
        learned = dict(adapter.learn_from_solution(current))
        machinery = learned.get("machinery")
        if not isinstance(machinery, Mapping) or not machinery.get("machinery_digest"):
            raise ExternalRepairCampaignError("learning did not return candidate machinery")
        parent = str(machinery.get("parent_machinery_digest") or "")
        if parent and parent != str(current["machinery"]["machinery_digest"]):
            raise ExternalRepairCampaignError("learned machinery names the wrong parent")
        return _append(
            current,
            kind="machinery_candidate_learned",
            payload={
                "case_id": current["current_case"]["case_id"],
                "learning_digest": str(learned.get("learning_digest") or digest_of(learned)),
                "candidate_machinery_digest": machinery["machinery_digest"],
            },
            phase="validate_machinery",
            learned_machinery=learned,
        )

    if phase == "validate_machinery":
        validation = dict(adapter.validate_machinery(current))
        passed = bool(validation.get("passed"))
        next_machinery = current["machinery"]
        if passed:
            next_machinery = dict(current["learned_machinery"]["machinery"])
        return _append(
            current,
            kind="machinery_validation",
            payload={
                "case_id": current["current_case"]["case_id"],
                "passed": passed,
                "validation_digest": str(validation.get("validation_digest") or digest_of(validation)),
                "machinery_digest": next_machinery["machinery_digest"],
            },
            phase="advance" if passed else "halted",
            machinery_validation=validation,
            machinery=next_machinery,
        )

    if phase == "advance":
        case_id = str(current["current_case"]["case_id"])
        attempted = list(current["attempted_case_ids"])
        attempted.append(case_id)
        generation = int(current["generation"]) + 1
        max_cases = int(current["max_cases"])
        stop_after = int(current["stop_after_successes"])
        complete = (
            (max_cases > 0 and len(attempted) >= max_cases)
            or (stop_after > 0 and int(current["success_count"]) >= stop_after)
        )
        return _append(
            current,
            kind="case_closed",
            payload={
                "case_id": case_id,
                "generation": generation,
                "success_count": current["success_count"],
                "next_phase": "complete" if complete else "select",
            },
            phase="complete" if complete else "select",
            generation=generation,
            attempted_case_ids=attempted,
            current_case=None,
            blind_freeze=None,
            blind_result=None,
            success_validation=None,
            pre_reveal_learning=None,
            solution_reveal=None,
            learned_machinery=None,
            machinery_validation=None,
        )

    raise ExternalRepairCampaignError(f"unhandled campaign phase: {phase}")


def run(
    store: CampaignStore,
    adapter: CampaignAdapter,
    *,
    initial_state: Mapping[str, Any] | None = None,
    max_transitions: int = 10_000,
) -> dict[str, Any]:
    """Run/resume without host sequencing; checkpoint after every transition."""
    if max_transitions < 1:
        raise ValueError("max_transitions must be positive")
    if store.exists():
        state = store.load()
    elif initial_state is not None:
        state = store.save(initial_state)
    else:
        raise ExternalRepairCampaignError("campaign has no checkpoint or initial state")

    for _ in range(max_transitions):
        if state["phase"] in {"complete", "halted"}:
            break
        next_state = transition(state, adapter)
        state = store.save(next_state)
    return state
