"""Externally-authorized component promotion and rollback for Genesis G7.

Mutable Genesis may generate component descendants, but it does not own the
verdict.  This module provides the lineage-side mechanism that can *apply* a
content-addressed external decision while keeping candidate artifacts isolated
from the active pointer until adoption.

The active component is never represented by an in-place editable source file.
Every source artifact is immutable-by-identity in an artifact store and the
lineage state contains only the digest of the active artifact.  Exact rollback
therefore means restoring the recorded parent digest, not synthesizing an
inverse patch.

The journal is the existing Genesis append-only hash chain.  A persisted store
can be reloaded and replayed to reconstruct the active lineage.  Any mismatch in
artifact bytes, state digest, decision records or journal links is refused.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from genesis.journal import Journal, JournalError
from genesis.trust_root import canonical_bytes, digest_of

ARTIFACT_SCHEMA = "genesis-component-source-artifact-v1"
DECISION_SCHEMA = "genesis-component-promotion-decision-v1"
ROLLBACK_SCHEMA = "genesis-component-rollback-authority-v1"
STATE_SCHEMA = "genesis-component-lineage-state-v1"
STORE_SCHEMA = "genesis-component-lineage-store-v1"


class LineagePromotionError(RuntimeError):
    pass


def _nonempty(value: Any, name: str) -> str:
    text = str(value or "")
    if not text:
        raise LineagePromotionError(f"{name} is required")
    return text


def create_source_artifact(
    *,
    component_id: str,
    source_utf8: str,
    source_path: str,
    parent_artifact_digest: str | None,
    producer: str,
    proposal_digest: str,
) -> dict[str, Any]:
    if not isinstance(source_utf8, str) or not source_utf8:
        raise LineagePromotionError("source_utf8 must be non-empty text")
    payload = {
        "schema": ARTIFACT_SCHEMA,
        "component_id": _nonempty(component_id, "component_id"),
        "source_path": _nonempty(source_path, "source_path"),
        "source_utf8": source_utf8,
        "source_sha256": hashlib.sha256(source_utf8.encode("utf-8")).hexdigest(),
        "parent_artifact_digest": (
            _nonempty(parent_artifact_digest, "parent_artifact_digest")
            if parent_artifact_digest is not None
            else None
        ),
        "producer": _nonempty(producer, "producer"),
        "proposal_digest": _nonempty(proposal_digest, "proposal_digest"),
    }
    return {**payload, "artifact_digest": digest_of(payload)}


def validate_artifact(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != ARTIFACT_SCHEMA:
        raise LineagePromotionError("unsupported component artifact schema")
    payload = {k: v for k, v in record.items() if k != "artifact_digest"}
    if record.get("artifact_digest") != digest_of(payload):
        raise LineagePromotionError("component artifact digest does not reproduce")
    source = record.get("source_utf8")
    if not isinstance(source, str) or not source:
        raise LineagePromotionError("component artifact carries no source")
    if record.get("source_sha256") != hashlib.sha256(source.encode("utf-8")).hexdigest():
        raise LineagePromotionError("component artifact source identity does not reproduce")
    for field in ("component_id", "source_path", "producer", "proposal_digest"):
        _nonempty(record.get(field), field)
    return dict(record)


def create_external_decision(
    *,
    parent_artifact: Mapping[str, Any],
    candidate_artifact: Mapping[str, Any],
    decision: str,
    authority_digest: str,
    rule_digest: str,
    evaluator_digest: str,
    case_set_digest: str,
    parent_measurement_digest: str,
    candidate_measurement_digest: str,
    ablation_evidence_digest: str,
) -> dict[str, Any]:
    """Bind an externally supplied decision to exact lineage/evidence identities."""
    parent = validate_artifact(parent_artifact)
    candidate = validate_artifact(candidate_artifact)
    if decision not in {"adopt", "reject"}:
        raise LineagePromotionError("decision must be adopt or reject")
    if parent["component_id"] != candidate["component_id"]:
        raise LineagePromotionError("candidate targets another component")
    if candidate.get("parent_artifact_digest") != parent["artifact_digest"]:
        raise LineagePromotionError("candidate is not a descendant of the named parent")
    payload = {
        "schema": DECISION_SCHEMA,
        "decision": decision,
        "component_id": parent["component_id"],
        "parent_artifact_digest": parent["artifact_digest"],
        "candidate_artifact_digest": candidate["artifact_digest"],
        "authority_digest": _nonempty(authority_digest, "authority_digest"),
        "rule_digest": _nonempty(rule_digest, "rule_digest"),
        "evaluator_digest": _nonempty(evaluator_digest, "evaluator_digest"),
        "case_set_digest": _nonempty(case_set_digest, "case_set_digest"),
        "parent_measurement_digest": _nonempty(
            parent_measurement_digest, "parent_measurement_digest"
        ),
        "candidate_measurement_digest": _nonempty(
            candidate_measurement_digest, "candidate_measurement_digest"
        ),
        "ablation_evidence_digest": _nonempty(
            ablation_evidence_digest, "ablation_evidence_digest"
        ),
    }
    return {**payload, "decision_digest": digest_of(payload)}


def validate_decision(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != DECISION_SCHEMA:
        raise LineagePromotionError("unsupported promotion decision schema")
    payload = {k: v for k, v in record.items() if k != "decision_digest"}
    if record.get("decision_digest") != digest_of(payload):
        raise LineagePromotionError("promotion decision digest does not reproduce")
    if record.get("decision") not in {"adopt", "reject"}:
        raise LineagePromotionError("promotion decision is invalid")
    for field in (
        "component_id",
        "parent_artifact_digest",
        "candidate_artifact_digest",
        "authority_digest",
        "rule_digest",
        "evaluator_digest",
        "case_set_digest",
        "parent_measurement_digest",
        "candidate_measurement_digest",
        "ablation_evidence_digest",
    ):
        _nonempty(record.get(field), field)
    return dict(record)


def create_external_rollback(
    *,
    adoption_decision: Mapping[str, Any],
    authority_digest: str,
    reason_evidence_digest: str,
) -> dict[str, Any]:
    adoption = validate_decision(adoption_decision)
    if adoption["decision"] != "adopt":
        raise LineagePromotionError("rollback can only reverse an adopted descendant")
    payload = {
        "schema": ROLLBACK_SCHEMA,
        "component_id": adoption["component_id"],
        "adoption_decision_digest": adoption["decision_digest"],
        "from_artifact_digest": adoption["candidate_artifact_digest"],
        "restore_artifact_digest": adoption["parent_artifact_digest"],
        "authority_digest": _nonempty(authority_digest, "authority_digest"),
        "reason_evidence_digest": _nonempty(
            reason_evidence_digest, "reason_evidence_digest"
        ),
    }
    return {**payload, "rollback_digest": digest_of(payload)}


def validate_rollback(
    record: Mapping[str, Any], *, adoption_decision: Mapping[str, Any]
) -> dict[str, Any]:
    adoption = validate_decision(adoption_decision)
    if adoption["decision"] != "adopt":
        raise LineagePromotionError("rollback cannot bind to rejection")
    if not isinstance(record, Mapping) or record.get("schema") != ROLLBACK_SCHEMA:
        raise LineagePromotionError("unsupported rollback schema")
    payload = {k: v for k, v in record.items() if k != "rollback_digest"}
    if record.get("rollback_digest") != digest_of(payload):
        raise LineagePromotionError("rollback digest does not reproduce")
    checks = {
        "component_id": adoption["component_id"],
        "adoption_decision_digest": adoption["decision_digest"],
        "from_artifact_digest": adoption["candidate_artifact_digest"],
        "restore_artifact_digest": adoption["parent_artifact_digest"],
    }
    for field, expected in checks.items():
        if record.get(field) != expected:
            raise LineagePromotionError(f"rollback {field} does not match adoption")
    _nonempty(record.get("authority_digest"), "authority_digest")
    _nonempty(record.get("reason_evidence_digest"), "reason_evidence_digest")
    return dict(record)


def _state_payload(
    *,
    component_id: str,
    seed_artifact_digest: str,
    active_artifact_digest: str,
    generation: int,
) -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "component_id": component_id,
        "seed_artifact_digest": seed_artifact_digest,
        "active_artifact_digest": active_artifact_digest,
        "generation": int(generation),
    }


def _state(**kwargs: Any) -> dict[str, Any]:
    payload = _state_payload(**kwargs)
    return {**payload, "state_digest": digest_of(payload)}


def validate_state(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping) or record.get("schema") != STATE_SCHEMA:
        raise LineagePromotionError("unsupported lineage state schema")
    payload = {k: v for k, v in record.items() if k != "state_digest"}
    if record.get("state_digest") != digest_of(payload):
        raise LineagePromotionError("lineage state digest does not reproduce")
    if int(record.get("generation", -1)) < 0:
        raise LineagePromotionError("lineage generation is invalid")
    for field in ("component_id", "seed_artifact_digest", "active_artifact_digest"):
        _nonempty(record.get(field), field)
    return dict(record)


class ComponentLineageStore:
    """Persistent content-addressed component lineage with external promotion."""

    def __init__(self, root: str | Path, *, state: Mapping[str, Any], journal: Journal) -> None:
        self.root = Path(root)
        self.state = validate_state(state)
        self.journal = journal
        self._validate_full_store()

    @property
    def artifacts_dir(self) -> Path:
        return self.root / "artifacts"

    @property
    def decisions_dir(self) -> Path:
        return self.root / "decisions"

    @property
    def rollbacks_dir(self) -> Path:
        return self.root / "rollbacks"

    @property
    def state_path(self) -> Path:
        return self.root / "STATE.json"

    @property
    def journal_path(self) -> Path:
        return self.root / "JOURNAL.json"

    @property
    def manifest_path(self) -> Path:
        return self.root / "STORE.json"

    @classmethod
    def initialize(
        cls, root: str | Path, *, seed_artifact: Mapping[str, Any]
    ) -> "ComponentLineageStore":
        base = Path(root)
        if base.exists() and any(base.iterdir()):
            raise LineagePromotionError("lineage store must start empty")
        artifact = validate_artifact(seed_artifact)
        if artifact.get("parent_artifact_digest") is not None:
            raise LineagePromotionError("seed artifact may not name a parent")
        base.mkdir(parents=True, exist_ok=True)
        for child in ("artifacts", "decisions", "rollbacks"):
            (base / child).mkdir(parents=True, exist_ok=True)
        state = _state(
            component_id=artifact["component_id"],
            seed_artifact_digest=artifact["artifact_digest"],
            active_artifact_digest=artifact["artifact_digest"],
            generation=0,
        )
        journal = Journal()
        store = cls.__new__(cls)
        store.root = base
        store.state = state
        store.journal = journal
        store._write_artifact(artifact)
        store.journal.append(
            "seed",
            0,
            {
                "kind": "component_lineage",
                "component_id": artifact["component_id"],
                "artifact_digest": artifact["artifact_digest"],
                "state_digest": state["state_digest"],
            },
        )
        store.save()
        store._validate_full_store()
        return store

    @classmethod
    def load(cls, root: str | Path) -> "ComponentLineageStore":
        base = Path(root)
        try:
            state = json.loads((base / "STATE.json").read_text(encoding="utf-8"))
            journal = Journal.load(base / "JOURNAL.json")
            manifest = json.loads((base / "STORE.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, JournalError) as exc:
            raise LineagePromotionError(f"lineage store cannot be loaded: {exc}") from exc
        expected = digest_of({k: v for k, v in manifest.items() if k != "store_digest"})
        if manifest.get("schema") != STORE_SCHEMA or manifest.get("store_digest") != expected:
            raise LineagePromotionError("lineage store manifest does not reproduce")
        if manifest.get("state_digest") != state.get("state_digest"):
            raise LineagePromotionError("store manifest names another lineage state")
        if manifest.get("journal_head") != journal.head:
            raise LineagePromotionError("store manifest names another journal head")
        return cls(base, state=state, journal=journal)

    def _artifact_path(self, artifact_digest: str) -> Path:
        return self.artifacts_dir / f"{artifact_digest}.json"

    def _decision_path(self, decision_digest: str) -> Path:
        return self.decisions_dir / f"{decision_digest}.json"

    def _rollback_path(self, rollback_digest: str) -> Path:
        return self.rollbacks_dir / f"{rollback_digest}.json"

    @staticmethod
    def _atomic_write(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        raw = canonical_bytes(value) + b"\n"
        temporary = path.with_suffix(path.suffix + ".partial")
        temporary.write_bytes(raw)
        temporary.replace(path)

    def _write_artifact(self, artifact: Mapping[str, Any]) -> None:
        held = validate_artifact(artifact)
        path = self._artifact_path(held["artifact_digest"])
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != held:
                raise LineagePromotionError("artifact digest collision or tampering")
            return
        self._atomic_write(path, held)

    def _write_decision(self, decision: Mapping[str, Any]) -> None:
        held = validate_decision(decision)
        path = self._decision_path(held["decision_digest"])
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != held:
                raise LineagePromotionError("decision digest collision or tampering")
            return
        self._atomic_write(path, held)

    def _write_rollback(self, rollback: Mapping[str, Any]) -> None:
        path = self._rollback_path(str(rollback["rollback_digest"]))
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != dict(rollback):
                raise LineagePromotionError("rollback digest collision or tampering")
            return
        self._atomic_write(path, dict(rollback))

    def artifact(self, artifact_digest: str) -> dict[str, Any]:
        path = self._artifact_path(artifact_digest)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LineagePromotionError(f"artifact {artifact_digest} is unavailable") from exc
        held = validate_artifact(value)
        if held["artifact_digest"] != artifact_digest:
            raise LineagePromotionError("artifact path and artifact identity disagree")
        return held

    def decision(self, decision_digest: str) -> dict[str, Any]:
        path = self._decision_path(decision_digest)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LineagePromotionError(f"decision {decision_digest} is unavailable") from exc
        held = validate_decision(value)
        if held["decision_digest"] != decision_digest:
            raise LineagePromotionError("decision path and identity disagree")
        return held

    def active_artifact(self) -> dict[str, Any]:
        return self.artifact(self.state["active_artifact_digest"])

    def stage_candidate(self, candidate_artifact: Mapping[str, Any]) -> str:
        candidate = validate_artifact(candidate_artifact)
        if candidate["component_id"] != self.state["component_id"]:
            raise LineagePromotionError("candidate belongs to another component")
        if candidate.get("parent_artifact_digest") != self.state["active_artifact_digest"]:
            raise LineagePromotionError("candidate was not generated from the active artifact")
        self._write_artifact(candidate)
        self.journal.append(
            "candidate_proposed",
            self.state["generation"],
            {
                "kind": "component_source",
                "parent_artifact_digest": self.state["active_artifact_digest"],
                "candidate_artifact_digest": candidate["artifact_digest"],
                "proposal_digest": candidate["proposal_digest"],
            },
        )
        self.save()
        return candidate["artifact_digest"]

    def apply_external_decision(self, decision_record: Mapping[str, Any]) -> dict[str, Any]:
        decision = validate_decision(decision_record)
        if decision["component_id"] != self.state["component_id"]:
            raise LineagePromotionError("decision targets another component")
        if decision["parent_artifact_digest"] != self.state["active_artifact_digest"]:
            raise LineagePromotionError("decision was made against another active parent")
        candidate = self.artifact(decision["candidate_artifact_digest"])
        if candidate.get("parent_artifact_digest") != self.state["active_artifact_digest"]:
            raise LineagePromotionError("staged candidate lineage parent does not match active state")
        self._write_decision(decision)
        before = self.state["state_digest"]
        if decision["decision"] == "reject":
            entry = self.journal.append(
                "candidate_rejected",
                self.state["generation"],
                {
                    "kind": "component_source",
                    "decision_digest": decision["decision_digest"],
                    "parent_artifact_digest": self.state["active_artifact_digest"],
                    "candidate_artifact_digest": candidate["artifact_digest"],
                    "state_digest_unchanged": before,
                },
            )
            self.save()
            if self.state["state_digest"] != before:
                raise LineagePromotionError("rejection mutated active lineage state")
            return entry

        self.state = _state(
            component_id=self.state["component_id"],
            seed_artifact_digest=self.state["seed_artifact_digest"],
            active_artifact_digest=candidate["artifact_digest"],
            generation=int(self.state["generation"]) + 1,
        )
        entry = self.journal.append(
            "candidate_accepted",
            self.state["generation"],
            {
                "kind": "component_source",
                "decision_digest": decision["decision_digest"],
                "parent_artifact_digest": decision["parent_artifact_digest"],
                "candidate_artifact_digest": candidate["artifact_digest"],
                "previous_state_digest": before,
                "new_state_digest": self.state["state_digest"],
            },
        )
        self.save()
        return entry

    def apply_external_rollback(
        self,
        rollback_record: Mapping[str, Any],
        *,
        adoption_decision: Mapping[str, Any],
    ) -> dict[str, Any]:
        rollback = validate_rollback(
            rollback_record, adoption_decision=adoption_decision
        )
        if rollback["component_id"] != self.state["component_id"]:
            raise LineagePromotionError("rollback targets another component")
        if rollback["from_artifact_digest"] != self.state["active_artifact_digest"]:
            raise LineagePromotionError("rollback does not start from active artifact")
        restore = self.artifact(rollback["restore_artifact_digest"])
        before = self.state["state_digest"]
        self._write_rollback(rollback)
        self.state = _state(
            component_id=self.state["component_id"],
            seed_artifact_digest=self.state["seed_artifact_digest"],
            active_artifact_digest=restore["artifact_digest"],
            generation=int(self.state["generation"]) + 1,
        )
        entry = self.journal.append(
            "rollback",
            self.state["generation"],
            {
                "kind": "component_source",
                "rollback_digest": rollback["rollback_digest"],
                "adoption_decision_digest": rollback["adoption_decision_digest"],
                "from_artifact_digest": rollback["from_artifact_digest"],
                "restore_artifact_digest": restore["artifact_digest"],
                "previous_state_digest": before,
                "new_state_digest": self.state["state_digest"],
            },
        )
        self.save()
        return entry

    def save(self) -> None:
        self._atomic_write(self.state_path, self.state)
        self.journal.save(self.journal_path)
        manifest_payload = {
            "schema": STORE_SCHEMA,
            "component_id": self.state["component_id"],
            "state_digest": self.state["state_digest"],
            "journal_head": self.journal.head,
        }
        self._atomic_write(
            self.manifest_path,
            {**manifest_payload, "store_digest": digest_of(manifest_payload)},
        )

    def _validate_full_store(self) -> None:
        active = self.artifact(self.state["active_artifact_digest"])
        if active["component_id"] != self.state["component_id"]:
            raise LineagePromotionError("active artifact belongs to another component")
        self._replay()

    def _replay(self) -> str:
        active: str | None = None
        generation = 0
        for record in self.journal.entries():
            kind = record["kind"]
            payload = record["payload"]
            if kind == "seed" and payload.get("kind") == "component_lineage":
                if active is not None:
                    raise LineagePromotionError("lineage journal contains duplicate seed")
                active = str(payload["artifact_digest"])
                self.artifact(active)
                continue
            if kind == "candidate_proposed" and payload.get("kind") == "component_source":
                if payload.get("parent_artifact_digest") != active:
                    raise LineagePromotionError("proposed candidate does not descend from replayed active")
                self.artifact(str(payload["candidate_artifact_digest"]))
                continue
            if kind in {"candidate_accepted", "candidate_rejected"} and payload.get("kind") == "component_source":
                decision = self.decision(str(payload["decision_digest"]))
                if decision["parent_artifact_digest"] != active:
                    raise LineagePromotionError("decision does not bind to replayed active parent")
                if kind == "candidate_rejected":
                    if decision["decision"] != "reject":
                        raise LineagePromotionError("rejection journal entry carries adopt decision")
                    if payload.get("state_digest_unchanged") is None:
                        raise LineagePromotionError("rejection lacks unchanged-state evidence")
                    continue
                if decision["decision"] != "adopt":
                    raise LineagePromotionError("acceptance journal entry carries reject decision")
                active = decision["candidate_artifact_digest"]
                generation += 1
                continue
            if kind == "rollback" and payload.get("kind") == "component_source":
                path = self._rollback_path(str(payload["rollback_digest"]))
                try:
                    rollback = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise LineagePromotionError("rollback evidence is unavailable") from exc
                adoption = self.decision(str(rollback["adoption_decision_digest"]))
                rollback = validate_rollback(rollback, adoption_decision=adoption)
                if rollback["from_artifact_digest"] != active:
                    raise LineagePromotionError("rollback does not start from replayed active")
                active = rollback["restore_artifact_digest"]
                self.artifact(active)
                generation += 1
                continue
        if active is None:
            raise LineagePromotionError("lineage replay found no seed")
        if active != self.state["active_artifact_digest"]:
            raise LineagePromotionError("replayed active artifact differs from persisted state")
        if generation != int(self.state["generation"]):
            raise LineagePromotionError("replayed generation differs from persisted state")
        return active
