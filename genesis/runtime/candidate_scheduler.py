"""Bounded candidate scheduling and composition for the autonomous RSI track.

A6 showed that adding memory can make search worse when one generator is simply
prepended ahead of all others. This module fixes that failure mode without
adding task-specific repair knowledge:

* candidates outside the frozen target scope are discarded;
* generator families receive deterministic weighted interleaving;
* compatible single-site scalar edits may be composed into bounded multi-site
  candidates.

The scheduler is an execution-policy layer only. Evaluators still determine
whether any candidate is correct.
"""
from __future__ import annotations

from collections import defaultdict, deque
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from genesis.trust_root import digest_of

SCHEDULE_SCHEMA = "genesis-fair-candidate-schedule-v1"
COORDINATED_SCHEMA = "genesis-coordinated-scalar-candidates-v2"

DEFAULT_WEIGHTS = {
    "learned_coordinated": 3,
    "scalar": 4,
    "learned": 1,
    "coordinated": 1,
    "retained": 1,
    "exemplar": 1,
}


def _in_scope(path: str, prefixes: Sequence[str]) -> bool:
    normalized = str(path).strip("/")
    wanted = tuple(str(p).strip("/") for p in prefixes if str(p).strip("/"))
    if not wanted:
        return True
    return any(normalized == p or normalized.startswith(p + "/") for p in wanted)


def filter_target_scope(
    candidates: Sequence[Mapping[str, Any]],
    prefixes: Sequence[str],
) -> list[dict[str, Any]]:
    """Keep candidates whose every mutation path is inside the frozen scope."""
    kept: list[dict[str, Any]] = []
    for raw in candidates:
        candidate = dict(raw)
        mutations = list(candidate.get("mutations") or [])
        if not mutations:
            continue
        if all(_in_scope(str(m.get("path", "")), prefixes) for m in mutations):
            kept.append(candidate)
    return kept


def _candidate_fingerprint(candidate: Mapping[str, Any]) -> str:
    mutations = [
        {
            "path": m.get("path"),
            "expected_sha256": m.get("expected_sha256"),
            "content_utf8": m.get("content_utf8"),
        }
        for m in (candidate.get("mutations") or [])
    ]
    return digest_of(mutations)


def fair_schedule(
    families: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    budget: int,
    weights: Mapping[str, int] = DEFAULT_WEIGHTS,
) -> dict[str, Any]:
    """Deterministically interleave generator families with bounded weights."""
    if budget < 1:
        raise ValueError("budget must be positive")

    queues = {
        name: deque(dict(item) for item in families.get(name, ()))
        for name in weights
    }
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    family_counts: dict[str, int] = {name: 0 for name in weights}

    while len(output) < budget and any(queues[name] for name in queues):
        made_progress = False
        for name, weight in weights.items():
            for _ in range(max(0, int(weight))):
                if len(output) >= budget:
                    break
                queue = queues[name]
                while queue:
                    candidate = queue.popleft()
                    fingerprint = _candidate_fingerprint(candidate)
                    if fingerprint in seen:
                        continue
                    seen.add(fingerprint)
                    output.append(candidate)
                    family_counts[name] += 1
                    made_progress = True
                    break
        if not made_progress:
            break

    payload = {
        "schema": SCHEDULE_SCHEMA,
        "budget": budget,
        "weights": dict(weights),
        "family_input_counts": {
            name: len(families.get(name, ())) for name in weights
        },
        "family_scheduled_counts": family_counts,
        "scheduled_count": len(output),
        "external_model_calls": 0,
        "candidates": output,
    }
    return {**payload, "schedule_digest": digest_of(payload)}



