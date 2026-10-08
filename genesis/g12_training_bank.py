"""Merge independently verified *released training* operators into reusable bank.

Each real case's A6c lineage remains immutable. The derived merged snapshot
is explicitly a new seed (not a continuation of either source lineage).
Its provenance includes both G12 test receipts and original memory digests.
The bank is opt-in only and never counts as unseen evaluation evidence.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from genesis.learning import self_extension
from genesis.trust_root import digest_of

SCHEMA = "genesis-g12-derived-training-operator-bank-v1"


def create_training_bank(
    released_rounds: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]],
) -> dict[str, Any]:
    if not (1 <= len(released_rounds) <= 32):
        raise ValueError("training bank requires 1..32 released rounds")
    accepted: dict[str, dict[str, Any]] = {}
    sources: dict[str, dict[str, Any]] = {}
    for raw_receipt, raw_memory in released_rounds:
        receipt = dict(raw_receipt)
        checksum = receipt.pop("receipt_digest", None)
        if not checksum or digest_of(receipt) != checksum:
            raise ValueError("training receipt checksum invalid")
        if (receipt.get("source_role") != "released_training"
                or receipt.get("human_patch_accessed") is not False
                or receipt.get("independent_new_bug_successes") != 0
                or receipt.get("novel_semantic_operator_autonomously_invented") is not False):
            raise ValueError("only evaluated development case operators may be banked")
        acquisition = receipt.get("validated_operator_acquisition")
        if not acquisition or not acquisition.get("replay_verified_on_training_source"):
            raise ValueError("unverified structural operator acquisition")
        if not any(a.get("validated_full_suite") is True
                   and a.get("outcome", {}).get("full_suite_pass") is True
                   and a.get("outcome", {}).get("full_suite_failures") == 0
                   for a in receipt.get("attempts", ())):
            raise ValueError("a full project test pass is required for training")
        memory = self_extension.validate_memory(raw_memory)
        if memory["memory_digest"] != receipt.get("memory_digest"):
            raise ValueError("memory receipt digest does not match stored operator")
        if not any(e.get("kind")=="operator_acquired" for e in memory["events"]):
            raise ValueError("memory lacks causal acquisition event")
        expected=set(acquisition.get("operator_digests", ()))
        found={item["operator_digest"]:item for item in memory["operators"]}
        if not expected or not expected.issubset(found):
            raise ValueError("acquired operator is not present in memory")
        if checksum in sources:
            raise ValueError("the same training round was supplied twice")
        sources[checksum]={
            "receipt_digest":checksum,
            "original_memory_digest":memory["memory_digest"],
            "original_memory_generation":memory["generation"],
            "acquired_operator_digests":sorted(expected),
            "source_role":"released_training",
            "independently_validated_new_bug":False,
        }
        for digest in expected:
            candidate=found[digest]
            if digest in accepted and accepted[digest] != candidate:
                raise ValueError("two different operators share a digest")
            accepted[digest]=candidate

    # The canonical newly seeded bank preserves all original operator objects,
    # but does NOT pretend its own generation=0 is a recursive improvement.
    merged=self_extension.create_memory(operators=list(accepted.values()))
    payload={
        "schema":SCHEMA,
        "sources":[sources[k] for k in sorted(sources)],
        "released_training_rounds":len(sources),
        "learned_operator_count":len(accepted),
        "retained_memory":merged,
        "merged_seed_is_not_a_continuation_of_source_lineages":True,
        "operator_semantics_preexisting_human_authored_generators":True,
        "new_independent_full_suite_successes":0,
        "g12_reuse_requires_explicit_opt_in":True,
    }
    return {**payload,"bank_digest":digest_of(payload)}


def validate_training_bank(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema") != SCHEMA:
        raise ValueError("unsupported training bank schema")
    receipt={k:v for k,v in value.items() if k!="bank_digest"}
    if value.get("bank_digest") != digest_of(receipt):
        raise ValueError("invalid bank digest")
    memory=self_extension.validate_memory(value["retained_memory"])
    sources=value.get("sources")
    if not isinstance(sources,list) or any(
        item.get("source_role") != "released_training"
        or item.get("original_memory_generation") != 2
        or not item.get("acquired_operator_digests")
        or item.get("independently_validated_new_bug") is not False
        for item in sources
    ):
        raise ValueError("training bank has missing or unreleased source provenance")
    proven={digest for item in sources for digest in item["acquired_operator_digests"]}
    retained={item["operator_digest"] for item in memory["operators"]}
    if proven != retained:
        raise ValueError("bank has missing or unproven structural operator provenance")
    if not (value.get("merged_seed_is_not_a_continuation_of_source_lineages") is True
            and value.get("new_independent_full_suite_successes") == 0
            and value.get("g12_reuse_requires_explicit_opt_in") is True
            and value.get("learned_operator_count")==len(memory["operators"])
            and value.get("released_training_rounds")==len(value["sources"])):
        raise ValueError("training bank's scientific scope is inconsistent")
    return dict(value)
