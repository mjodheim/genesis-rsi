"""Contrats inertes, sans exécution ni authentification des déclarations.

Publication AGPL après revue : vérifier la couverture de la délégation déjà
consultée avant publication. Aucune autorisation particulière n'est déduite du
registre, où aucune disposition privée applicable n'a été identifiée.
Une confidentialité exige une raison spécifique consignée.
La couverture de publication reste à vérifier.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass

VERSION = 1
_DIGEST = re.compile(r"[0-9a-f]{64}")

def _validate_json(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        return
    if type(value) is list:
        for item in value:
            _validate_json(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("JSON object keys must be strings")
            _validate_json(item)
        return
    raise ValueError("Unsupported JSON value")

def canonical_json_utf8(payload):
    """Encode a strict JSON object with sorted keys and fixed separators."""
    if type(payload) is not dict:
        raise ValueError("Expected a JSON object")
    try:
        _validate_json(payload)
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid JSON object") from exc

def _version(version):
    if type(version) is not int or version != VERSION:
        raise ValueError("Unknown contract version")

def _digest(value):
    if type(value) is not str or _DIGEST.fullmatch(value) is None:
        raise ValueError("Invalid SHA-256 digest")

@dataclass(frozen=True)
class JsonObjectEnvelope:
    version: int
    canonical_utf8: bytes
    sha256: str

    def __post_init__(self):
        _version(self.version)
        _digest(self.sha256)
        if type(self.canonical_utf8) is not bytes:
            raise ValueError("Expected UTF-8 bytes")
        try:
            payload = json.loads(self.canonical_utf8.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ValueError("Invalid JSON encoding") from exc
        if canonical_json_utf8(payload) != self.canonical_utf8:
            raise ValueError("Non-canonical JSON encoding")
        if hashlib.sha256(self.canonical_utf8).hexdigest() != self.sha256:
            raise ValueError("Inconsistent SHA-256 digest")

    @classmethod
    def create(cls, payload):
        encoded = canonical_json_utf8(payload)
        return cls(VERSION, encoded, hashlib.sha256(encoded).hexdigest())

    @property
    def payload(self):
        return json.loads(self.canonical_utf8.decode("utf-8"))

    def to_dict(self):
        return {
            "version": self.version,
            "payload": self.payload,
            "canonical_utf8": self.canonical_utf8.decode("utf-8"),
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) != {
            "version", "payload", "canonical_utf8", "sha256",
        }:
            raise ValueError("Invalid envelope fields")
        _version(data["version"])
        if type(data["canonical_utf8"]) is not str:
            raise ValueError("Expected canonical UTF-8 text")
        try:
            encoded = data["canonical_utf8"].encode("utf-8")
        except UnicodeError as exc:
            raise ValueError("Invalid UTF-8 text") from exc
        envelope = cls(data["version"], encoded, data["sha256"])
        if canonical_json_utf8(data["payload"]) != encoded:
            raise ValueError("Payload differs from canonical representation")
        return envelope

@dataclass(frozen=True)
class ExternalReceipt:
    """A declaration; neither judge authentication nor independence evidence.

    The digest checks internal consistency, not provenance or truthfulness.
    Budgets are declared consumption, not measurements made by this module.
    """

    version: int
    envelope: JsonObjectEnvelope

    def __post_init__(self):
        _version(self.version)
        if type(self.envelope) is not JsonObjectEnvelope:
            raise ValueError("Expected a JSON object envelope")
        payload = self.envelope.payload
        if set(payload) != {
            "policy_sha256", "task_id", "judge_id",
            "declared_result", "consumed_budget",
        }:
            raise ValueError("Invalid receipt fields")
        _digest(payload["policy_sha256"])
        for field in ("task_id", "judge_id"):
            if type(payload[field]) is not str or not payload[field]:
                raise ValueError("Expected a nonempty identifier")
        budget = payload["consumed_budget"]
        if type(budget) is not dict or set(budget) != {
            "models", "tokens", "proposals", "time_seconds",
        }:
            raise ValueError("Invalid budget fields")
        if type(budget["models"]) is not list or any(
            type(model) is not str for model in budget["models"]
        ):
            raise ValueError("Expected model identifiers")
        for field in ("tokens", "proposals"):
            if type(budget[field]) is not int or budget[field] < 0:
                raise ValueError("Expected a nonnegative integer budget")
        elapsed = budget["time_seconds"]
        if type(elapsed) not in (int, float) or elapsed < 0:
            raise ValueError("Expected nonnegative elapsed seconds")

    @classmethod
    def create(cls, *, policy_sha256, task_id, judge_id,
               declared_result, consumed_budget):
        return cls(VERSION, JsonObjectEnvelope.create({
            "policy_sha256": policy_sha256,
            "task_id": task_id,
            "judge_id": judge_id,
            "declared_result": declared_result,
            "consumed_budget": consumed_budget,
        }))

    @property
    def payload(self):
        return self.envelope.payload

    def to_dict(self):
        return {"version": self.version, "envelope": self.envelope.to_dict()}

    @classmethod
    def from_dict(cls, data):
        if type(data) is not dict or set(data) != {"version", "envelope"}:
            raise ValueError("Invalid receipt envelope fields")
        _version(data["version"])
        return cls(data["version"], JsonObjectEnvelope.from_dict(data["envelope"]))

@dataclass(frozen=True)
class BankExternalReceipt(ExternalReceipt):
    """Distinct bank-bearing declaration, with the historical version unchanged.

    Neither its digest nor context concordance authenticates provenance,
    establishes truth, or demonstrates judge independence.
    """

    def __post_init__(self):
        _version(self.version)
        if type(self.envelope) is not JsonObjectEnvelope:
            raise ValueError("Expected a JSON object envelope")
        JsonObjectEnvelope.__post_init__(self.envelope)
        payload = self.envelope.payload
        if set(payload) != {
            "policy_sha256", "bank_sha256", "task_id", "judge_id",
            "declared_result", "consumed_budget",
        }:
            raise ValueError("Invalid bank receipt fields")
        _digest(payload.pop("bank_sha256"))
        ExternalReceipt(self.version, JsonObjectEnvelope.create(payload))

    @classmethod
    def create(cls, *, policy_sha256, bank_sha256, task_id, judge_id,
               declared_result, consumed_budget):
        return cls(VERSION, JsonObjectEnvelope.create({
            "policy_sha256": policy_sha256,
            "bank_sha256": bank_sha256,
            "task_id": task_id,
            "judge_id": judge_id,
            "declared_result": declared_result,
            "consumed_budget": consumed_budget,
        }))

def validate_receipt_consistency(receipt, *, context=None):
    """Check a declaration against a caller-supplied external reference.

    Context must contain bank_sha256 and consumed_budget, including all four
    budget components. The caller must supply these expectations independently;
    no expected value is inferred from the receipt. Model order and repetitions
    are significant; elapsed seconds are compared numerically.

    Concordance proves neither authenticity, truth, nor independence. In
    particular, a concordant provenance declaration remains unauthenticated.
    Historical receipts remain readable but cannot pass this check.
    """
    if type(context) is not dict or set(context) != {
        "bank_sha256", "consumed_budget",
    }:
        raise ValueError("Expected complete external context")
    # Validate and detach the external reference before inspecting the receipt.
    context = json.loads(canonical_json_utf8(context).decode("utf-8"))
    _digest(context["bank_sha256"])
    budget = context["consumed_budget"]
    if type(budget) is not dict or set(budget) != {
        "models", "tokens", "proposals", "time_seconds",
    }:
        raise ValueError("Invalid budget fields")
    if type(budget["models"]) is not list or any(
        type(model) is not str for model in budget["models"]
    ):
        raise ValueError("Expected model identifiers")
    for field in ("tokens", "proposals"):
        if type(budget[field]) is not int or budget[field] < 0:
            raise ValueError("Expected a nonnegative integer budget")
    elapsed = budget["time_seconds"]
    if type(elapsed) not in (int, float) or elapsed < 0:
        raise ValueError("Expected nonnegative elapsed seconds")
    if type(receipt) is not BankExternalReceipt:
        raise ValueError("Expected a bank-bearing receipt")
    # Revalidate even objects whose frozen dataclass guard was bypassed.
    receipt.__post_init__()
    payload = receipt.payload
    if payload["bank_sha256"] != context["bank_sha256"]:
        raise ValueError("Bank differs from external context")
    for field in ("models", "tokens", "proposals", "time_seconds"):
        if payload["consumed_budget"][field] != budget[field]:
            raise ValueError("Budget differs from external context: " + field)
