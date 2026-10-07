"""Distill validated expensive repair traces into a cheap local specialist.

G8 treats model-produced passing repairs as training evidence, not as a runtime
dependency.  Only already-evaluated fallback records may contribute templates.
The resulting specialist is a content-addressed data artifact executed by the
existing deterministic patch-template engine with zero external model calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from genesis import patch_templates
from genesis.trust_root import digest_of

SPECIALIST_SCHEMA = "genesis-local-repair-specialist-v1"
SOURCE_SCHEMA = "mira-genesis-a6b-fallback-result-v1"


class DistillationError(ValueError):
    pass


def _validate_template(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema") != patch_templates.TEMPLATE_SCHEMA:
        raise DistillationError("source record contains an unsupported learned template")
    payload = {k: v for k, v in raw.items() if k != "template_digest"}
    if raw.get("template_digest") != digest_of(payload):
        raise DistillationError("learned template digest does not reproduce")
    if int(raw.get("external_model_calls_for_learning", -1)) != 0:
        raise DistillationError("template acquisition must be deterministic after validated evidence")
    return json.loads(json.dumps(dict(raw), sort_keys=True))


def validate_source_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema") != SOURCE_SCHEMA:
        raise DistillationError("unsupported distillation source record")
    payload = {k: v for k, v in raw.items() if k != "report_digest"}
    if raw.get("report_digest") != digest_of(payload):
        raise DistillationError("source fallback report digest does not reproduce")
    if raw.get("fallback_passed") is not True:
        raise DistillationError("only passing evaluated fallback evidence may be distilled")
    calls = int(raw.get("model_calls", 0))
    if calls < 1:
        raise DistillationError("source trace is not expensive external reasoning")
    templates = [_validate_template(item) for item in raw.get("learned_templates") or []]
    if not templates:
        raise DistillationError("source trace yielded no reusable deterministic template")
    result = dict(raw)
    result["learned_templates"] = templates
    return result


def distill_local_specialist(
    records: Sequence[Mapping[str, Any]],
    *,
    specialist_id: str = "repair-template-specialist",
) -> dict[str, Any]:
    if not records:
        raise DistillationError("distillation requires at least one validated source trace")

    admitted = [validate_source_record(record) for record in records]
    templates: list[dict[str, Any]] = []
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []

    for record in admitted:
        sources.append(
            {
                "task_id": int(record["task_id"]),
                "report_digest": str(record["report_digest"]),
                "model": str(record.get("model") or ""),
                "model_calls": int(record["model_calls"]),
                "cost_usd": (
                    float(record["cost_usd"]) if record.get("cost_usd") is not None else None
                ),
                "template_digests": [
                    str(template["template_digest"])
                    for template in record["learned_templates"]
                ],
            }
        )
        for template in record["learned_templates"]:
            digest = str(template["template_digest"])
            if digest in seen:
                continue
            seen.add(digest)
            templates.append(template)

    templates.sort(key=lambda item: str(item["template_digest"]))
    sources.sort(key=lambda item: (item["task_id"], item["report_digest"]))
    source_calls = sum(item["model_calls"] for item in sources)
    known_costs = [item["cost_usd"] for item in sources if item["cost_usd"] is not None]

    payload = {
        "schema": SPECIALIST_SCHEMA,
        "specialist_id": str(specialist_id),
        "mechanism": "deterministic_learned_line_rewrite_bundle",
        "templates": templates,
        "template_count": len(templates),
        "distilled_from": sources,
        "source_external_model_calls": source_calls,
        "source_cost_usd": sum(known_costs) if len(known_costs) == len(sources) else None,
        "runtime_external_model_calls": 0,
        "host_issue_specific_recipe": False,
    }
    return {**payload, "specialist_digest": digest_of(payload)}


def validate_specialist(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or raw.get("schema") != SPECIALIST_SCHEMA:
        raise DistillationError("unsupported specialist schema")
    payload = {k: v for k, v in raw.items() if k != "specialist_digest"}
    if raw.get("specialist_digest") != digest_of(payload):
        raise DistillationError("specialist digest does not reproduce")
    templates = [_validate_template(item) for item in raw.get("templates") or []]
    if int(raw.get("template_count", -1)) != len(templates):
        raise DistillationError("specialist template count is inconsistent")
    if int(raw.get("source_external_model_calls", 0)) < 1:
        raise DistillationError("specialist is not backed by expensive source reasoning")
    if int(raw.get("runtime_external_model_calls", -1)) != 0:
        raise DistillationError("local specialist must use zero external model calls at runtime")
    if raw.get("host_issue_specific_recipe") is not False:
        raise DistillationError("specialist may not declare issue-specific host recipes")
    return json.loads(json.dumps(dict(raw), sort_keys=True))


def distill_from_paths(paths: Iterable[str | Path], *, specialist_id: str = "repair-template-specialist") -> dict[str, Any]:
    records = [json.loads(Path(path).read_text(encoding="utf-8")) for path in paths]
    return distill_local_specialist(records, specialist_id=specialist_id)


def generate(
    root: str | Path,
    specialist: Mapping[str, Any],
    *,
    max_candidates: int = 64,
) -> dict[str, Any]:
    held = validate_specialist(specialist)
    generated = patch_templates.generate(
        root,
        held["templates"],
        max_candidates=max_candidates,
    )
    candidates = []
    for candidate in generated["candidates"]:
        item = json.loads(json.dumps(candidate, sort_keys=True))
        provenance = dict(item.get("provenance") or {})
        provenance.update(
            {
                "specialist_digest": held["specialist_digest"],
                "specialist_id": held["specialist_id"],
                "distilled_local_specialist": True,
                "external_model_calls": 0,
            }
        )
        item["provenance"] = provenance
        candidates.append(item)
    payload = {
        "schema": "genesis-local-specialist-candidates-v1",
        "specialist_digest": held["specialist_digest"],
        "candidate_count": len(candidates),
        "truncated": bool(generated["truncated"]),
        "external_model_calls": 0,
        "candidates": candidates,
    }
    return {**payload, "generation_digest": digest_of(payload)}