def compose_learned_candidates(
    learned_candidates: Sequence[Mapping[str, Any]],
    *,
    max_sites: int = 2,
    max_candidates: int = 128,
) -> dict[str, Any]:
    """Compose prior learned-template applications across distinct files."""
    if max_sites != 2:
        raise ValueError("learned-template composition currently supports pairs only")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in learned_candidates:
        candidate = dict(raw)
        provenance = candidate.get("provenance") or {}
        template_digest = str(provenance.get("template_digest", ""))
        mutations = list(candidate.get("mutations") or [])
        if not template_digest or len(mutations) != 1:
            continue
        groups[template_digest].append(candidate)

    out: list[dict[str, Any]] = []
    for template_digest in sorted(groups):
        candidates = sorted(
            groups[template_digest],
            key=lambda c: (
                str(c["mutations"][0]["path"]),
                str(c.get("id", "")),
            ),
        )
        for left, right in combinations(candidates, 2):
            lm = left["mutations"][0]
            rm = right["mutations"][0]
            if str(lm["path"]) == str(rm["path"]):
                continue
            mutations = sorted([dict(lm), dict(rm)], key=lambda m: str(m["path"]))
            payload = {
                "template_digest": template_digest,
                "source_candidate_ids": [left["id"], right["id"]],
                "mutations": mutations,
            }
            cd = digest_of(payload)
            out.append(
                {
                    "id": f"learned-coordinated-{cd[:16]}",
                    "label": f"learned_coordinated:{template_digest[:12]}:2files",
                    "provenance": {
                        "generator": "coordinated_learned_template",
                        "operator": "learned_template",
                        "template_digest": template_digest,
                        "coordination_size": 2,
                        "strategy_origin": "prior_passing_evaluated_patch",
                        "external_model_calls": 0,
                    },
                    "mutations": mutations,
                    "candidate_digest": cd,
                }
            )
            if len(out) >= max_candidates:
                return {
                    "schema": "genesis-coordinated-learned-template-candidates-v1",
                    "candidate_count": len(out),
                    "truncated": True,
                    "external_model_calls": 0,
                    "candidates": out,
                }

    return {
        "schema": "genesis-coordinated-learned-template-candidates-v1",
        "candidate_count": len(out),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": out,
    }

