"""Generic Java fixed-layout delimited-parser empty-segment completion.

Distilled after ER1-J8 exposed a parser branch that was missing when the
middle component of a delimited input is empty. The operator mines every
identifier, delimiter, index and constructor shape from source. It contains
no repository, class, method, test, issue, delimiter, commit, or line identity.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-empty-segment-parser-mutation-set-v1"

_DELIM_CHECK = re.compile(
    r"if\s*\(\s*(?P<text>[A-Za-z_$][A-Za-z0-9_$]*)\.charAt\(\s*(?P<pos>\d+)\s*\)"
    r"\s*!=\s*'(?P<delim>(?:\\.|[^'\\]))'\s*\)"
)
_CHAR_DECL = re.compile(
    r"(?m)^(?P<indent>[ \t]*)char\s+(?P<var>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*"
    r"(?P<text>[A-Za-z_$][A-Za-z0-9_$]*)\.charAt\(\s*(?P<pos>\d+)\s*\)\s*;"
)
_RETURN3 = re.compile(
    r"return\s+new\s+(?P<type>[A-Za-z_$][A-Za-z0-9_$.]*)\s*\(\s*"
    r"(?P<text>[A-Za-z_$][A-Za-z0-9_$]*)\.substring\(\s*(?P<a0>\d+)\s*,\s*(?P<a1>\d+)\s*\)\s*,\s*"
    r"(?P=text)\.substring\(\s*(?P<b0>\d+)\s*,\s*(?P<b1>\d+)\s*\)\s*,\s*"
    r"(?P=text)\.substring\(\s*(?P<c0>\d+)\s*\)\s*\)\s*;",
    re.MULTILINE,
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


def _candidate(
    relative: str,
    before: str,
    after: str,
    *,
    text_var: str,
    char_var: str,
    delimiter_raw: str,
    delimiter_pos: int,
    empty_segment_pos: int,
    constructor_type: str,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_delimited_parser_empty_segment_complete",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "text_var": text_var,
        "char_var": char_var,
        "delimiter_raw": delimiter_raw,
        "delimiter_pos": delimiter_pos,
        "empty_segment_pos": empty_segment_pos,
        "constructor_type": constructor_type,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-empty-segment-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_delimited_parser_empty_segment_complete",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "text_var": text_var,
            "char_var": char_var,
            "delimiter_raw": delimiter_raw,
            "delimiter_pos": delimiter_pos,
            "empty_segment_pos": empty_segment_pos,
            "constructor_type": constructor_type,
            "strategy_origin": "source_local_adjacent_delimiter_and_sibling_constructor_shape",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    checks = list(_DELIM_CHECK.finditer(text))
    decls = list(_CHAR_DECL.finditer(text))
    returns = list(_RETURN3.finditer(text))
    if not checks or not decls or not returns:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for check in checks:
        text_var = check.group("text")
        delimiter_pos = int(check.group("pos"))
        delim_raw = check.group("delim")
        empty_pos = delimiter_pos + 1

        for decl in decls:
            if decl.group("text") != text_var or int(decl.group("pos")) != empty_pos:
                continue
            char_var = decl.group("var")
            insert_at = decl.end()
            indent = decl.group("indent")

            for ret in returns:
                if ret.group("text") != text_var:
                    continue

                a0, a1 = int(ret.group("a0")), int(ret.group("a1"))
                b0, b1 = int(ret.group("b0")), int(ret.group("b1"))
                c0 = int(ret.group("c0"))

                # The existing sibling return must describe the normal
                # non-empty middle segment around the char we are guarding.
                if a0 != 0 or a1 != delimiter_pos:
                    continue
                if b0 != empty_pos or b1 <= b0:
                    continue
                if c0 <= b1:
                    continue

                typ = ret.group("type")
                suffix_start = empty_pos + 1
                branch = (
                    "\n"
                    f"{indent}if ({char_var} == '{delim_raw}') {{\n"
                    f"{indent}    return new {typ}({text_var}.substring({a0}, {a1}), "
                    f"\"\", {text_var}.substring({suffix_start}));\n"
                    f"{indent}}}"
                )
                mutated = text[:insert_at] + branch + text[insert_at:]
                key = _sha(mutated)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    _candidate(
                        relative,
                        text,
                        mutated,
                        text_var=text_var,
                        char_var=char_var,
                        delimiter_raw=delim_raw,
                        delimiter_pos=delimiter_pos,
                        empty_segment_pos=empty_pos,
                        constructor_type=typ,
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
        "scheduling": "round_robin_by_source_file_then_empty_segment_site",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
