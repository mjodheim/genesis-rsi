"""Outcome-derived structural edit operators for the A6c autonomy track.

The A6b campaign exposed a specific limitation: Genesis could retain one-line
token rewrites, but it could not represent many multi-line, insertion/deletion,
C/C++ or configuration-file repairs at all.

This module adds a generic acquisition mechanism.  It does *not* contain
bug-specific repair recipes.  Given a patch that has already passed a frozen
evaluator, it:

1. derives contextual changed hunks with difflib;
2. abstracts identifiers/literals that survive the edit into captures;
3. verifies that the acquired operator can replay the passing patch exactly;
4. later proposes applications of that operator to compatible text files.

Evaluators remain the source of truth.  Acquisition itself uses zero model calls.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from genesis.trust_root import digest_of

OPERATOR_SCHEMA = "genesis-acquired-structural-operator-v1"
ACQUISITION_SCHEMA = "genesis-structural-operator-acquisition-v1"
CANDIDATE_SET_SCHEMA = "genesis-structural-operator-candidates-v1"

_IGNORED_PARTS = {
    ".git", ".github", ".venv", "__pycache__", "bin", "build", "coverage",
    "dist", "node_modules", "obj", "target", "test", "tests", "venv",
}

_FAMILY_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "javascript",
    ".tsx": "javascript",
    ".java": "java",
    ".cs": "dotnet",
    ".go": "go",
    ".rs": "rust",
    ".c": "c-family",
    ".h": "c-family",
    ".cc": "c-family",
    ".cpp": "c-family",
    ".cxx": "c-family",
    ".hpp": "c-family",
    ".hh": "c-family",
    ".yaml": "config",
    ".yml": "config",
    ".json": "config",
    ".toml": "config",
    ".ini": "config",
    ".cfg": "config",
    ".conf": "config",
}

_TOKEN_RE = re.compile(
    r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|'''
    r'''[A-Za-z_$][A-Za-z0-9_$]*|'''
    r'''\d+(?:\.\d+)?|'''
    r'''===|!==|==|!=|<=|>=|=>|\+\+|--|&&|\|\||\.\.=|\.\.|'''
    r'''[^\s])'''
)
_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
_STR_RE = re.compile(r'''^("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')$''')

_KEYWORDS = {
    "abstract", "as", "async", "await", "bool", "boolean", "break", "case",
    "catch", "char", "class", "const", "continue", "def", "default", "do",
    "double", "else", "enum", "export", "extends", "false", "final", "finally",
    "float", "fn", "for", "from", "func", "function", "if", "implements",
    "import", "in", "int", "interface", "let", "long", "match", "namespace",
    "new", "null", "package", "private", "protected", "public", "return",
    "static", "string", "struct", "switch", "throw", "throws", "true", "try",
    "type", "typeof", "using", "var", "void", "while", "with", "yield",
}

_CAPTURE_MARKER = "__GENESIS_CAPTURE_"


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _family(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    return _FAMILY_BY_SUFFIX.get(suffix, f"suffix:{suffix}" if suffix else "extensionless")


def validate_operator(record: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless a retained structural operator reproduces its content digest."""
    if not isinstance(record, Mapping) or record.get("schema") != OPERATOR_SCHEMA:
        raise ValueError("unsupported structural operator schema")
    value = dict(record)
    recorded = str(value.pop("operator_digest", ""))
    if not recorded or recorded != digest_of(value):
        raise ValueError("structural operator does not reproduce its digest")
    return dict(record)


def _token_kind(token: str) -> str:
    if token in _KEYWORDS:
        return "static"
    if _IDENT_RE.match(token):
        return "ident"
    if _NUM_RE.match(token):
        return "number"
    if _STR_RE.match(token):
        return "string"
    return "static"


def _tokenize(line: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _TOKEN_RE.finditer(line))


def _changed_line_indexes(
    group: Sequence[tuple[str, int, int, int, int]],
) -> tuple[set[int], set[int]]:
    before: set[int] = set()
    after: set[int] = set()
    for tag, i1, i2, j1, j2 in group:
        if tag != "equal":
            before.update(range(i1, i2))
            after.update(range(j1, j2))
    return before, after


