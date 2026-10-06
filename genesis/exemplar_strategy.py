"""Repository-exemplar mutation acquisition for autonomous Genesis A4.

This module does not contain task-specific fixes. It mines structural variants
that already occur in a repository and turns those observations into candidate
transformations at analogous sites.

The first acquisition substrate is deliberately narrow and auditable:
subscript expressions using the same identifier. If a repository contains both
plain forms such as [index] and adjusted forms such as [index - 1] or
[index + 2], Genesis may propose reusing an observed adjusted form at a plain
site. The offset, sign and identifier are discovered from repository text; they
are not supplied by an issue-specific recipe.

A successful candidate can then be distilled into an identifier-agnostic
strategy template for later reuse.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from genesis.trust_root import digest_of

EXEMPLAR_MUTATION_SCHEMA = "genesis-repository-exemplar-mutations-v1"
ACQUIRED_STRATEGY_SCHEMA = "genesis-acquired-edit-strategy-v1"

_SUPPORTED_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs")
_IGNORED = {
    ".git", ".github", ".venv", "__pycache__", "bin", "build", "coverage",
    "dist", "node_modules", "obj", "target", "test", "tests", "venv",
}

_PLAIN_SUBSCRIPT = re.compile(r"\[\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*\]")
_ADJUSTED_SUBSCRIPT = re.compile(
    r"\[\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*([+-])\s*([0-9]+)\s*\]"
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _eligible_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        if ".test." in path.name or ".spec." in path.name:
            continue
        relative = path.relative_to(root)
        if any(part in _IGNORED for part in relative.parts[:-1]):
            continue
        if path.stat().st_size > 512_000:
            continue
        result.append(path)
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def mine_subscript_exemplars(root: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Mine adjusted subscript forms, keyed by identifier."""
    base = Path(root).resolve()
    found: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in _eligible_files(base):
        relative = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for match in _ADJUSTED_SUBSCRIPT.finditer(text):
            identifier, sign, amount_raw = match.groups()
            amount = int(amount_raw)
            delta = amount if sign == "+" else -amount
            if any(item["delta"] == delta for item in found[identifier]):
                continue
            record = {
                "identifier": identifier,
                "delta": delta,
                "expression": f"{identifier} {sign} {amount}",
                "path": relative,
                "start": match.start(),
                "end": match.end(),
            }
            found[identifier].append(record)

    for identifier in found:
        found[identifier].sort(
            key=lambda item: (item["path"], item["start"], item["delta"])
        )
    return dict(found)


def generate(root: str | Path, *, max_candidates: int = 256) -> dict[str, Any]:
    """Generate analogous edits from repository-observed subscript exemplars."""
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")

    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    exemplars = mine_subscript_exemplars(base)
    candidates: list[dict[str, Any]] = []
    target_sites = 0

    for path in _eligible_files(base):
        relative = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        expected = _sha256_text(text)

        for match in _PLAIN_SUBSCRIPT.finditer(text):
            identifier = match.group(1)
            observed = exemplars.get(identifier, ())
            if not observed:
                continue
            target_sites += 1

            for exemplar in observed:
                replacement = f"[{exemplar['expression']}]"
                if replacement == match.group(0):
                    continue
                mutated = text[:match.start()] + replacement + text[match.end():]
                payload = {
                    "path": relative,
                    "target_start": match.start(),
                    "target_end": match.end(),
                    "before": match.group(0),
                    "after": replacement,
                    "identifier": identifier,
                    "delta": exemplar["delta"],
                    "exemplar_path": exemplar["path"],
                    "exemplar_start": exemplar["start"],
                    "expected_sha256": expected,
                }
                candidate_digest = digest_of(payload)
                candidates.append(
                    {
                        "id": f"exemplar-{candidate_digest[:16]}",
                        "label": (
                            f"observed_subscript_delta:{relative}:{match.start()}:"
                            f"{exemplar['delta']:+d}"
                        ),
                        "provenance": {
                            "generator": "repository_exemplar_mutations",
                            "operator": "observed_subscript_delta",
                            "strategy_origin": "repository_observation",
                            "identifier": identifier,
                            "delta": exemplar["delta"],
                            "exemplar_path": exemplar["path"],
                            "exemplar_start": exemplar["start"],
                            "external_model_calls": 0,
                        },
                        "mutations": [
                            {
                                "path": relative,
                                "expected_sha256": expected,
                                "expected_absent": False,
                                "content_utf8": mutated,
                            }
                        ],
                        "candidate_digest": candidate_digest,
                    }
                )
                if len(candidates) >= max_candidates:
                    return {
                        "schema": EXEMPLAR_MUTATION_SCHEMA,
                        "root": str(base),
                        "target_site_count": target_sites,
                        "candidate_count": len(candidates),
                        "truncated": True,
                        "external_model_calls": 0,
                        "candidates": candidates,
                    }

    return {
        "schema": EXEMPLAR_MUTATION_SCHEMA,
        "root": str(base),
        "target_site_count": target_sites,
        "candidate_count": len(candidates),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": candidates,
    }


def acquire_strategy(candidate: dict[str, Any], *, result_digest: str) -> dict[str, Any]:
    """Distill a winning repository-observed edit into a reusable template."""
    provenance = candidate.get("provenance") or {}
    if provenance.get("generator") != "repository_exemplar_mutations":
        raise ValueError("candidate is not repository-exemplar-derived")
    if provenance.get("strategy_origin") != "repository_observation":
        raise ValueError("candidate strategy origin is not repository observation")

    delta = int(provenance["delta"])
    sign = "+" if delta >= 0 else "-"
    amount = abs(delta)
    payload: dict[str, Any] = {
        "schema": ACQUIRED_STRATEGY_SCHEMA,
        "kind": "subscript_identifier_delta",
        "template_before": "[$IDENT]",
        "template_after": f"[$IDENT {sign} {amount}]",
        "delta": delta,
        "acquired_from_candidate_id": candidate["id"],
        "acquired_from_candidate_digest": candidate["candidate_digest"],
        "acquired_from_result_digest": result_digest,
        "source_of_transformation": "repository_observed_exemplar_plus_evaluator_selection",
        "external_model_calls": 0,
        "host_issue_specific_recipe": False,
    }
    return {**payload, "strategy_digest": digest_of(payload)}
