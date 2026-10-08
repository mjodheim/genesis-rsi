"""G11: bounded, falsifiable source-change hypotheses.

Hypotheses predict WHICH program behavior a candidate might change, not
whether that change repairs a defect. Predictions originate from compiler
condition ranges and the candidate's proposed edit; no expected answer,
human solution, or hidden test is consulted.

The language-neutral output is disposable advice. The independent validator
always controls whether a patch is correct.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from genesis.repair_ir import edits_from_variant
from genesis.trust_root import digest_of

SCHEMA = "genesis-g11-repair-hypotheses-v1"

# Bounded, intentionally conservative predicate grammar. Matching raw strings
# alone is unsafe: detection is limited to *compiler-verified condition spans*.
_PREDICATE = re.compile(
    r"(?<![\w$])(?P<subject>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\s*(?P<operator><=|>=|==|!=|<|>)\s*"
    r"(?P<limit>-?\d+|null)\b"
)


def _predicates(text: str) -> list[dict[str, str]]:
    return [m.groupdict() for m in _PREDICATE.finditer(text)]


def _probes(left: str, right: str) -> list[dict[str, Any]]:
    values: set[int] = set()
    for raw in (left, right):
        if raw != "null":
            number = int(raw)
            if abs(number) <= 100_000:
                values.update((number - 1, number, number + 1))
    if values:
        return [{"kind": "integer_boundary", "value": value}
                for value in sorted(values)[:9]]
    return [{"kind": "null"}, {"kind": "non_null_representative"}]


def infer_for_candidate(
    *,
    path: str | Path,
    understanding: Mapping[str, Any],
    candidate: Mapping[str, Any],
    max_hypotheses: int = 4,
) -> dict[str, Any]:
    """Inspect compiler-backed Java candidate changes without executing code.

    The target file is read from the buggy/working source tree; no human fix,
    expected output, benchmark annotations, or evaluator records are opened.
    For positional accuracy Java source must be ASCII; Unicode is refused
    until UTF-16 offsets can be translated correctly.
    """
    if max_hypotheses < 1 or max_hypotheses > 16:
        raise ValueError("max_hypotheses must be in [1,16]")
    source_path = Path(path).resolve(strict=True)
    original = source_path.read_text(encoding="utf-8")
    if (understanding.get("language") != "java"
            or not str(understanding.get("fidelity", "")).startswith("compiler_semantic")
            or understanding.get("diagnostics")
            or understanding.get("offset_unit") != "utf16_code_units"):
        raise ValueError("a clean compiler-derived Java analysis is required")
    if not original.isascii():
        raise ValueError("Java source contains non-ASCII, cannot match UTF-16 offsets safely")
    if hashlib.sha256(original.encode()).hexdigest() != understanding.get("source_digest"):
        raise ValueError("understanding source digest is stale")
    unsigned = {key: val for key, val in understanding.items() if key != "analysis_digest"}
    if understanding.get("analysis_digest") != digest_of(unsigned):
        raise ValueError("understanding report integrity mismatch")
    mutated = candidate.get("content_utf8")
    if not isinstance(mutated, str) or len(mutated) > 512_000:
        raise ValueError("candidate source is missing or too large")
    if candidate.get("expected_sha256") not in (None, "", hashlib.sha256(original.encode()).hexdigest()):
        raise ValueError("candidate does not target current source")
    candidate_hash = hashlib.sha256(mutated.encode()).hexdigest()
    edits = edits_from_variant(
        path=source_path.name,
        original=original,
        mutated=mutated,
        operator=str(candidate.get("operator") or "unknown"),
        component_digest=str(candidate.get("candidate_digest") or candidate_hash),
    )
    hypotheses: list[dict[str, Any]] = []
    for edit in edits:
        for branch in understanding.get("details", {}).get("branches", ()):
            start, end = branch.get("condition_start"), branch.get("condition_end")
            if (not isinstance(start, int) or not isinstance(end, int)
                    or start < 0 or end <= start or end > len(original)):
                continue
            # Only a local edit strictly WITHIN the compiler's predicate range
            # supports an unambiguous old/new predicate comparison.
            if not (start <= edit.start <= edit.end <= end):
                continue
            before = original[start:end]
            replacement = edit.replacement
            after = before[: edit.start - start] + replacement + before[edit.end - start:]
            old_predicates = _predicates(before)
            new_predicates = _predicates(after)
            if len(old_predicates) != 1 or len(new_predicates) != 1:
                continue
            before_p, after_p = old_predicates[0], new_predicates[0]
            if before_p == after_p:
                continue
            if before_p["subject"] != after_p["subject"]:
                continue
            if "null" in (before_p["limit"], after_p["limit"]):
                kind = "null_guard_behavior_change"
            elif before_p["operator"] != after_p["operator"]:
                kind = "comparison_boundary_behavior_change"
            elif before_p["limit"] != after_p["limit"]:
                kind = "numeric_threshold_behavior_change"
            else:
                continue
            context = str(branch.get("kind") or "")
            # Even if the condition appears inside a loop, we don't assert
            # algorithmic complexity: loop bounds need their own proof.
            payload = {
                "schema": SCHEMA,
                "kind": kind,
                "language": "java",
                "candidate_sha256": candidate_hash,
                "source_analysis_digest": understanding["analysis_digest"],
                "source_sha256": understanding["source_digest"],
                "origin": "compiler_verified_condition_span",
                "node_kind": context,
                "condition_start": start,
                "condition_end": end,
                "changed_span_start": edit.start,
                "changed_span_end": edit.end,
                "subject": before_p["subject"],
                "before_comparison": {
                    "operator": before_p["operator"],
                    "limit": before_p["limit"],
                },
                "after_comparison": {
                    "operator": after_p["operator"],
                    "limit": after_p["limit"],
                },
                "suggested_probe_values": _probes(before_p["limit"], after_p["limit"]),
                "prediction": "This candidate may alter outcomes near the indicated guard boundary.",
                "falsification": "Run independent public assertions around the boundary; reject if required behavior is violated.",
                "correct_fix_proven": False,
                "causal_bug_origin_proven": False,
                "confidence": "structural_only",
                "hidden_tests_seen": False,
            }
            hypotheses.append({**payload, "hypothesis_digest": digest_of(payload)})
            if len(hypotheses) >= max_hypotheses:
                break
        if len(hypotheses) >= max_hypotheses:
            break
    result = {
        "schema": "genesis-g11-hypothesis-bundle-v1",
        "candidate_sha256": candidate_hash,
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses,
        "proves_repair": False,
    }
    return {**result, "bundle_digest": digest_of(result)}


def hypotheses_for_candidates(
    *,
    root: Path,
    reports: Mapping[str, Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    max_candidates: int = 24,
) -> dict[str, Any]:
    """Produce annotations for top candidates, without changing their order."""
    if max_candidates < 1 or max_candidates > 128:
        raise ValueError("max_candidates must be in [1,128]")
    output = []
    errors = []
    for rank, candidate in enumerate(candidates[:max_candidates], 1):
        relative = str(candidate.get("path") or "")
        report = reports.get(relative)
        if not report:
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            continue
        try:
            bundle = infer_for_candidate(path=path, understanding=report, candidate=candidate)
        except (ValueError, OSError) as exc:
            errors.append({"rank": rank, "reason": type(exc).__name__})
            continue
        if bundle["hypothesis_count"]:
            output.append({
                "rank": rank,
                "candidate_sha256": bundle["candidate_sha256"],
                "hypotheses": bundle["hypotheses"],
            })
    payload = {
        "schema": "genesis-g11-hypothesis-index-v1",
        "inspected_top_k": min(max_candidates, len(candidates)),
        "annotated_candidate_count": len(output),
        "hypothesis_count": sum(len(r["hypotheses"]) for r in output),
        "annotations": output,
        "errors": errors,
        "ranking_altered": False,
        "external_model_calls": 0,
    }
    return {**payload, "index_digest": digest_of(payload)}
