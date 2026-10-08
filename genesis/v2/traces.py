"""Convert *already released* external failures to a sealed V2 development lab.

Only proposals that underwent independent evaluation are eligible for offline
counterfactual comparison. Never infer the outcome of untested candidates.

The feature extractor cannot read success labels and uses neither benchmark
solutions nor patched project sources. Imported projects are exposed historical
development data, *not* untouched holdouts, even when split train/check here.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

from genesis.trust_root import digest_of
from genesis.v2.genome import FEATURES

SCHEMA = "genesis-v2-released-development-catalogue-v1"


class TraceError(ValueError):
    pass


def _verify(record: Mapping[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise TraceError("expected signed evidence")
    obj = dict(record)
    digest = obj.pop(field, None)
    if digest_of(obj) != digest:
        raise TraceError(f"tampered {field}")
    return dict(record)


def from_released_batch(
    frozen: Mapping[str, Any], results: Mapping[str, Any]
) -> list[dict[str, Any]]:
    f = _verify(frozen, "freeze_digest")
    r = _verify(results, "result_digest")
    if (f.get("freeze_digest") != r.get("freeze_digest")
            or f.get("preregistration_digest") != r.get("preregistration_digest")):
        raise TraceError("results do not match pre-evaluation freeze")
    frozen_cases = {(case["project"], case["bug_id"]): case for case in f["all_cases"]}
    reported_cases = {(case["project"], case["bug_id"]): case for case in r["cases"]}
    if len(frozen_cases) != len(f["all_cases"]) or set(frozen_cases) != set(reported_cases):
        raise TraceError("missing or duplicate cases")
    records = []
    for (project, bug_id), case in frozen_cases.items():
        measured = reported_cases[(project, bug_id)]
        if measured["original_failure_count"] < 1:
            raise TraceError("only observed failures may be replayed")
        if measured["full_suite_valid_unique_candidates"] != 0:
            raise TraceError("this negative-only research corpus changed")
        results_by_key = {}
        for outcome in measured["outcomes"]:
            key = (outcome["path"], outcome["sha256"])
            if key in results_by_key:
                raise TraceError("duplicate outcome key")
            res = outcome["result"]
            if not isinstance(res.get("compiled"), bool) or not isinstance(
                res.get("full_suite_pass"), bool
            ):
                raise TraceError("untrustworthy validator result")
            if res["full_suite_pass"] and (not res["compiled"] or
                res.get("full_suite_ran") is not True or res.get("full_suite_failures") != 0):
                raise TraceError("full-suite proof missing for passing candidate")
            results_by_key[key] = res
        if len(results_by_key) != measured["distinct_candidates_evaluated"]:
            raise TraceError("disagreement on evaluated candidate count")
        hints = set(case.get("failure_source_hints", {}).get("matched_source_paths", []))
        hints.update(
            row["path"]
            for row in case.get("test_source_priority", {}).get("ranked_evidence", [])
            if row.get("score", 0) > 0
        )
        # Deterministic order: legacy candidates, then candidates not already
        # evaluated by that arm. This reproduces the legacy baseline at weight 0.
        arm_names = sorted(case["arms"], key=lambda x: (not x.startswith("legacy"), x))
        ordered = {}
        for arm in arm_names:
            for candidate in case["arms"][arm]["top"]:
                key = (candidate["path"], candidate["sha256"])
                if key not in results_by_key:
                    raise TraceError("frozen candidate has no validator result")
                if sha256(candidate["content_utf8"].encode()).hexdigest() != key[1]:
                    raise TraceError("candidate bytes differ from recorded digest")
                if key in ordered:
                    old = ordered[key]
                    if (old["depth"] != candidate["depth"]
                            or old["operators"] != candidate["operators"]):
                        raise TraceError("colliding candidate metadata")
                else:
                    ordered[key] = candidate
        if set(ordered) != set(results_by_key):
            raise TraceError("candidate result without a frozen index")
        counts = Counter(k[0] for k in ordered)
        catalogue = []
        for (path, candidate_hash), cand in ordered.items():
            operators = cand["operators"]
            if not isinstance(operators, list) or not all(
                isinstance(item, str) for item in operators
            ):
                raise TraceError("invalid operator provenance")
            semantic_tokens = (
                "guard", "iterator", "state", "null", "default", "parser",
                "expression", "range", "progress", "boundary", "calendar",
            )
            features = {
                "atomic": int(cand["depth"] == 1),
                "source_evidence": int(path in hints),
                "non_modifier": int(not any("modifier" in op for op in operators)),
                "rare_source": int(counts[path] <= 2),
                "semantic_operator": int(any(
                    any(token in op for token in semantic_tokens)
                    for op in operators
                )),
            }
            if set(features) != set(FEATURES):
                raise TraceError("feature schema drift")
            res = results_by_key[(path, candidate_hash)]
            catalogue.append({
                "id": digest_of({"source": path, "candidate_sha256": candidate_hash}),
                "features": features,
                "compiled": res["compiled"],
                "full_suite_pass": res["full_suite_pass"],
            })
        if not catalogue:
            raise TraceError("zero evaluated candidates")
        item = {
            "case_id": f"{project}-{bug_id}",
            "released_training_only": True,
            "candidate_count": len(catalogue),
            "candidates": catalogue,
            "source_freeze_digest": f["freeze_digest"],
            "source_result_digest": r["result_digest"],
        }
        records.append({**item, "case_digest": digest_of(item)})
    return records


def create_catalogue(batches: Sequence[tuple[Mapping[str, Any], Mapping[str, Any]]]) -> dict[str, Any]:
    if not (1 <= len(batches) <= 9):
        raise TraceError("bounded released batch count required")
    cases = []
    for frozen, result in batches:
        cases.extend(from_released_batch(frozen, result))
    if len(set(c["case_id"] for c in cases)) != len(cases):
        raise TraceError("project/bug identity duplicated across batches")
    body = {
        "schema": SCHEMA,
        "cases": cases,
        "case_count": len(cases),
        "contains_only_already_exposed_cases": True,
        "contains_untouched_holdouts": False,
        "candidate_pools_include_only_evaluated_proposals": True,
        "source_patches_stored": False,
    }
    return {**body, "catalogue_digest": digest_of(body)}


def validate_catalogue(catalogue: Mapping[str, Any]) -> dict[str, Any]:
    data = _verify(catalogue, "catalogue_digest")
    if set(data) != {
        "schema", "cases", "case_count", "contains_only_already_exposed_cases",
        "contains_untouched_holdouts", "candidate_pools_include_only_evaluated_proposals",
        "source_patches_stored", "catalogue_digest",
    } or data["schema"] != SCHEMA:
        raise TraceError("unexpected catalogue schema")
    if (data["contains_only_already_exposed_cases"] is not True
            or data["contains_untouched_holdouts"] is not False
            or data["candidate_pools_include_only_evaluated_proposals"] is not True
            or data["source_patches_stored"] is not False):
        raise TraceError("unacceptable evidence scope")
    if not (1 <= data["case_count"] <= 100) or len(data["cases"]) != data["case_count"]:
        raise TraceError("invalid case count")
    seen = set()
    for case in data["cases"]:
        item = {k: v for k, v in case.items() if k != "case_digest"}
        if digest_of(item) != case.get("case_digest"):
            raise TraceError("tampered case")
        if case["case_id"] in seen:
            raise TraceError("duplicate case")
        seen.add(case["case_id"])
        if case["released_training_only"] is not True or not case["candidates"]:
            raise TraceError("only released observations may enter the V2 lab")
        if len(case["candidates"]) != case["candidate_count"]:
            raise TraceError("candidate count mismatch")
        ids = set()
        for item in case["candidates"]:
            if item["id"] in ids:
                raise TraceError("duplicate candidate identity")
            ids.add(item["id"])
            if not isinstance(item["compiled"], bool) or not isinstance(
                item["full_suite_pass"], bool
            ):
                raise TraceError("invalid label")
            if item["full_suite_pass"] and not item["compiled"]:
                raise TraceError("test pass without compilation")
            if set(item["features"]) != set(FEATURES) or any(
                type(x) is not int or x not in (0, 1)
                for x in item["features"].values()
            ):
                raise TraceError("invalid observation features")
    return dict(data)
