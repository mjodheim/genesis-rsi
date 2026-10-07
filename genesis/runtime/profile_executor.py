"""Execute a content-addressed Genesis system profile without owning evaluation.

This is lineage-side runtime machinery. It materializes candidates according to a
profile's routing program and a single global candidate budget.  It never runs
tests, assigns success, or promotes a profile.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import types
from typing import Any, Mapping

from genesis.evolution import successor_generation
from genesis.learning import distillation
from genesis.trust_root import digest_of

EXECUTION_SCHEMA = "genesis-profile-candidate-generation-v1"
_SUPPORTED_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs")


class ProfileExecutionError(RuntimeError):
    pass


def _load_module(source: str, name: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = f"<{name}>"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module


def _candidate_files(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in _SUPPORTED_SUFFIXES
            and ".test." not in path.name
            and ".spec." not in path.name
            and "__pycache__" not in path.parts
            and "node_modules" not in path.parts
            and "target" not in path.parts
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _load_universal_module(
    repository_root: Path,
    profile: Mapping[str, Any],
) -> types.ModuleType:
    override = (profile.get("active_overrides") or {}).get("universal_operator_ir") or {}
    rel = str(override.get("source_path") or "")
    expected = str(override.get("source_sha256") or "")
    if not rel or not expected:
        raise ProfileExecutionError("profile has no active universal operator source")
    path = repository_root / rel
    if not path.is_file():
        raise ProfileExecutionError(f"universal operator source missing: {rel}")
    source = path.read_text(encoding="utf-8")
    actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
    if actual != expected:
        raise ProfileExecutionError("universal operator source identity mismatch")
    return _load_module(source, f"genesis_profile_universal_{expected[:12]}")


def _load_specialist(
    repository_root: Path,
    profile: Mapping[str, Any],
) -> dict[str, Any] | None:
    override = (profile.get("active_overrides") or {}).get("local_repair_specialist")
    if override is None:
        return None
    rel = str(override.get("artifact_path") or "")
    expected = str(override.get("specialist_digest") or "")
    if not rel or not expected:
        raise ProfileExecutionError("profile specialist artifact identity is incomplete")
    path = repository_root / rel
    if not path.is_file():
        raise ProfileExecutionError(f"specialist artifact missing: {rel}")
    freeze = json.loads(path.read_text(encoding="utf-8"))
    specialist = distillation.validate_specialist(freeze.get("specialist") or {})
    if specialist["specialist_digest"] != expected:
        raise ProfileExecutionError("specialist artifact identity mismatch")
    return specialist


def _specialist_candidates(
    task_root: Path,
    specialist: Mapping[str, Any],
    remaining: int,
) -> list[dict[str, Any]]:
    generated = distillation.generate(
        task_root,
        specialist,
        max_candidates=max(1, remaining),
    )
    return [
        {
            "route": "local_repair_specialist",
            "candidate_id": item["id"],
            "candidate_digest": item["candidate_digest"],
            "mutations": item["mutations"],
            "provenance": item["provenance"],
        }
        for item in generated["candidates"][:remaining]
    ]


def _universal_candidates(
    task_root: Path,
    module: Any,
    operator: Mapping[str, Any],
    remaining: int,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in _candidate_files(task_root):
        if len(records) >= remaining:
            break
        rel = path.relative_to(task_root).as_posix()
        original = path.read_text(encoding="utf-8")
        outputs = module.materialize_source(
            original,
            path=rel,
            operator=operator,
            max_outputs=remaining - len(records),
        )
        for output in outputs:
            payload = {
                "path": rel,
                "expected_sha256": hashlib.sha256(original.encode("utf-8")).hexdigest(),
                "content_utf8": output,
                "operator_digest": operator.get("operator_digest"),
            }
            records.append(
                {
                    "route": "universal_operator_ir",
                    "candidate_id": f"universal-{digest_of(payload)[:16]}",
                    "candidate_digest": digest_of(payload),
                    "mutations": [
                        {
                            "path": rel,
                            "expected_sha256": payload["expected_sha256"],
                            "expected_absent": False,
                            "content_utf8": output,
                        }
                    ],
                    "provenance": {
                        "generator": "profile_universal_operator_ir",
                        "operator_digest": operator.get("operator_digest"),
                        "external_model_calls": 0,
                    },
                }
            )
            if len(records) >= remaining:
                break
    return records


def generate_candidates(
    task_root: str | Path,
    profile: Mapping[str, Any],
    *,
    repository_root: str | Path,
    universal_operator: Mapping[str, Any],
    max_candidates: int,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 10_000:
        raise ProfileExecutionError("max_candidates must be in [1, 10000]")
    held = successor_generation._validate_profile(profile)
    root = Path(task_root).resolve()
    repository = Path(repository_root).resolve()
    if not root.is_dir():
        raise ProfileExecutionError("task root does not exist")

    route = list((held.get("routing_program") or {}).get("order") or [])
    if not route:
        raise ProfileExecutionError("profile has an empty routing program")

    universal_module = None
    specialist = None
    candidates: list[dict[str, Any]] = []
    route_counts: dict[str, int] = {}

    for step in route:
        remaining = max_candidates - len(candidates)
        if remaining <= 0:
            break
        before = len(candidates)
        if step == "local_repair_specialist":
            if specialist is None:
                specialist = _load_specialist(repository, held)
            if specialist is not None:
                candidates.extend(_specialist_candidates(root, specialist, remaining))
        elif step == "universal_operator_ir":
            if universal_module is None:
                universal_module = _load_universal_module(repository, held)
            candidates.extend(
                _universal_candidates(root, universal_module, universal_operator, remaining)
            )
        else:
            raise ProfileExecutionError(f"unsupported route step: {step}")
        route_counts[step] = len(candidates) - before

    payload = {
        "schema": EXECUTION_SCHEMA,
        "profile_digest": held["profile_digest"],
        "routing_digest": held["routing_program"]["routing_digest"],
        "candidate_budget": max_candidates,
        "candidate_count": len(candidates),
        "within_candidate_budget": len(candidates) <= max_candidates,
        "route_candidate_counts": route_counts,
        "external_model_calls": 0,
        "candidates": candidates,
    }
    return {**payload, "generation_digest": digest_of(payload)}
