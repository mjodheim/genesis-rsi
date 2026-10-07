"""Generic source-local Java qualified-symbol substitution candidates.

ER1-J4 exposed a missing operation: replacing one qualified static symbol with
a sibling symbol from the same qualifier, sometimes at repeated coordinated
sites. This module mines all alternatives from the source itself.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-qualified-symbol-mutation-set-v1"

_QUALIFIED = re.compile(
    r"\b(?P<qual>[A-Za-z_$][A-Za-z0-9_$]*)\."
    r"(?P<symbol>[A-Z][A-Z0-9_]*)\b"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _eligible_java_files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    wanted = tuple(str(x).strip("/") for x in prefixes if str(x).strip("/"))
    out: list[Path] = []
    for p in root.rglob("*.java"):
        if not p.is_file() or p.stat().st_size > 512_000:
            continue
        rel = p.relative_to(root)
        if any(part in {".git", "target", "build", "test", "tests"} for part in rel.parts[:-1]):
            continue
        s = rel.as_posix()
        if wanted and not any(s == x or s.startswith(x + "/") for x in wanted):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _rank(source: str, alternative: str) -> tuple[int, int, str]:
    s_tokens = source.split("_")
    a_tokens = alternative.split("_")
    shared_tokens = 0
    for left, right in zip(s_tokens, a_tokens):
        if left != right:
            break
        shared_tokens += 1

    common_chars = 0
    for left, right in zip(source, alternative):
        if left != right:
            break
        common_chars += 1

    # Negative values sort the most similar sibling first.
    return (-shared_tokens, -common_chars, alternative)


def _candidate(
    relative: str,
    before: str,
    after: str,
    *,
    qualifier: str,
    source_symbol: str,
    replacement_symbol: str,
    line: int,
    site_count: int,
    mode: str,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_qualified_symbol_substitute",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "qualifier": qualifier,
        "source_symbol": source_symbol,
        "replacement_symbol": replacement_symbol,
        "line": line,
        "site_count": site_count,
        "mode": mode,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-symbol-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_qualified_symbol_substitute",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "qualifier": qualifier,
            "source_symbol": source_symbol,
            "replacement_symbol": replacement_symbol,
            "line": line,
            "site_count": site_count,
            "mode": mode,
            "strategy_origin": "source_local_sibling_qualified_symbol",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    siblings: dict[str, set[str]] = {}
    for match in _QUALIFIED.finditer(text):
        siblings.setdefault(match.group("qual"), set()).add(match.group("symbol"))

    outputs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for line_index, line in enumerate(lines):
        matches = list(_QUALIFIED.finditer(line))
        if not matches:
            continue

        grouped: dict[tuple[str, str], list[re.Match[str]]] = {}
        for match in matches:
            key = (match.group("qual"), match.group("symbol"))
            grouped.setdefault(key, []).append(match)

        # Coordinated substitutions on repeated symbols in one source line.
        for (qualifier, source_symbol), occurrences in sorted(grouped.items()):
            alternatives = sorted(
                (s for s in siblings.get(qualifier, set()) if s != source_symbol),
                key=lambda item: _rank(source_symbol, item),
            )[:8]
            if not alternatives:
                continue
            source_token = f"{qualifier}.{source_symbol}"

            if len(occurrences) >= 2:
                for replacement_symbol in alternatives:
                    replacement_token = f"{qualifier}.{replacement_symbol}"
                    new_line = line.replace(source_token, replacement_token)
                    mutated = "".join(lines[:line_index] + [new_line] + lines[line_index + 1:])
                    key = _sha(mutated)
                    if key in seen:
                        continue
                    seen.add(key)
                    outputs.append(
                        _candidate(
                            relative,
                            text,
                            mutated,
                            qualifier=qualifier,
                            source_symbol=source_symbol,
                            replacement_symbol=replacement_symbol,
                            line=line_index + 1,
                            site_count=len(occurrences),
                            mode="coordinated_line",
                        )
                    )

            # Single-site variants are retained for defects that require only
            # one symbolic replacement.
            for occurrence in occurrences:
                start, end = occurrence.span()
                for replacement_symbol in alternatives:
                    replacement_token = f"{qualifier}.{replacement_symbol}"
                    new_line = line[:start] + replacement_token + line[end:]
                    mutated = "".join(lines[:line_index] + [new_line] + lines[line_index + 1:])
                    key = _sha(mutated)
                    if key in seen:
                        continue
                    seen.add(key)
                    outputs.append(
                        _candidate(
                            relative,
                            text,
                            mutated,
                            qualifier=qualifier,
                            source_symbol=source_symbol,
                            replacement_symbol=replacement_symbol,
                            line=line_index + 1,
                            site_count=1,
                            mode="single_site",
                        )
                    )

    return outputs


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 4096,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    files = _eligible_java_files(base, include_prefixes)
    per_file: list[list[dict[str, Any]]] = []
    for path in files:
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        candidates = _file_candidates(rel, text)
        if candidates:
            per_file.append(candidates)

    out: list[dict[str, Any]] = []
    round_index = 0
    while len(out) < max_candidates:
        progress = False
        for items in per_file:
            if round_index >= len(items):
                continue
            progress = True
            rec = dict(items[round_index])
            rec["index"] = len(out)
            out.append(rec)
            if len(out) >= max_candidates:
                break
        if not progress:
            break
        round_index += 1

    payload = {
        "schema": SCHEMA,
        "candidate_count": len(out),
        "eligible_source_file_count": len(files),
        "scheduled_source_file_count": len(per_file),
        "scheduling": "round_robin_by_source_file_then_symbol_similarity",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
