"""Generic source-local Java progress-step insertion candidates.

Learned after ER1-J3 exposed a missing control-flow operation: an existing
source-local progress step may need to be repeated before a sibling early exit.

This module does not encode repository, class, method, test, or identifier
names. It mines exemplars directly from the candidate source file.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-progress-mutation-set-v1"

_CALL_LINE = re.compile(
    r"^(?P<indent>\s*)(?P<callee>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"\(\s*(?P<arg>[A-Za-z_$][A-Za-z0-9_$]*)\s*\);\s*$"
)
_EXIT_START = re.compile(r"^\s*(?:return\b|continue\s*;|break\s*;)")


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


def _next_nonblank(lines: list[str], start: int, limit: int = 2) -> int | None:
    for i in range(start + 1, min(len(lines), start + 1 + limit)):
        if lines[i].strip():
            return i
    return None


def _previous_nonblank(lines: list[str], start: int) -> int | None:
    for i in range(start - 1, -1, -1):
        if lines[i].strip():
            return i
    return None


def _nearby_identifier(lines: list[str], line_index: int, ident: str, radius: int = 16) -> bool:
    lo = max(0, line_index - radius)
    hi = min(len(lines), line_index + 2)
    pat = re.compile(rf"\b{re.escape(ident)}\b")
    return any(pat.search(lines[i]) for i in range(lo, hi))


def _candidate(
    relative: str,
    before: str,
    after: str,
    *,
    callee: str,
    argument: str,
    exemplar_line: int,
    insertion_line: int,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_progress_step_insert",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "callee": callee,
        "argument": argument,
        "exemplar_line": exemplar_line,
        "insertion_line": insertion_line,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-progress-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_progress_step_insert",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "callee": callee,
            "argument": argument,
            "exemplar_line": exemplar_line,
            "insertion_line": insertion_line,
            "strategy_origin": "source_local_pre_exit_progress_exemplar",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    exemplars: list[tuple[int, str, str, str]] = []

    for i, line in enumerate(lines):
        raw = line.rstrip("\r\n")
        m = _CALL_LINE.match(raw)
        if not m:
            continue
        nxt = _next_nonblank(lines, i)
        if nxt is None or not _EXIT_START.match(lines[nxt].rstrip("\r\n")):
            continue
        exemplars.append((i, m.group("callee"), m.group("arg"), raw.strip()))

    if not exemplars:
        return []

    outputs: list[dict[str, Any]] = []
    seen: set[str] = set()

    for exit_i, line in enumerate(lines):
        raw_exit = line.rstrip("\r\n")
        if not _EXIT_START.match(raw_exit):
            continue
        prev = _previous_nonblank(lines, exit_i)

        for exemplar_i, callee, arg, call_text in exemplars:
            if abs(exit_i - exemplar_i) > 80:
                continue
            if not _nearby_identifier(lines, exit_i, arg):
                continue
            if prev is not None and lines[prev].strip() == call_text:
                continue

            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            indent = re.match(r"^\s*", raw_exit).group(0)
            insertion = f"{indent}{callee}({arg});{ending}"
            mutated = "".join(lines[:exit_i] + [insertion] + lines[exit_i:])
            if mutated == text:
                continue
            key = _sha(mutated)
            if key in seen:
                continue
            seen.add(key)
            outputs.append(
                _candidate(
                    relative,
                    text,
                    mutated,
                    callee=callee,
                    argument=arg,
                    exemplar_line=exemplar_i + 1,
                    insertion_line=exit_i + 1,
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

    per_file: list[list[dict[str, Any]]] = []
    files = _eligible_java_files(base, include_prefixes)
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
        "scheduling": "round_robin_by_source_file_then_local_progress_analogy",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