def _bindings_for_group(
    before_lines: Sequence[str],
    after_lines: Sequence[str],
    changed_before: set[int],
    changed_after: set[int],
) -> dict[tuple[str, str], str]:
    before_values: list[tuple[str, str]] = []
    after_values: set[tuple[str, str]] = set()

    for index in sorted(changed_before):
        for token in _tokenize(before_lines[index]):
            kind = _token_kind(token)
            if kind != "static":
                before_values.append((kind, token))

    for index in sorted(changed_after):
        for token in _tokenize(after_lines[index]):
            kind = _token_kind(token)
            if kind != "static":
                after_values.add((kind, token))

    counters = {"ident": 0, "number": 0, "string": 0}
    result: dict[tuple[str, str], str] = {}
    for key in before_values:
        if key not in after_values or key in result:
            continue
        kind = key[0]
        name = f"{kind[0].upper()}{counters[kind]}"
        counters[kind] += 1
        result[key] = name
    return result


def _pattern_line(line: str, bindings: Mapping[tuple[str, str], str]) -> dict[str, Any]:
    pattern: list[dict[str, Any]] = []
    for token in _tokenize(line):
        kind = _token_kind(token)
        key = (kind, token)
        if key in bindings:
            pattern.append({"kind": "capture", "type": kind, "name": bindings[key]})
        else:
            pattern.append({"kind": "literal", "value": token})
    return {"kind": "pattern_line", "pattern": pattern}


def _render_template_line(line: str, bindings: Mapping[tuple[str, str], str]) -> str:
    parts: list[str] = []
    cursor = 0
    for match in _TOKEN_RE.finditer(line):
        parts.append(line[cursor:match.start()])
        token = match.group(0)
        key = (_token_kind(token), token)
        name = bindings.get(key)
        if name is None:
            parts.append(token)
        else:
            parts.append(f"{_CAPTURE_MARKER}{name}__")
        cursor = match.end()
    parts.append(line[cursor:])
    return "".join(parts)


def _learn_group(
    before_lines: Sequence[str],
    after_lines: Sequence[str],
    group: Sequence[tuple[str, int, int, int, int]],
) -> dict[str, Any]:
    b_start = min(item[1] for item in group)
    b_end = max(item[2] for item in group)
    changed_before, changed_after = _changed_line_indexes(group)
    bindings = _bindings_for_group(before_lines, after_lines, changed_before, changed_after)

    before_program: list[dict[str, Any]] = []
    for index in range(b_start, b_end):
        if index in changed_before:
            before_program.append(_pattern_line(before_lines[index], bindings))
        else:
            before_program.append({"kind": "literal_line", "text": before_lines[index]})

    after_program: list[dict[str, Any]] = []
    for tag, i1, i2, j1, j2 in group:
        if tag == "equal":
            for offset in range(i2 - i1):
                after_program.append({
                    "kind": "copy_line",
                    "before_line": i1 + offset - b_start,
                })
        elif tag in {"replace", "insert"}:
            for index in range(j1, j2):
                after_program.append({
                    "kind": "render_line",
                    "template": _render_template_line(after_lines[index], bindings),
                })
        elif tag == "delete":
            continue
        else:
            raise ValueError(f"unsupported diff opcode: {tag}")

    payload = {
        "before_line_count": b_end - b_start,
        "before_program": before_program,
        "after_program": after_program,
        "change_kinds": [item[0] for item in group if item[0] != "equal"],
    }
    return {**payload, "hunk_digest": digest_of(payload)}


def synthesize_operator(
    before_text: str,
    after_text: str,
    *,
    source_result_digest: str,
    source_path: str,
    context_lines: int = 1,
) -> dict[str, Any]:
    """Create a generic contextual operator from one passing file mutation."""
    if before_text == after_text:
        raise ValueError("operator acquisition requires a changed file")
    if context_lines < 0 or context_lines > 4:
        raise ValueError("context_lines must be in [0, 4]")

    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    matcher = SequenceMatcher(a=before_lines, b=after_lines, autojunk=False)
    groups = list(matcher.get_grouped_opcodes(n=context_lines))
    if not groups:
        raise ValueError("no changed hunks found")

    hunks = [
        _learn_group(before_lines, after_lines, tuple(group))
        for group in groups
    ]

    payload = {
        "schema": OPERATOR_SCHEMA,
        "source_result_digest": str(source_result_digest),
        "source_path": str(source_path),
        "source_family": _family(source_path),
        "context_lines": context_lines,
        "hunks": hunks,
        "external_model_calls_for_learning": 0,
    }
    operator = {**payload, "operator_digest": digest_of(payload)}

    # Fail closed: retained operators must be capable of reproducing the
    # evaluated outcome that created them.
    replay = apply_operator_to_text(before_text, operator, max_outputs=32)
    if after_text not in replay:
        raise ValueError("synthesized operator failed exact passing-patch replay")
    return operator


