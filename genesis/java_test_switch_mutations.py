"""Test-guided Java switch-case completion.

ER1-J7 exposed a missing capability: use literal test assertions as a local
specification and complete a compatible production switch by analogy with
existing sibling cases.

The operator:
- scans Java tests for assertEquals("expected", Type.method("input"));
- decodes Java string literals;
- identifies characters that appear escaped in the expected value and occur
  in the input;
- finds a production switch in Type.java whose sibling cases already emit an
  escape prefix followed by the case character;
- proposes missing case labels by cloning that structural template.

No target repository, class, method, issue, line, or character is hard-coded.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-java-test-guided-switch-completion-v1"

_ASSERT = re.compile(
    r'assertEquals\(\s*"(?P<expected>(?:\\.|[^"\\])*)"\s*,\s*'
    r'(?P<class>[A-Za-z_$][A-Za-z0-9_$]*)\.'
    r'(?P<method>[A-Za-z_$][A-Za-z0-9_$]*)\(\s*'
    r'"(?P<input>(?:\\.|[^"\\])*)"\s*\)\s*\)',
    re.DOTALL,
)
_SWITCH = re.compile(r"switch\s*\([^)]*\)\s*\{")
_CASE_CHAR = re.compile(r"case\s+'(?P<char>(?:\\.|[^'\\]))'\s*:")
_TEMPLATE = re.compile(
    r"(?m)^(?P<case_indent>[ \t]*)case\s+'(?P<label>(?:\\.|[^'\\]))'\s*:\s*\n"
    r"(?P<body_indent>[ \t]*)(?P<writer>[A-Za-z_$][A-Za-z0-9_$]*)\.write\('\\\\'\);\s*\n"
    r"(?P=body_indent)(?P=writer)\.write\('(?P<emit>(?:\\.|[^'\\]))'\);\s*\n"
    r"(?P=body_indent)break\s*;"
)
_DEFAULT = re.compile(r"(?m)^(?P<indent>[ \t]*)default\s*:")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _decode_java_escaped(raw: str) -> str:
    out: list[str] = []
    i = 0
    simple = {
        "b": "\b",
        "t": "\t",
        "n": "\n",
        "f": "\f",
        "r": "\r",
        '"': '"',
        "'": "'",
        "\\": "\\",
    }
    while i < len(raw):
        ch = raw[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(raw):
            out.append("\\")
            break
        esc = raw[i]
        if esc == "u":
            j = i
            while j < len(raw) and raw[j] == "u":
                j += 1
            hexpart = raw[j:j+4]
            if len(hexpart) == 4 and all(c in "0123456789abcdefABCDEF" for c in hexpart):
                out.append(chr(int(hexpart, 16)))
                i = j + 4
                continue
        out.append(simple.get(esc, esc))
        i += 1
    return "".join(out)


def _encode_java_char(ch: str) -> str:
    mapping = {
        "\b": "\\b",
        "\t": "\\t",
        "\n": "\\n",
        "\f": "\\f",
        "\r": "\\r",
        "'": "\\'",
        "\\": "\\\\",
    }
    return mapping.get(ch, ch)


def _block_span(text: str, open_brace: int) -> tuple[int, int] | None:
    depth = 0
    in_string = False
    in_char = False
    escaped = False
    for pos in range(open_brace, len(text)):
        ch = text[pos]
        if escaped:
            escaped = False
            continue
        if ch == "\\" and (in_string or in_char):
            escaped = True
            continue
        if ch == '"' and not in_char:
            in_string = not in_string
            continue
        if ch == "'" and not in_string:
            in_char = not in_char
            continue
        if in_string or in_char:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return open_brace + 1, pos
    return None


def _production_files(root: Path, prefixes: Sequence[str]) -> list[Path]:
    wanted = tuple(str(x).strip("/") for x in prefixes if str(x).strip("/"))
    out: list[Path] = []
    for p in root.rglob("*.java"):
        if not p.is_file() or p.stat().st_size > 512_000:
            continue
        rel = p.relative_to(root)
        if any(part in {"test", "tests"} for part in rel.parts[:-1]):
            continue
        s = rel.as_posix()
        if wanted and not any(s == x or s.startswith(x + "/") for x in wanted):
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _test_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*.java"):
        if not p.is_file() or p.stat().st_size > 512_000:
            continue
        rel = p.relative_to(root)
        if any(part in {"test", "tests"} for part in rel.parts):
            out.append(p)
    return sorted(out, key=lambda p: p.relative_to(root).as_posix())


def _assertion_hints(root: Path) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for path in _test_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(root).as_posix()
        for m in _ASSERT.finditer(text):
            expected = _decode_java_escaped(m.group("expected"))
            input_value = _decode_java_escaped(m.group("input"))
            escaped_targets: list[str] = []
            for i in range(len(expected) - 1):
                if expected[i] != "\\":
                    continue
                target = expected[i + 1]
                if target in input_value and target not in escaped_targets:
                    escaped_targets.append(target)
            if escaped_targets:
                hints.append(
                    {
                        "test_path": rel,
                        "test_sha256": _sha(text),
                        "class": m.group("class"),
                        "method": m.group("method"),
                        "targets": escaped_targets,
                    }
                )
    return hints


def _candidate(
    relative: str,
    before: str,
    after: str,
    *,
    test_path: str,
    test_sha256: str,
    class_name: str,
    method_name: str,
    target: str,
    switch_index: int,
) -> dict[str, Any]:
    payload = {
        "path": relative,
        "operator": "java_test_guided_switch_case_completion",
        "expected_sha256": _sha(before),
        "content_sha256": _sha(after),
        "test_path": test_path,
        "test_sha256": test_sha256,
        "class_name": class_name,
        "method_name": method_name,
        "target_codepoint": ord(target),
        "switch_index": switch_index,
    }
    cd = digest_of(payload)
    return {
        "id": f"java-test-switch-{cd[:16]}",
        "candidate_digest": cd,
        "path": relative,
        "operator": "java_test_guided_switch_case_completion",
        "expected_sha256": payload["expected_sha256"],
        "content_utf8": after,
        "detail": {
            "test_path": test_path,
            "test_sha256": test_sha256,
            "class_name": class_name,
            "method_name": method_name,
            "target_codepoint": ord(target),
            "switch_index": switch_index,
            "strategy_origin": "literal_test_expected_output_plus_source_local_switch_analogy",
        },
        "external_model_calls": 0,
    }


def _file_candidates(relative: str, text: str, hints: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hint in hints:
        class_name = hint["class"]
        if Path(relative).stem != class_name:
            continue

        for switch_index, sm in enumerate(_SWITCH.finditer(text)):
            brace = text.find("{", sm.start(), sm.end())
            span = _block_span(text, brace)
            if not span:
                continue
            body_start, body_end = span
            body = text[body_start:body_end]
            templates = list(_TEMPLATE.finditer(body))
            default_match = _DEFAULT.search(body)
            if not templates or not default_match:
                continue

            existing = {
                _decode_java_escaped(m.group("char"))
                for m in _CASE_CHAR.finditer(body)
            }
            # Compatibility is established by the production class named
            # in the literal assertion plus the structural escape-case
            # template in this switch. Requiring the same assertion to also
            # mention an already-handled escaped character would make the
            # operator needlessly dependent on test wording.
            template = templates[0]
            case_indent = template.group("case_indent")
            body_indent = template.group("body_indent")
            writer = template.group("writer")

            insert_abs = body_start + default_match.start()
            for target in hint["targets"]:
                if len(target) != 1 or target in existing:
                    continue
                lit = _encode_java_char(target)
                block = (
                    f"{case_indent}case '{lit}':\n"
                    f"{body_indent}{writer}.write('\\\\');\n"
                    f"{body_indent}{writer}.write('{lit}');\n"
                    f"{body_indent}break;\n"
                )
                mutated = text[:insert_abs] + block + text[insert_abs:]
                key = _sha(mutated)
                if key in seen:
                    continue
                seen.add(key)
                out.append(
                    _candidate(
                        relative,
                        text,
                        mutated,
                        test_path=hint["test_path"],
                        test_sha256=hint["test_sha256"],
                        class_name=class_name,
                        method_name=hint["method"],
                        target=target,
                        switch_index=switch_index,
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

    hints = _assertion_hints(base)
    files = _production_files(base, include_prefixes)
    per_file: list[list[dict[str, Any]]] = []
    for path in files:
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        candidates = _file_candidates(rel, text, hints)
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
        "test_hint_count": len(hints),
        "eligible_source_file_count": len(files),
        "scheduled_source_file_count": len(per_file),
        "scheduling": "round_robin_by_source_file_then_test_guided_switch_target",
        "truncated": len(out) >= max_candidates,
        "external_model_calls": 0,
        "candidates": out,
    }
    return {**payload, "set_digest": digest_of(payload)}
