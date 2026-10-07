"""Bounded source-local Java Calendar normalization specialist.

Distilled after ER1-J6 exposed a coordinated repair gap. The specialist is
activated only by structural evidence for a Calendar truncation/rounding
routine and composes two coordinated changes:
1. low-unit pre-normalization using Calendar fields,
2. guarding a zero-offset Calendar.set state write.

It encodes no repository, class, method, issue, commit, test, or line identity.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-calendar-normalization-specialist-v1"

_METHOD = re.compile(
    r"(?P<indent>^[ \t]*)(?:private|protected|public)?\s*static\s+void\s+"
    r"(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)\s*\(\s*"
    r"Calendar\s+(?P<cal>[A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*"
    r"int\s+(?P<field>[A-Za-z_$][A-Za-z0-9_$]*)\s*,\s*"
    r"boolean\s+(?P<round>[A-Za-z_$][A-Za-z0-9_$]*)\s*\)\s*\{",
    re.MULTILINE,
)
_OFFSET = re.compile(r"\bint\s+(?P<offset>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*0\s*;")
_BOOL_FALSE = re.compile(
    r"(?m)^(?P<indent>[ \t]*)boolean\s+(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*false\s*;"
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _block_span(text: str, open_brace: int) -> tuple[int, int] | None:
    depth = 0
    for pos in range(open_brace, len(text)):
        ch = text[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, pos
    return None


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
    method: str,
    calendar_var: str,
    field_var: str,
    round_var: str,
    offset_var: str,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_calendar_low_unit_normalization",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "method": method,
        "calendar_var": calendar_var,
        "field_var": field_var,
        "round_var": round_var,
        "offset_var": offset_var,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-calendar-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_calendar_low_unit_normalization",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "method": method,
            "calendar_var": calendar_var,
            "field_var": field_var,
            "round_var": round_var,
            "offset_var": offset_var,
            "strategy_origin": "source_local_calendar_truncation_specialist",
        },
        "external_model_calls": 0,
    }


def _method_candidate(relative: str, text: str, m: re.Match[str]) -> dict[str, Any] | None:
    brace = text.find("{", m.start(), m.end())
    span = _block_span(text, brace)
    if not span:
        return None
    body_start, body_end = span
    body = text[body_start:body_end]

    cal = m.group("cal")
    field = m.group("field")
    round_var = m.group("round")
    method = m.group("method")
    method_indent = m.group("indent")
    inner = method_indent + "    "

    # Structural activation: this must really look like a generic Calendar
    # truncate/round routine, not just any method with the same signature.
    required_fragments = (
        f"{cal}.getActualMinimum(",
        f"{cal}.getActualMaximum(",
        "Calendar.MILLISECOND",
        "Calendar.SECOND",
        "Calendar.MINUTE",
    )
    if not all(fragment in text for fragment in required_fragments):
        return None
    if "for (" not in body or ".length" not in body:
        return None

    # Find the zero-initialized variable that actually participates
    # in the Calendar.set(... Calendar.get(...) - variable) state update.
    # This avoids confusing loop indices such as "int i = 0" for the offset.
    offset = None
    set_match = None
    for offset_match in _OFFSET.finditer(body):
        candidate_offset = offset_match.group("offset")
        set_pattern = re.compile(
            rf"(?m)^(?P<indent>[ \t]*){re.escape(cal)}\.set\("
            rf"(?P<slot>[^,\n]+),\s*{re.escape(cal)}\.get\((?P=slot)\)"
            rf"\s*-\s*{re.escape(candidate_offset)}\s*\);"
        )
        candidate_set = set_pattern.search(body)
        if candidate_set:
            offset = candidate_offset
            set_match = candidate_set
            break
    if offset is None or set_match is None:
        return None

    round_anchor = _BOOL_FALSE.search(body)
    if not round_anchor:
        return None

    # Prefer explicit source-local comments when present, but do not require
    # their exact wording. They are legitimate buggy-source evidence.
    body_lower = body.lower()
    comment_signal = (
        "truncate millisecond" in body_lower
        or "truncate second" in body_lower
        or "truncate minute" in body_lower
        or "reset time" in body_lower
    )
    if not comment_signal:
        return None

    # Insert the pre-normalization immediately before the generic roundUp
    # state begins. Names are generated to avoid depending on historical ones.
    anchor_abs = body_start + round_anchor.start()
    local_date = "__genesisDate"
    local_time = "__genesisTime"
    local_done = "__genesisDone"
    millis = "__genesisMillis"
    seconds = "__genesisSeconds"
    minutes = "__genesisMinutes"

    pre = (
        f"{inner}if ({field} == Calendar.MILLISECOND) {{\n"
        f"{inner}    return;\n"
        f"{inner}}}\n\n"
        f"{inner}Date {local_date} = {cal}.getTime();\n"
        f"{inner}long {local_time} = {local_date}.getTime();\n"
        f"{inner}boolean {local_done} = false;\n\n"
        f"{inner}int {millis} = {cal}.get(Calendar.MILLISECOND);\n"
        f"{inner}if (!{round_var} || {millis} < 500) {{\n"
        f"{inner}    {local_time} = {local_time} - {millis};\n"
        f"{inner}    if ({field} == Calendar.SECOND) {{\n"
        f"{inner}        {local_done} = true;\n"
        f"{inner}    }}\n"
        f"{inner}}}\n\n"
        f"{inner}int {seconds} = {cal}.get(Calendar.SECOND);\n"
        f"{inner}if (!{local_done} && (!{round_var} || {seconds} < 30)) {{\n"
        f"{inner}    {local_time} = {local_time} - ({seconds} * 1000L);\n"
        f"{inner}    if ({field} == Calendar.MINUTE) {{\n"
        f"{inner}        {local_done} = true;\n"
        f"{inner}    }}\n"
        f"{inner}}}\n\n"
        f"{inner}int {minutes} = {cal}.get(Calendar.MINUTE);\n"
        f"{inner}if (!{local_done} && (!{round_var} || {minutes} < 30)) {{\n"
        f"{inner}    {local_time} = {local_time} - ({minutes} * 60000L);\n"
        f"{inner}}}\n\n"
        f"{inner}if ({local_date}.getTime() != {local_time}) {{\n"
        f"{inner}    {local_date}.setTime({local_time});\n"
        f"{inner}    {cal}.setTime({local_date});\n"
        f"{inner}}}\n\n"
    )

    mutated = text[:anchor_abs] + pre + text[anchor_abs:]

    # Re-find the original set statement after insertion and guard it.
    guarded_pattern = re.compile(
        rf"(?m)^(?P<indent>[ \t]*){re.escape(cal)}\.set\("
        rf"(?P<slot>[^,\n]+),\s*{re.escape(cal)}\.get\((?P=slot)\)"
        rf"\s*-\s*{re.escape(offset)}\s*\);"
    )
    guarded_match = guarded_pattern.search(mutated, anchor_abs + len(pre))
    if not guarded_match:
        return None

    indent = guarded_match.group("indent")
    original_line = guarded_match.group(0).lstrip()
    guarded = (
        f"{indent}if ({offset} != 0) {{\n"
        f"{indent}    {original_line}\n"
        f"{indent}}}"
    )
    mutated = mutated[:guarded_match.start()] + guarded + mutated[guarded_match.end():]

    if mutated == text:
        return None
    return _candidate(
        relative,
        text,
        mutated,
        method=method,
        calendar_var=cal,
        field_var=field,
        round_var=round_var,
        offset_var=offset,
    )


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 256,
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
        candidates: list[dict[str, Any]] = []
        for m in _METHOD.finditer(text):
            c = _method_candidate(rel, text, m)
            if c is not None:
                candidates.append(c)
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
        "scheduling": "round_robin_by_source_file_then_calendar_normalization_site",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