def _match_pattern(
    tokens: Sequence[str],
    pattern: Sequence[Mapping[str, Any]],
    captures: dict[str, str],
) -> bool:
    if len(tokens) != len(pattern):
        return False
    for token, part in zip(tokens, pattern):
        kind = str(part.get("kind"))
        if kind == "literal":
            if token != str(part.get("value")):
                return False
            continue
        if kind != "capture":
            return False
        if _token_kind(token) != str(part.get("type")):
            return False
        name = str(part.get("name"))
        previous = captures.get(name)
        if previous is not None and previous != token:
            return False
        captures[name] = token
    return True


def _match_hunk_at(
    lines: Sequence[str],
    start: int,
    hunk: Mapping[str, Any],
) -> dict[str, str] | None:
    program = list(hunk.get("before_program") or [])
    if start < 0 or start + len(program) > len(lines):
        return None
    captures: dict[str, str] = {}
    for offset, part in enumerate(program):
        line = lines[start + offset]
        kind = str(part.get("kind"))
        if kind == "literal_line":
            if line != str(part.get("text")):
                return None
        elif kind == "pattern_line":
            if not _match_pattern(_tokenize(line), list(part.get("pattern") or []), captures):
                return None
        else:
            return None
    return captures


def _render_hunk(
    lines: Sequence[str],
    start: int,
    hunk: Mapping[str, Any],
    captures: Mapping[str, str],
) -> list[str]:
    rendered: list[str] = []
    for part in list(hunk.get("after_program") or []):
        kind = str(part.get("kind"))
        if kind == "copy_line":
            rendered.append(lines[start + int(part["before_line"])])
        elif kind == "render_line":
            text = str(part.get("template", ""))
            for name, value in captures.items():
                text = text.replace(f"{_CAPTURE_MARKER}{name}__", value)
            if _CAPTURE_MARKER in text:
                raise ValueError("unresolved capture in structural operator")
            rendered.append(text)
        else:
            raise ValueError(f"unsupported structural after part: {kind}")
    return rendered


def _apply_hunk_once(
    text: str,
    hunk: Mapping[str, Any],
    *,
    max_matches: int = 16,
) -> tuple[str, ...]:
    lines = text.splitlines(keepends=True)
    count = int(hunk.get("before_line_count", 0))
    if count < 1:
        return ()
    outputs: list[str] = []
    for start in range(0, len(lines) - count + 1):
        captures = _match_hunk_at(lines, start, hunk)
        if captures is None:
            continue
        replacement = _render_hunk(lines, start, hunk, captures)
        mutated = "".join(lines[:start] + replacement + lines[start + count:])
        if mutated != text and mutated not in outputs:
            outputs.append(mutated)
        if len(outputs) >= max_matches:
            break
    return tuple(outputs)


def apply_operator_to_text(
    text: str,
    operator: Mapping[str, Any],
    *,
    max_outputs: int = 64,
) -> tuple[str, ...]:
    """Apply every hunk of one acquired operator, returning bounded variants."""
    operator = validate_operator(operator)
    states = [text]
    for hunk in list(operator.get("hunks") or []):
        next_states: list[str] = []
        for state in states:
            for candidate in _apply_hunk_once(state, hunk):
                if candidate not in next_states:
                    next_states.append(candidate)
                if len(next_states) >= max_outputs:
                    break
            if len(next_states) >= max_outputs:
                break
        if not next_states:
            return ()
        states = next_states
    return tuple(states[:max_outputs])


