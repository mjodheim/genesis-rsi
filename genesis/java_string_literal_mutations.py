"""Generic Java string-predicate literal equivalence closure.

The operator finds OR-chains containing repeated calls to the same receiver
and method with string-literal arguments. When the literals expose an ASCII
case-equivalence family, it proposes the missing case variants in the same
predicate chain.

The rule is source-local and encodes no repository, class, method, API,
literal, issue, test, commit, or line identity.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-string-literal-closure-v1"

_IF_LINE = re.compile(
    r"^(?P<indent>[ \t]*)if\s*\((?P<condition>.*)\)\s*\{\s*$"
)
_CALL = re.compile(
    r"(?P<receiver>[A-Za-z_$][A-Za-z0-9_$.]*)\."
    r"(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\(\s*\"(?P<literal>(?:\\.|[^\"\\])*)\"\s*\)"
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


def _ascii_case_variant(value: str) -> str:
    chars: list[str] = []
    changed = False
    escaped = False
    for ch in value:
        if escaped:
            chars.append(ch)
            escaped = False
            continue
        if ch == "\\":
            chars.append(ch)
            escaped = True
            continue
        if "a" <= ch <= "z":
            chars.append(ch.upper())
            changed = True
        elif "A" <= ch <= "Z":
            chars.append(ch.lower())
            changed = True
        else:
            chars.append(ch)
    return "".join(chars) if changed else value


def _escape_java_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _line_candidate(
    relative: str,
    before: str,
    lines: list[str],
    line_index: int,
) -> dict[str, Any] | None:
    raw = lines[line_index].rstrip("\r\n")
    ending = "\r\n" if lines[line_index].endswith("\r\n") else "\n" if lines[line_index].endswith("\n") else ""
    match = _IF_LINE.match(raw)
    if not match or "||" not in match.group("condition"):
        return None

    calls = list(_CALL.finditer(match.group("condition")))
    if len(calls) < 2:
        return None

    grouped: dict[tuple[str, str], list[str]] = {}
    for call in calls:
        grouped.setdefault(
            (call.group("receiver"), call.group("method")), []
        ).append(call.group("literal"))

    additions: list[tuple[str, str, str]] = []
    for (receiver, method), literals in grouped.items():
        if len(literals) < 2:
            continue
        present = set(literals)
        for literal in literals:
            variant = _ascii_case_variant(literal)
            if variant == literal or variant in present:
                continue
            additions.append((receiver, method, variant))
            present.add(variant)

    if not additions:
        return None

    condition = match.group("condition").rstrip()
    extras = " || ".join(
        f'{receiver}.{method}("{_escape_java_string(literal)}")'
        for receiver, method, literal in additions
    )
    new_line = (
        f'{match.group("indent")}if ({condition} || {extras}) {{{ending}'
    )
    mutated = "".join(lines[:line_index] + [new_line] + lines[line_index + 1:])
    payload = {
        "path": relative,
        "operator": "java_string_literal_case_closure",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(mutated),
        "line": line_index + 1,
        "added_variant_count": len(additions),
        "group_count": len(grouped),
    }
    cd = digest_of(payload)
    return {
        "id": f"java-string-closure-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_string_literal_case_closure",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": mutated,
        "detail": {
            "line": line_index + 1,
            "added_variant_count": len(additions),
            "group_count": len(grouped),
            "strategy_origin": "source_local_repeated_string_predicate_ascii_case_closure",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line_index in range(len(lines)):
        candidate = _line_candidate(relative, text, lines, line_index)
        if candidate is None:
            continue
        key = _sha(candidate["content_utf8"])
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
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
        raise ValueError(
            f"project root does not exist or is not a directory: {base}"
        )

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
        "scheduling": "round_robin_by_source_file_then_predicate_line",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
