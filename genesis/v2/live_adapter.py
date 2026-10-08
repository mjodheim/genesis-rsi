"""Opt-in V2 policy applied to actual V1 candidate proposals.

This only REORDERS already generated candidates. It never changes source
bytes, policy genomes cannot execute code, and evaluator decisions remain
outside this module. No exposure to compile/test labels at proposal time.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from genesis.trust_root import digest_of
from genesis.v2.genome import rank, validate_genome


def observable_features(
    candidates: Sequence[Mapping[str, Any]],
    *,
    prioritized_sources: Sequence[str] = (),
) -> list[dict[str, int]]:
    counts = Counter(c["path"] for c in candidates)
    hinted = set(prioritized_sources)
    tokens = (
        "guard", "iterator", "state", "null", "default", "parser",
        "expression", "range", "progress", "boundary", "calendar",
    )
    features = []
    for candidate in candidates:
        plan = candidate["plan"]
        ops = plan["component_operators"]
        if not isinstance(ops, list) or not all(isinstance(s, str) for s in ops):
            raise ValueError("malformed candidate operator provenance")
        features.append({
            "atomic": int(plan["depth"] == 1),
            "source_evidence": int(candidate["path"] in hinted),
            "non_modifier": int(not any("modifier" in x for x in ops)),
            "rare_source": int(counts[candidate["path"]] <= 2),
            "semantic_operator": int(any(
                any(token in operation for token in tokens) for operation in ops
            )),
        })
    return features


def rerank(
    candidates: Sequence[Mapping[str, Any]],
    genome: Mapping[str, Any],
    *,
    prioritized_sources: Sequence[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    valid = validate_genome(genome)
    candidate_list = [dict(x) for x in candidates]
    scores = [
        rank(valid, features) for features in observable_features(
            candidate_list, prioritized_sources=prioritized_sources,
        )
    ]
    ordered = sorted(
        range(len(candidate_list)),
        key=lambda position: (-scores[position], position),
    )
    output = []
    for index, source_pos in enumerate(ordered):
        item = {**candidate_list[source_pos], "logical_index": index}
        output.append(item)
    previous = sorted((
        str(c["path"]), sha256(str(c["content_utf8"]).encode()).hexdigest()
    ) for c in candidate_list)
    after = sorted((
        str(c["path"]), sha256(str(c["content_utf8"]).encode()).hexdigest()
    ) for c in output)
    if previous != after:
        raise ValueError("V2 policy must never change the candidate source set")
    detail = {
        "schema": "genesis-v2-optional-repair-ranking-v1",
        "genome_digest": valid["genome_digest"],
        "genome_generation": valid["generation"],
        "observed_candidate_count": len(output),
        "candidate_set_unchanged": True,
        "original_order_digest": digest_of([
            c["candidate_digest"] for c in candidate_list
        ]),
        "v2_order_digest": digest_of([c["candidate_digest"] for c in output]),
        "selection_policy_only": True,
        "policy_not_deployed_or_promoted": True,
    }
    return output, {**detail, "rerank_digest": digest_of(detail)}