def _apply_sites(
    root: Path,
    sites: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_path: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for site in sites:
        by_path[str(site["path"])].append(site)

    mutations: list[dict[str, Any]] = []
    for rel in sorted(by_path):
        path = root / rel
        original = path.read_text(encoding="utf-8")
        expected = str(by_path[rel][0]["expected_sha256"])
        current = original
        for site in sorted(by_path[rel], key=lambda x: int(x["start"]), reverse=True):
            start = int(site["start"])
            end = int(site["end"])
            before = str(site["before"])
            after = str(site["after"])
            if original[start:end] != before:
                raise ValueError(f"scalar site no longer matches baseline: {rel}:{start}")
            current = current[:start] + after + current[end:]
        mutations.append(
            {
                "path": rel,
                "expected_sha256": expected,
                "expected_absent": False,
                "content_utf8": current,
            }
        )
    return mutations


def _combo_sort_key(chosen: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    paths = [str(site["path"]) for site in chosen]
    cross_file_first = 0 if len(set(paths)) > 1 else 1
    coordinates = tuple(
        (str(site["path"]), int(site["start"]), int(site["end"]))
        for site in chosen
    )
    return (cross_file_first, coordinates)


def _emit_group_combinations(
    root: Path,
    *,
    operator: str,
    before: str,
    after: str,
    context: str,
    sites: Sequence[Mapping[str, Any]],
    max_sites: int,
    seen_site_sets: set[tuple[tuple[str, int, int], ...]],
    out: list[dict[str, Any]],
    max_candidates: int,
) -> bool:
    if len(sites) < 2:
        return False

    upper = min(max_sites, len(sites))
    for size in range(2, upper + 1):
        combos = list(combinations(sites, size))
        combos.sort(key=_combo_sort_key)
        for chosen in combos:
            site_key = tuple(
                sorted(
                    (
                        str(site["path"]),
                        int(site["start"]),
                        int(site["end"]),
                    )
                    for site in chosen
                )
            )
            if site_key in seen_site_sets:
                continue
            seen_site_sets.add(site_key)
            mutations = _apply_sites(root, chosen)
            payload = {
                "operator": operator,
                "before": before,
                "after": after,
                "context": context,
                "sites": [
                    {
                        "path": site["path"],
                        "start": site["start"],
                        "end": site["end"],
                    }
                    for site in chosen
                ],
                "mutations": mutations,
            }
            cd = digest_of(payload)
            out.append(
                {
                    "id": f"coordinated-{cd[:16]}",
                    "label": (
                        f"coordinated_{operator}:{before}->{after}:"
                        f"{size}sites:{'context' if context else 'broad'}"
                    ),
                    "provenance": {
                        "generator": "coordinated_scalar_mutations",
                        "operator": operator,
                        "coordination_size": size,
                        "before": before,
                        "after": after,
                        "context": context,
                        "external_model_calls": 0,
                    },
                    "mutations": mutations,
                    "candidate_digest": cd,
                }
            )
            if len(out) >= max_candidates:
                return True
    return False


def compose_scalar_candidates(
    root: str | Path,
    scalar_candidates: Sequence[Mapping[str, Any]],
    *,
    max_sites: int = 2,
    max_candidates: int = 512,
) -> dict[str, Any]:
    """Compose compatible scalar edits without issue-specific knowledge.

    Exact source-line context is used first. This favors repeated instances of
    the same coding pattern, including coordinated fixes across files. A second
    broader pass may combine the same operator/before/after transformation even
    when surrounding source text differs.

    Cross-file combinations are ranked before same-file combinations because
    they preserve independent source sites and reduce accidental clustering.
    """
    if max_sites < 2:
        raise ValueError("max_sites must be >= 2")
    if max_candidates < 1:
        raise ValueError("max_candidates must be positive")

    base = Path(root).resolve()
    exact_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    broad_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for raw in scalar_candidates:
        candidate = dict(raw)
        provenance = candidate.get("provenance") or {}
        site = provenance.get("site_edit")
        if not isinstance(site, Mapping):
            continue
        operator = str(provenance.get("operator", ""))
        before = str(site.get("before", ""))
        after = str(site.get("after", ""))
        context = str(site.get("context", ""))
        site_copy = dict(site)
        exact_groups[(operator, before, after, context)].append(site_copy)
        broad_groups[(operator, before, after)].append(site_copy)

    coordinated: list[dict[str, Any]] = []
    seen_site_sets: set[tuple[tuple[str, int, int], ...]] = set()

    for key in sorted(exact_groups):
        operator, before, after, context = key
        sites = sorted(
            exact_groups[key],
            key=lambda site: (
                str(site["path"]),
                int(site["start"]),
                int(site["end"]),
            ),
        )
        if _emit_group_combinations(
            base,
            operator=operator,
            before=before,
            after=after,
            context=context,
            sites=sites,
            max_sites=max_sites,
            seen_site_sets=seen_site_sets,
            out=coordinated,
            max_candidates=max_candidates,
        ):
            return {
                "schema": COORDINATED_SCHEMA,
                "candidate_count": len(coordinated),
                "truncated": True,
                "external_model_calls": 0,
                "candidates": coordinated,
            }

    for key in sorted(broad_groups):
        operator, before, after = key
        sites = sorted(
            broad_groups[key],
            key=lambda site: (
                str(site["path"]),
                int(site["start"]),
                int(site["end"]),
            ),
        )
        if _emit_group_combinations(
            base,
            operator=operator,
            before=before,
            after=after,
            context="",
            sites=sites,
            max_sites=max_sites,
            seen_site_sets=seen_site_sets,
            out=coordinated,
            max_candidates=max_candidates,
        ):
            return {
                "schema": COORDINATED_SCHEMA,
                "candidate_count": len(coordinated),
                "truncated": True,
                "external_model_calls": 0,
                "candidates": coordinated,
            }

    return {
        "schema": COORDINATED_SCHEMA,
        "candidate_count": len(coordinated),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": coordinated,
    }
