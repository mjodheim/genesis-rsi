"""Execute G10 recursive chain profiles under one bounded candidate budget."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from genesis import patch_templates
from genesis.evolution import recursive_chain
from genesis.learning import distillation
from genesis.trust_root import digest_of

EXECUTION_SCHEMA = "genesis-g10-recursive-candidate-generation-v1"
_SCOPE_START = re.compile(r"^\s*//\s*scope:([A-Za-z0-9_-]+)\s*$")
_SCOPE_END = re.compile(r"^\s*//\s*endscope\s*$")


class RecursiveExecutionError(RuntimeError):
    pass


def _load_specialist(repository_root: Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    base = profile["base_system_profile"]
    override = (base.get("active_overrides") or {}).get("local_repair_specialist") or {}
    rel = str(override.get("artifact_path") or "")
    expected = str(override.get("specialist_digest") or "")
    if not rel or not expected:
        raise RecursiveExecutionError("G10 seed has no retained specialist artifact")
    freeze = json.loads((repository_root / rel).read_text(encoding="utf-8"))
    specialist = distillation.validate_specialist(freeze.get("specialist") or {})
    if specialist["specialist_digest"] != expected:
        raise RecursiveExecutionError("retained specialist digest mismatch")
    return specialist


def _scope_ids(lines: list[str]) -> list[str]:
    current = "__global__"
    result: list[str] = []
    for line in lines:
        start = _SCOPE_START.match(line.rstrip("\n"))
        if start:
            current = start.group(1)
            result.append(current)
            continue
        if _SCOPE_END.match(line.rstrip("\n")):
            result.append(current)
            current = "__global__"
            continue
        result.append(current)
    return result


def _macro_occurrences(
    path: Path,
    templates: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], dict[str, list[dict[str, Any]]]]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    scopes = _scope_ids(lines)
    found: dict[str, list[dict[str, Any]]] = {digest: [] for digest in templates}
    for index, line in enumerate(lines):
        for digest, template in templates.items():
            replacement = patch_templates.apply_template_to_line(line, template)
            if replacement is None:
                continue
            found[digest].append({
                "line_index": index,
                "scope_id": scopes[index],
                "replacement": replacement,
            })
    return lines, found


def _macro_candidate(
    *,
    path: Path,
    root: Path,
    lines: list[str],
    edits: list[dict[str, Any]],
    level: int,
    mode: str,
    template_digests: list[str],
) -> dict[str, Any] | None:
    if not edits:
        return None
    indexes = [int(edit["line_index"]) for edit in edits]
    if len(set(indexes)) != len(indexes):
        return None
    mutated = list(lines)
    for edit in edits:
        mutated[int(edit["line_index"])] = str(edit["replacement"])
    before = "".join(lines)
    after = "".join(mutated)
    if before == after:
        return None
    rel = path.relative_to(root).as_posix()
    scopes = sorted({str(edit["scope_id"]) for edit in edits})
    trace = {
        "capability_level": level,
        "mode": mode,
        "scope_ids": scopes,
        "template_digests": sorted(template_digests),
        "edited_line_indexes": sorted(indexes),
    }
    mutation = {
        "path": rel,
        "expected_sha256": hashlib.sha256(before.encode("utf-8")).hexdigest(),
        "expected_absent": False,
        "content_utf8": after,
    }
    payload = {
        "route": "recursive_macro",
        "mutations": [mutation],
        "recursive_trace": trace,
    }
    candidate_digest = digest_of(payload)
    return {
        **payload,
        "candidate_id": f"g10-macro-{candidate_digest[:16]}",
        "candidate_digest": candidate_digest,
        "provenance": {
            "generator": "g10_recursive_macro",
            "external_model_calls": 0,
            **trace,
        },
    }


def _global_pair_candidates(
    root: Path,
    templates: Mapping[str, Mapping[str, Any]],
    pair: list[str],
    *,
    level: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in patch_templates._eligible_files(root):
        lines, found = _macro_occurrences(path, templates)
        if not found.get(pair[0]) or not found.get(pair[1]):
            continue
        left = found[pair[0]][0]
        right = next(
            (item for item in found[pair[1]] if item["line_index"] != left["line_index"]),
            None,
        )
        if right is None:
            continue
        candidate = _macro_candidate(
            path=path,
            root=root,
            lines=lines,
            edits=[left, right],
            level=level,
            mode="global_pair",
            template_digests=pair,
        )
        if candidate:
            result.append(candidate)
    return result


def _scope_pair_candidates(
    root: Path,
    templates: Mapping[str, Mapping[str, Any]],
    pair: list[str],
    *,
    level: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in patch_templates._eligible_files(root):
        lines, found = _macro_occurrences(path, templates)
        scopes: list[str] = []
        for digest in pair:
            for item in found.get(digest, []):
                scope = str(item["scope_id"])
                if scope != "__global__" and scope not in scopes:
                    scopes.append(scope)
        for scope in scopes:
            left = next((item for item in found[pair[0]] if item["scope_id"] == scope), None)
            right = next(
                (
                    item
                    for item in found[pair[1]]
                    if item["scope_id"] == scope
                    and (left is None or item["line_index"] != left["line_index"])
                ),
                None,
            )
            if left is None or right is None:
                continue
            candidate = _macro_candidate(
                path=path,
                root=root,
                lines=lines,
                edits=[left, right],
                level=level,
                mode="scope_bound_pair",
                template_digests=pair,
            )
            if candidate:
                result.append(candidate)
    return result


def _iterated_scope_candidates(
    root: Path,
    templates: Mapping[str, Mapping[str, Any]],
    pair: list[str],
    *,
    level: int,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for path in patch_templates._eligible_files(root):
        lines, found = _macro_occurrences(path, templates)
        scopes: list[str] = []
        for item in found.get(pair[0], []):
            scope = str(item["scope_id"])
            if scope != "__global__" and scope not in scopes:
                scopes.append(scope)
        edits: list[dict[str, Any]] = []
        for scope in scopes:
            left = next((item for item in found[pair[0]] if item["scope_id"] == scope), None)
            right = next(
                (
                    item
                    for item in found[pair[1]]
                    if item["scope_id"] == scope
                    and (left is None or item["line_index"] != left["line_index"])
                ),
                None,
            )
            if left is not None and right is not None:
                edits.extend([left, right])
        if len(edits) < 4:
            continue
        candidate = _macro_candidate(
            path=path,
            root=root,
            lines=lines,
            edits=edits,
            level=level,
            mode="iterate_scope_pairs",
            template_digests=pair,
        )
        if candidate:
            result.append(candidate)
    return result


def _base_candidates(
    root: Path,
    specialist: Mapping[str, Any],
) -> list[dict[str, Any]]:
    generated = distillation.generate(root, specialist, max_candidates=512)
    result: list[dict[str, Any]] = []
    for item in generated["candidates"]:
        provenance = dict(item.get("provenance") or {})
        template_digest = str(provenance.get("template_digest") or "")
        trace = {
            "capability_level": 0,
            "mode": "base_single",
            "scope_ids": [],
            "template_digests": [template_digest] if template_digest else [],
            "base_template_digest": template_digest,
        }
        result.append({
            "route": "local_repair_specialist",
            "candidate_id": item["id"],
            "candidate_digest": item["candidate_digest"],
            "mutations": item["mutations"],
            "provenance": {**provenance, "external_model_calls": 0},
            "recursive_trace": trace,
        })
    return result


def generate_candidates(
    task_root: str | Path,
    profile: Mapping[str, Any],
    *,
    repository_root: str | Path,
    max_candidates: int,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 256:
        raise RecursiveExecutionError("max_candidates must be in [1, 256]")
    held = recursive_chain.validate_profile(profile)
    root = Path(task_root).resolve()
    repository = Path(repository_root).resolve()
    if not root.is_dir():
        raise RecursiveExecutionError("task root does not exist")

    specialist = _load_specialist(repository, held)
    capability = held["recursive_capability"]
    level = int(capability["level"])
    pair = list(capability.get("pair_template_digests") or [])
    template_map = {
        item["template_digest"]: item
        for item in specialist["templates"]
        if item["template_digest"] in set(pair)
    }
    if level > 0 and (len(pair) != 2 or set(template_map) != set(pair)):
        raise RecursiveExecutionError("recursive pair templates are not present in retained specialist")

    candidates: list[dict[str, Any]] = []
    if level >= 3:
        candidates.extend(_iterated_scope_candidates(root, template_map, pair, level=level))
    if level >= 2:
        candidates.extend(_scope_pair_candidates(root, template_map, pair, level=level))
    if level >= 1:
        candidates.extend(_global_pair_candidates(root, template_map, pair, level=level))
    candidates.extend(_base_candidates(root, specialist))

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        digest = str(candidate["candidate_digest"])
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(candidate)
        if len(unique) >= max_candidates:
            break

    route_counts: dict[str, int] = {}
    for candidate in unique:
        route = str(candidate["route"])
        route_counts[route] = route_counts.get(route, 0) + 1

    payload = {
        "schema": EXECUTION_SCHEMA,
        "profile_digest": held["profile_digest"],
        "campaign_generation": held["campaign_generation"],
        "capability_digest": capability["capability_digest"],
        "candidate_budget": max_candidates,
        "candidate_count": len(unique),
        "within_candidate_budget": len(unique) <= max_candidates,
        "route_candidate_counts": route_counts,
        "external_model_calls": 0,
        "candidates": unique,
    }
    return {**payload, "generation_digest": digest_of(payload)}
