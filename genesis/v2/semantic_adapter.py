"""Read-only V2.1 typed Java hypotheses as an opt-in repair family."""
from __future__ import annotations
from pathlib import Path
from collections.abc import Sequence
from typing import Any
from genesis.trust_root import digest_of
from genesis.v2.semantic_registry import default_registry

SCHEMA = "genesis-v21-semantic-hypothesis-candidates-v1"

def generate(root: str | Path, *, include_prefixes: Sequence[str] = (),
             max_candidates: int = 32) -> dict[str, Any]:
    if type(max_candidates) is not int or not 1 <= max_candidates <= 128:
        raise ValueError("V2.1 semantic budget outside 1..128")
    base=Path(root).resolve(strict=True)
    raw=tuple(str(p).replace("\\","/").strip("/") for p in include_prefixes)
    if not raw or len(raw)>32:
        raise ValueError("V2.1 requires explicit bounded source frontier")
    files=[]
    for value in raw:
        if not value.endswith(".java"):
            raise ValueError("V2.1 needs Java source paths, not directory scans")
        if value not in files:
            files.append(value)
    output=[]
    hypothesis_index=[]
    registry=default_registry()
    for relative in files:
        recorded=registry.propose(base,relative,max_hypotheses=32)
        suggestions=recorded["proposal_response"]
        for index,h in enumerate(suggestions["proposals"]):
            compiled=registry.compile(base,recorded,index)
            identifier={
                "schema":SCHEMA,"path":relative,
                "expected_sha256":compiled["source_sha256"],
                "candidate_sha256":compiled["candidate_sha256"],
                "hypothesis_digest":h["hypothesis_digest"],
            }
            digest=digest_of(identifier)
            output.append({
                "id":"v21-hypothesis-"+digest[:16],
                "candidate_digest":digest,
                "path":relative,
                "expected_sha256":compiled["source_sha256"],
                "operator":"v21_peer_contract_hypothesis",
                "content_utf8":compiled["content_utf8"],
                "detail":{
                    "mode":"typed_public_contract_synthesis",
                    "site_count":1,
                    "donor_quorum":h["donor_quorum"],
                    "hypothesis_digest":h["hypothesis_digest"],
                    "source_derived_only":True,
                    "evaluator_seen":False,
                },
                "external_model_calls":0,
            })
            hypothesis_index.append({
                "path":relative,"hypothesis_digest":h["hypothesis_digest"],
                "candidate_digest":digest,"donor_quorum":h["donor_quorum"],
            })
            if len(output)>=max_candidates:
                break
        if len(output)>=max_candidates:
            break
    body={
        "schema":SCHEMA,
        "candidate_count":len(output),
        "candidates":output,
        "hypothesis_index":hypothesis_index,
        "no_evaluator_used":True,
        "proposals_before_validation":True,
        "external_model_calls":0,
    }
    return {**body,"result_digest":digest_of(body)}
