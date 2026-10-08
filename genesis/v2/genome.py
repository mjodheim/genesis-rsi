"""Typed policy genome; Genesis may evolve weights, never evaluator authority.

A genome changes *how candidates are selected*, not the source being
evaluated. The grammar is deliberately finite and reviewable. This is an
evolvable decision policy rather than arbitrary executable self-modification.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from genesis.trust_root import digest_of

SCHEMA = "genesis-v2-search-genome-v1"
FEATURES = (
    "atomic",
    "source_evidence",
    "non_modifier",
    "rare_source",
    "semantic_operator",
)
MAX_ABS_WEIGHT = 6


class GenomeError(ValueError):
    """Rejected self-modification outside the admitted genome grammar."""


def _validate_weights(weights: Mapping[str, Any]) -> dict[str, int]:
    if not isinstance(weights, Mapping) or set(weights) != set(FEATURES):
        raise GenomeError("genome must supply exactly the admitted features")
    clean: dict[str, int] = {}
    for feature in FEATURES:
        weight = weights[feature]
        if isinstance(weight, bool) or not isinstance(weight, int):
            raise GenomeError(f"{feature}: weight must be an integer")
        if not -MAX_ABS_WEIGHT <= weight <= MAX_ABS_WEIGHT:
            raise GenomeError(f"{feature}: weight outside admitted bounds")
        clean[feature] = weight
    return clean


def make_seed(weights: Mapping[str, int] | None = None) -> dict[str, Any]:
    clean = _validate_weights(
        {feature: 0 for feature in FEATURES} if weights is None else weights
    )
    body = {
        "schema": SCHEMA,
        "generation": 0,
        "parent_digest": None,
        "mutation": None,
        "weights": clean,
        "can_change_trust_root": False,
        "can_execute_generated_source": False,
    }
    return {**body, "genome_digest": digest_of(body)}


def validate_genome(genome: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(genome, Mapping) or set(genome) != {
        "schema", "generation", "parent_digest", "mutation", "weights",
        "can_change_trust_root", "can_execute_generated_source", "genome_digest",
    }:
        raise GenomeError("invalid genome fields")
    if genome["schema"] != SCHEMA:
        raise GenomeError("unsupported genome schema")
    clean = _validate_weights(genome["weights"])
    generation = genome["generation"]
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
        raise GenomeError("invalid generation")
    if (genome["can_change_trust_root"] is not False
            or genome["can_execute_generated_source"] is not False):
        raise GenomeError("trust root and executable mutation are forbidden")
    if generation == 0:
        if genome["parent_digest"] is not None or genome["mutation"] is not None:
            raise GenomeError("seed must not pretend to have a parent")
    else:
        mutation = genome["mutation"]
        if not isinstance(genome["parent_digest"], str) or len(genome["parent_digest"]) != 64:
            raise GenomeError("descendant must name its parent digest")
        if (not isinstance(mutation, Mapping) or set(mutation) != {"feature", "delta"}
                or mutation["feature"] not in FEATURES
                or type(mutation["delta"]) is not int
                or mutation["delta"] not in (-1, 1)):
            raise GenomeError("descendant mutation outside admitted grammar")
    body = {key: value for key, value in genome.items() if key != "genome_digest"}
    if genome["genome_digest"] != digest_of(body):
        raise GenomeError("genome content digest mismatch")
    return dict(genome)


def mutate(parent: Mapping[str, Any], feature: str, delta: int) -> dict[str, Any]:
    baseline = validate_genome(parent)
    if feature not in FEATURES or type(delta) is not int or delta not in (-1, 1):
        raise GenomeError("unrecognized mutation")
    weights = dict(baseline["weights"])
    if not -MAX_ABS_WEIGHT <= weights[feature] + delta <= MAX_ABS_WEIGHT:
        raise GenomeError("mutation exceeds bounded search language")
    weights[feature] += delta
    body = {
        "schema": SCHEMA,
        "generation": baseline["generation"] + 1,
        "parent_digest": baseline["genome_digest"],
        "mutation": {"feature": feature, "delta": delta},
        "weights": weights,
        "can_change_trust_root": False,
        "can_execute_generated_source": False,
    }
    return validate_genome({**body, "genome_digest": digest_of(body)})


def neighborhood(parent: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Self-proposed, deterministic one-step mutations; no evaluator labels."""
    valid = validate_genome(parent)
    result = []
    for feature in FEATURES:
        for delta in (-1, 1):
            if -MAX_ABS_WEIGHT <= valid["weights"][feature] + delta <= MAX_ABS_WEIGHT:
                result.append(mutate(valid, feature, delta))
    return result


def rank(genome: Mapping[str, Any], candidate_features: Mapping[str, Any]) -> int:
    valid = validate_genome(genome)
    if not isinstance(candidate_features, Mapping) or set(candidate_features) != set(FEATURES):
        raise GenomeError("candidate features outside admitted grammar")
    score = 0
    for feature in FEATURES:
        value = candidate_features[feature]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 1:
            raise GenomeError(f"invalid observable {feature}")
        score += valid["weights"][feature] * value
    return score
