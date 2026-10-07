"""Generic Java sentinel-range derivation candidates.

ER1-J5 exposed a missing operation: when a method uses a pair of numeric
bounds where (0, 0) is a sentinel for "derive defaults", and an optional array
parameter supplies the actual domain, derive the upper bound from array.length
instead of from the generic default range.

The operator mines all identifiers and control-flow evidence from the source;
it contains no repository-, class-, method-, test-, or bug-specific names.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-sentinel-range-mutation-set-v1"

_SENTINEL_IF = re.compile(
    r"(?P<indent>^[ \t]*)if\s*\(\s*(?P<lo>[A-Za-z_$][A-Za-z0-9_$]*)\s*==\s*0\s*"
    r"&&\s*(?P<hi>[A-Za-z_$][A-Za-z0-9_$]*)\s*==\s*0\s*\)\s*\{",
    re.MULTILINE,
)
_ARRAY_INDEX = re.compile(r"\b(?P<array>[A-Za-z_$][A-Za-z0-9_$]*)\s*\[")
_NULL_CHECK = re.compile(
    r"\b(?P<array>[A-Za-z_$][A-Za-z0-9_$]*)\s*(?:==|!=)\s*null\b"
)
_GAP = re.compile(
    r"\b(?:int|long)\s+[A-Za-z_$][A-Za-z0-9_$]*\s*=\s*"
    r"(?P<hi>[A-Za-z_$][A-Za-z0-9_$]*)\s*-\s*(?P<lo>[A-Za-z_$][A-Za-z0-9_$]*)\s*;"
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


def _block_span(text: str, open_brace: int) -> tuple[int, int] | None:
    depth = 0
    for i in range(open_brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, i
    return None


def _candidate(
    relative: str,
    before: str,
    after: str,
    *,
    lower: str,
    upper: str,
    array: str,
    sentinel_line: int,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_sentinel_range_from_array_length",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "lower": lower,
        "upper": upper,
        "array": array,
        "sentinel_line": sentinel_line,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-range-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_sentinel_range_from_array_length",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "lower": lower,
            "upper": upper,
            "array": array,
            "sentinel_line": sentinel_line,
            "strategy_origin": "source_local_zero_zero_sentinel_plus_optional_array_domain",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    null_checked = {m.group("array") for m in _NULL_CHECK.finditer(text)}
    indexed = {m.group("array") for m in _ARRAY_INDEX.finditer(text)}
    arrays = sorted(null_checked & indexed)
    if not arrays:
        return []

    gaps = {(m.group("lo"), m.group("hi")) for m in _GAP.finditer(text)}
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for m in _SENTINEL_IF.finditer(text):
        lo, hi = m.group("lo"), m.group("hi")
        if (lo, hi) not in gaps:
            continue

        brace = text.find("{", m.start(), m.end())
        span = _block_span(text, brace)
        if not span:
            continue
        body_start, body_end = span
        original_body = text[body_start:body_end]
        indent = m.group("indent")
        inner = indent + "    "

        for array in arrays:
            # Require the candidate array to be used after the sentinel block;
            # this keeps the proposal tied to the same local range semantics.
            tail = text[body_end:]
            if not re.search(rf"\b{re.escape(array)}\s*\[", tail):
                continue

            body = original_body
            # Preserve the original block verbatim under the else branch by
            # indenting each non-empty line one level.
            body_lines = body.splitlines(keepends=True)
            indented_parts: list[str] = []
            for line in body_lines:
                if line.strip():
                    indented_parts.append("    " + line)
                else:
                    indented_parts.append(line)
            indented_body = "".join(indented_parts)

            replacement = (
                "\n"
                f"{inner}if ({array} != null) {{\n"
                f"{inner}    {hi} = {array}.length;\n"
                f"{inner}}} else {{"
                f"{indented_body}"
                f"{inner}}}\n"
                f"{indent}"
            )
            mutated = text[:body_start] + replacement + text[body_end:]
            key = _sha(mutated)
            if key in seen:
                continue
            seen.add(key)
            line_no = text.count("\n", 0, m.start()) + 1
            out.append(
                _candidate(
                    relative,
                    text,
                    mutated,
                    lower=lo,
                    upper=hi,
                    array=array,
                    sentinel_line=line_no,
                )
            )

    return out


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
        "scheduling": "round_robin_by_source_file_then_sentinel_array_domain",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
