"""Generic zero-LLM scalar mutation grammar for autonomous Genesis A2.

The grammar is intentionally small and language-agnostic. It does not encode
issue-specific fixes. It enumerates single-site edits that are common in small
correctness defects:

* integer literal +/- 1;
* comparison-boundary alternatives;
* boolean literal toggles.

Candidates are deterministic, content-addressed and compatible with the
real-project evaluator. Selection remains entirely test/evaluator driven.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from genesis.trust_root import digest_of

MUTATION_SET_SCHEMA = "genesis-generic-scalar-mutation-set-v1"
SUPPORTED_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs")
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".github",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "target",
    "tests",
    "test",
}

_INTEGER = re.compile(r"(?<![A-Za-z0-9_.$])([0-9]+)(?![A-Za-z0-9_.$])")
_BOOLEAN = re.compile(r"\b(True|False|true|false)\b")
_COMPARISON = re.compile(r"(?<![<>=!])(?:===|!==|==|!=|<=|>=|<|>)(?![<>=])")

_COMPARISON_ALTERNATIVES = {
    "<": ("<=", ">"),
    "<=": ("<", ">="),
    ">": (">=", "<"),
    ">=": (">", "<="),
    "==": ("!=",),
    "!=": ("==",),
    "===": ("!==",),
    "!==": ("===",),
}

_BOOLEAN_ALTERNATIVES = {
    "True": ("False",),
    "False": ("True",),
    "true": ("false",),
    "false": ("true",),
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _eligible_files(
    root: Path,
    *,
    include_prefixes: Sequence[str] = (),
    excluded_parts: Iterable[str] = DEFAULT_EXCLUDED_PARTS,
) -> list[Path]:
    excluded = set(excluded_parts)
    prefixes = tuple(str(item).strip("/") for item in include_prefixes if str(item).strip("/"))
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        parts = path.relative_to(root).parts
        if any(part in excluded for part in parts[:-1]):
            continue
        if prefixes and not any(relative == prefix or relative.startswith(prefix + "/") for prefix in prefixes):
            continue
        if path.stat().st_size > 512_000:
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def _site_alternatives(text: str) -> list[tuple[int, int, str, str]]:
    sites: list[tuple[int, int, str, str]] = []

    for match in _INTEGER.finditer(text):
        raw = match.group(1)
        try:
            value = int(raw, 10)
        except ValueError:
            continue
        if value > 1_000_000_000:
            continue
        replacements = []
        if value > 0:
            replacements.append(str(value - 1))
        replacements.append(str(value + 1))
        for replacement in replacements:
            if replacement != raw:
                sites.append((match.start(1), match.end(1), replacement, "integer_delta"))

    for match in _BOOLEAN.finditer(text):
        raw = match.group(1)
        for replacement in _BOOLEAN_ALTERNATIVES[raw]:
            sites.append((match.start(1), match.end(1), replacement, "boolean_toggle"))

    for match in _COMPARISON.finditer(text):
        raw = match.group(0)
        for replacement in _COMPARISON_ALTERNATIVES.get(raw, ()):
            sites.append((match.start(), match.end(), replacement, "comparison_boundary"))

    sites.sort(key=lambda item: (item[0], item[1], item[3], item[2]))
    return sites


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 256,
) -> dict[str, Any]:
    """Enumerate deterministic single-site scalar candidates without an LLM."""
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    candidates: list[dict[str, Any]] = []
    site_count = 0

    for path in _eligible_files(base, include_prefixes=include_prefixes):
        relative = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        expected = _sha256_text(text)

        for start, end, replacement, operator in _site_alternatives(text):
            site_count += 1
            mutated = text[:start] + replacement + text[end:]
            payload = {
                "path": relative,
                "start": start,
                "end": end,
                "before": text[start:end],
                "after": replacement,
                "operator": operator,
                "expected_sha256": expected,
            }
            candidate_digest = digest_of(payload)
            candidates.append(
                {
                    "id": f"scalar-{candidate_digest[:16]}",
                    "label": f"{operator}:{relative}:{start}",
                    "provenance": {
                        "generator": "generic_scalar_mutations",
                        "operator": operator,
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
                    "schema": MUTATION_SET_SCHEMA,
                    "root": str(base),
                    "include_prefixes": list(include_prefixes),
                    "site_alternative_count_observed": site_count,
                    "candidate_count": len(candidates),
                    "truncated": True,
                    "external_model_calls": 0,
                    "candidates": candidates,
                }

    return {
        "schema": MUTATION_SET_SCHEMA,
        "root": str(base),
        "include_prefixes": list(include_prefixes),
        "site_alternative_count_observed": site_count,
        "candidate_count": len(candidates),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": candidates,
    }
