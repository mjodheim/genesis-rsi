"""Generic zero-LLM Java structural mutations learned after ER1-J2.

The module adds bounded structural candidates that the scalar A2 grammar cannot
express.  It contains no repository-, bug-, class-, or test-specific identity.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-structural-mutation-set-v1"

_FIELD = re.compile(
    r"^(?P<indent>\s*)(?P<visibility>public|protected|private)?(?P<gap>\s*)"
    r"(?P<mods>(?:(?:static|final|transient|volatile)\s+)*)"
    r"(?P<type>[A-Za-z_$][A-Za-z0-9_$.<>?, \[\]]*)\s+"
    r"(?P<name>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"(?P<tail>\s*(?:=[^;]*)?;)\s*$"
)
_INIT = re.compile(r"\b(?:private|protected|public)?\s*void\s+init\s*\(\s*\)\s*\{")
_ASSIGN = re.compile(r"\b(?:this\.)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _java_files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    wanted = tuple(str(x).strip("/") for x in prefixes if str(x).strip("/"))
    out: list[Path] = []
    for p in root.rglob("*.java"):
        rel = p.relative_to(root)
        s = rel.as_posix()
        if any(x in {".git", "target", "build", "test", "tests"} for x in rel.parts[:-1]):
            continue
        if wanted and not any(s == x or s.startswith(x + "/") for x in wanted):
            continue
        if p.is_file() and p.stat().st_size <= 512_000:
            out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _candidate(relative: str, before: str, after: str, operator: str, detail: dict[str, Any]) -> dict[str, Any]:
    expected = _sha(before)
    identity = {
        "path": relative,
        "operator": operator,
        "expected_sha256": expected,
        "content_sha256": _sha(after),
        "detail": detail,
    }
    digest = digest_of(identity)
    return {
        "id": f"java-struct-{digest[:16]}",
        "candidate_digest": digest,
        "path": relative,
        "operator": operator,
        "expected_sha256": expected,
        "content_utf8": after,
        "detail": detail,
        "external_model_calls": 0,
    }


def _field_modifier_candidates(relative: str, text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    out: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        raw = line.rstrip("\r\n")
        ending = line[len(raw):]
        m = _FIELD.match(raw)
        if not m or "(" in raw or ")" in raw:
            continue
        modifiers = tuple(x for x in m.group("mods").split() if x)
        for modifier in ("transient", "final", "static"):
            if modifier in modifiers:
                continue
            # Avoid clearly invalid final declarations without an initializer.
            if modifier == "final" and "=" not in m.group("tail"):
                continue
            visibility = m.group("visibility") or ""
            prefix = m.group("indent") + visibility
            if visibility:
                prefix += " "
            new_mods = " ".join((*modifiers, modifier))
            replacement = (
                prefix + (new_mods + " " if new_mods else "") +
                m.group("type").strip() + " " + m.group("name") + m.group("tail") + ending
            )
            mutated = "".join(lines[:i] + [replacement] + lines[i + 1:])
            out.append(_candidate(
                relative, text, mutated, "java_field_modifier_add",
                {"line": i + 1, "field": m.group("name"), "modifier": modifier},
            ))
    return out


def _method_body_span(text: str, start: int) -> tuple[int, int] | None:
    brace = text.find("{", start)
    if brace < 0:
        return None
    depth = 0
    for pos in range(brace, len(text)):
        ch = text[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return brace + 1, pos
    return None


def _serialization_reinit_candidate(relative: str, text: str) -> dict[str, Any] | None:
    if "readObject(" in text:
        return None
    if "Serializable" not in text and "serialVersionUID" not in text:
        return None
    init = _INIT.search(text)
    if not init:
        return None
    span = _method_body_span(text, init.start())
    if not span:
        return None
    body = text[span[0]:span[1]]
    assigned = set(_ASSIGN.findall(body))
    if not assigned:
        return None

    lines = text.splitlines(keepends=True)
    changed_fields: list[str] = []
    for i, line in enumerate(lines):
        raw = line.rstrip("\r\n")
        ending = line[len(raw):]
        m = _FIELD.match(raw)
        if not m or m.group("name") not in assigned:
            continue
        mods = tuple(x for x in m.group("mods").split() if x)
        if "static" in mods or "transient" in mods:
            continue
        visibility = m.group("visibility") or ""
        prefix = m.group("indent") + visibility + (" " if visibility else "")
        new_mods = " ".join((*mods, "transient"))
        lines[i] = (
            prefix + new_mods + " " + m.group("type").strip() + " " +
            m.group("name") + m.group("tail") + ending
        )
        changed_fields.append(m.group("name"))
    if not changed_fields:
        return None

    mutated = "".join(lines)
    package_match = re.search(r"(?m)^package\s+[^;]+;\s*$", mutated)
    if not package_match:
        return None
    imports = []
    if "import java.io.IOException;" not in mutated:
        imports.append("import java.io.IOException;\n")
    if "import java.io.ObjectInputStream;" not in mutated:
        imports.append("import java.io.ObjectInputStream;\n")
    if imports:
        pos = package_match.end()
        mutated = mutated[:pos] + "\n\n" + "".join(imports) + mutated[pos:]

    close = mutated.rfind("}")
    if close < 0:
        return None
    hook = (
        "\n    private void readObject(ObjectInputStream in) "
        "throws IOException, ClassNotFoundException {\n"
        "        in.defaultReadObject();\n"
        "        init();\n"
        "    }\n"
    )
    mutated = mutated[:close] + hook + mutated[close:]
    if mutated == text:
        return None
    return _candidate(
        relative, text, mutated, "java_serialization_reinit",
        {"derived_fields": sorted(changed_fields), "initializer_method": "init"},
    )


def generate(
    root: str | Path,
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 2048,
) -> dict[str, Any]:
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    files = _java_files(base, include_prefixes)
    per_file: list[list[dict[str, Any]]] = []
    for path in files:
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        candidates = _field_modifier_candidates(rel, text)
        special = _serialization_reinit_candidate(rel, text)
        if special is not None:
            candidates.insert(0, special)
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
            item = dict(items[round_index])
            item["index"] = len(out)
            out.append(item)
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
        "scheduling": "round_robin_by_source_file_then_operator_order",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