def acquire_from_candidate(
    source_root: str | Path,
    candidate: Mapping[str, Any],
    *,
    source_result_digest: str,
    context_lines: int = 1,
) -> dict[str, Any]:
    """Acquire replay-verified operators from a passing candidate."""
    root = Path(source_root).resolve()
    operators: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []

    for mutation in list(candidate.get("mutations") or []):
        rel = str(mutation.get("path", ""))
        target = root / rel
        if not rel or not target.is_file() or bool(mutation.get("expected_absent")):
            rejected.append({"path": rel, "reason": "unsupported_new_or_missing_file"})
            continue
        try:
            before = target.read_text(encoding="utf-8")
            after = str(mutation["content_utf8"])
            operator = synthesize_operator(
                before,
                after,
                source_result_digest=source_result_digest,
                source_path=rel,
                context_lines=context_lines,
            )
        except (UnicodeDecodeError, KeyError, ValueError) as exc:
            rejected.append({"path": rel, "reason": str(exc)})
            continue
        operators.append(operator)

    payload = {
        "schema": ACQUISITION_SCHEMA,
        "source_result_digest": str(source_result_digest),
        "operator_count": len(operators),
        "operators": operators,
        "rejected": rejected,
        "external_model_calls": 0,
    }
    return {**payload, "acquisition_digest": digest_of(payload)}


def _in_scope(relative: str, prefixes: Sequence[str]) -> bool:
    wanted = tuple(str(item).strip("/") for item in prefixes if str(item).strip("/"))
    if not wanted:
        return True
    return any(relative == prefix or relative.startswith(prefix + "/") for prefix in wanted)


def _eligible_files(
    root: Path,
    *,
    family: str,
    include_prefixes: Sequence[str],
) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or _family(path) != family:
            continue
        rel_path = path.relative_to(root)
        relative = rel_path.as_posix()
        if any(part in _IGNORED_PARTS for part in rel_path.parts[:-1]):
            continue
        if not _in_scope(relative, include_prefixes):
            continue
        if path.stat().st_size > 512_000:
            continue
        result.append(path)
    return sorted(result, key=lambda item: item.relative_to(root).as_posix())


def generate(
    root: str | Path,
    operators: Sequence[Mapping[str, Any]],
    *,
    include_prefixes: Sequence[str] = (),
    max_candidates: int = 256,
) -> dict[str, Any]:
    """Generate candidates from replay-verified acquired structural operators."""
    if max_candidates < 1 or max_candidates > 10_000:
        raise ValueError("max_candidates must be in [1, 10000]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    candidates: list[dict[str, Any]] = []
    for raw_operator in operators:
        operator = validate_operator(raw_operator)
        family = str(operator.get("source_family", ""))
        for path in _eligible_files(base, family=family, include_prefixes=include_prefixes):
            relative = path.relative_to(base).as_posix()
            try:
                original = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            expected = _sha256_text(original)
            for mutated in apply_operator_to_text(original, operator):
                payload = {
                    "path": relative,
                    "operator_digest": operator["operator_digest"],
                    "expected_sha256": expected,
                    "content_sha256": _sha256_text(mutated),
                }
                candidate_digest = digest_of(payload)
                candidates.append({
                    "id": f"structural-{candidate_digest[:16]}",
                    "label": f"structural_operator:{relative}",
                    "provenance": {
                        "generator": "acquired_structural_operator",
                        "operator": "structural_operator",
                        "operator_digest": operator["operator_digest"],
                        "source_result_digest": operator["source_result_digest"],
                        "strategy_origin": "prior_passing_evaluated_patch",
                        "external_model_calls": 0,
                    },
                    "mutations": [{
                        "path": relative,
                        "expected_sha256": expected,
                        "expected_absent": False,
                        "content_utf8": mutated,
                    }],
                    "candidate_digest": candidate_digest,
                })
                if len(candidates) >= max_candidates:
                    return {
                        "schema": CANDIDATE_SET_SCHEMA,
                        "candidate_count": len(candidates),
                        "truncated": True,
                        "external_model_calls": 0,
                        "candidates": candidates,
                    }

    return {
        "schema": CANDIDATE_SET_SCHEMA,
        "candidate_count": len(candidates),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": candidates,
    }
