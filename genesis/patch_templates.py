"""Generic learned line-rewrite templates for autonomous software work.

This DEVELOPMENT substrate lets Genesis retain a successful textual edit as
data and propose analogous edits later without another model call.

Important boundary:
- The learner is generic and frozen before the A6 v2 campaign.
- It only learns from *passing evaluated patches*.
- It does not receive issue-specific repair recipes.
- It supports one-line replacements whose before/after token sequences can be
  related by copied identifiers/literals, numeric deltas, and inserted static
  syntax.
- Applying a template creates candidates; tests/evaluators still decide truth.

The representation is intentionally conservative. If a patch cannot be
expressed safely, acquisition fails closed rather than inventing semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from genesis.trust_root import digest_of

TEMPLATE_SCHEMA = "genesis-learned-line-rewrite-template-v1"
TEMPLATE_SET_SCHEMA = "genesis-learned-line-rewrite-set-v1"

_SUPPORTED_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rs")
_IGNORED = {
    ".git", ".github", ".venv", "__pycache__", "bin", "build", "coverage",
    "dist", "node_modules", "obj", "target", "test", "tests", "venv",
}

_TOKEN_RE = re.compile(
    r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|'''
    r'''[A-Za-z_$][A-Za-z0-9_$]*|'''
    r'''\d+(?:\.\d+)?|'''
    r'''===|!==|==|!=|<=|>=|=>|\+\+|--|&&|\|\||\.\.=|\.\.|'''
    r'''[^\s])'''
)

_KEYWORDS = {
    "abstract","as","async","await","bool","boolean","break","case","catch","char",
    "class","const","continue","def","default","double","else","enum","export","extends",
    "false","final","finally","float","fn","for","from","func","function","if","implements",
    "import","in","int","interface","let","long","match","namespace","new","null","package",
    "private","protected","public","return","static","string","struct","switch","throw","throws",
    "true","try","type","typeof","using","var","void","while","with","yield",
}

_IDENT_RE = re.compile(r"^[A-Za-z_$][A-Za-z0-9_$]*$")
_NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
_STR_RE = re.compile(r'''^("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')$''')


def tokenize(line: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(line))


def _kind(token: str) -> str:
    if token in _KEYWORDS:
        return "static"
    if _IDENT_RE.match(token):
        return "ident"
    if _NUM_RE.match(token):
        return "number"
    if _STR_RE.match(token):
        return "string"
    return "static"


def _numeric_delta(before: str, after: str) -> int | float | None:
    if not (_NUM_RE.match(before) and _NUM_RE.match(after)):
        return None
    try:
        if "." in before or "." in after:
            delta = float(after) - float(before)
            if abs(delta) <= 1000:
                return delta
        else:
            delta = int(after) - int(before)
            if abs(delta) <= 1000:
                return delta
    except ValueError:
        return None
    return None


def learn_template(before_line: str, after_line: str, *, source_digest: str) -> dict[str, Any]:
    """Learn one conservative line rewrite from a successful evaluated edit."""
    b = tokenize(before_line)
    a = tokenize(after_line)
    if not b or not a or b == a:
        raise ValueError("template requires a non-empty changed line")

    # Bind every non-keyword identifier/literal from the before side by first
    # occurrence. Repeated values share the same variable.
    bindings: dict[tuple[str, str], str] = {}
    before_pattern: list[dict[str, Any]] = []
    counters = {"ident": 0, "number": 0, "string": 0}

    for tok in b:
        kind = _kind(tok)
        if kind == "static":
            before_pattern.append({"kind": "literal", "value": tok})
            continue
        key = (kind, tok)
        if key not in bindings:
            name = f"{kind[0].upper()}{counters[kind]}"
            counters[kind] += 1
            bindings[key] = name
        before_pattern.append({"kind": "capture", "type": kind, "name": bindings[key]})

    # Build the after program. Tokens copied verbatim from before become capture
    # references where unambiguous. Numeric changes may become a delta from a
    # nearby/unique numeric capture.
    after_program: list[dict[str, Any]] = []
    reverse = {value: key for key, value in bindings.items()}
    before_numbers = [(name, key[1]) for name, key in reverse.items() if key[0] == "number"]

    for tok in a:
        kind = _kind(tok)
        key = (kind, tok)
        if key in bindings:
            after_program.append({"kind": "copy", "name": bindings[key]})
            continue

        delta_match = None
        if kind == "number" and len(before_numbers) == 1:
            name, old = before_numbers[0]
            delta = _numeric_delta(old, tok)
            if delta is not None and delta != 0:
                delta_match = {"kind": "number_delta", "name": name, "delta": delta}
        if delta_match is not None:
            after_program.append(delta_match)
        else:
            after_program.append({"kind": "literal", "value": tok})

    payload = {
        "schema": TEMPLATE_SCHEMA,
        "before_pattern": before_pattern,
        "after_program": after_program,
        "source_result_digest": str(source_digest),
        "external_model_calls_for_learning": 0,
    }
    return {**payload, "template_digest": digest_of(payload)}


def _match(tokens: Sequence[str], pattern: Sequence[Mapping[str, Any]]) -> dict[str, str] | None:
    if len(tokens) != len(pattern):
        return None
    captures: dict[str, str] = {}
    for tok, part in zip(tokens, pattern):
        if part["kind"] == "literal":
            if tok != part["value"]:
                return None
            continue
        if part["kind"] != "capture":
            return None
        typ = str(part["type"])
        if _kind(tok) != typ:
            return None
        name = str(part["name"])
        previous = captures.get(name)
        if previous is not None and previous != tok:
            return None
        captures[name] = tok
    return captures


def _render(program: Sequence[Mapping[str, Any]], captures: Mapping[str, str]) -> str:
    out: list[str] = []
    for part in program:
        kind = part["kind"]
        if kind == "literal":
            out.append(str(part["value"]))
        elif kind == "copy":
            out.append(captures[str(part["name"])])
        elif kind == "number_delta":
            raw = captures[str(part["name"])]
            delta = part["delta"]
            if "." in raw or isinstance(delta, float):
                value = float(raw) + float(delta)
                rendered = ("%f" % value).rstrip("0").rstrip(".")
            else:
                rendered = str(int(raw) + int(delta))
            out.append(rendered)
        else:
            raise ValueError(f"unsupported after-program part: {kind}")
    return _join_tokens(out)


def _join_tokens(tokens: Sequence[str]) -> str:
    """Render tokens with conservative spacing while preserving valid syntax."""
    if not tokens:
        return ""

    # Preserve compatibility with templates learned before Go's := operator had
    # any dedicated rendering logic. The tokenizer intentionally keeps ':' and
    # '=' separate in stored patterns; rendering folds only that adjacent pair.
    normalized: list[str] = []
    index = 0
    while index < len(tokens):
        if index + 1 < len(tokens) and tokens[index] == ":" and tokens[index + 1] == "=":
            normalized.append(":=")
            index += 2
            continue
        normalized.append(tokens[index])
        index += 1
    tokens = normalized

    text = tokens[0]
    no_space_before = {")","]","}",",",";",":",".","?.","::","..","..="}
    no_space_after = {"(","[","{",".","?.","::","..","..="}
    tight_ops = {"++","--"}
    for prev, tok in zip(tokens, tokens[1:]):
        if (
            tok in no_space_before
            or prev in no_space_after
            or tok in tight_ops
            or (prev in tight_ops and (_IDENT_RE.match(tok) or _NUM_RE.match(tok)))
        ):
            text += tok
        elif tok in {"(", "["} and (_IDENT_RE.match(prev) or prev in {")", "]"}):
            text += tok
        else:
            text += " " + tok
    return text


def apply_template_to_line(line: str, template: Mapping[str, Any]) -> str | None:
    newline = "\n" if line.endswith("\n") else ""
    body = line[:-1] if newline else line
    indent = body[: len(body) - len(body.lstrip())]
    stripped = body.strip()
    captures = _match(tokenize(stripped), template["before_pattern"])
    if captures is None:
        return None
    rendered = _render(template["after_program"], captures)
    candidate = indent + rendered + newline
    return None if candidate == line else candidate


def learn_from_texts(
    before_text: str,
    after_text: str,
    *,
    source_digest: str,
) -> tuple[dict[str, Any], ...]:
    """Learn templates from simple one-line replacements in aligned files."""
    before_lines = before_text.splitlines(keepends=True)
    after_lines = after_text.splitlines(keepends=True)
    if len(before_lines) != len(after_lines):
        return ()
    templates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for before, after in zip(before_lines, after_lines):
        if before == after:
            continue
        try:
            template = learn_template(before, after, source_digest=source_digest)
        except ValueError:
            continue
        digest = template["template_digest"]
        if digest not in seen:
            seen.add(digest)
            templates.append(template)
    return tuple(templates)


def _eligible_files(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in _SUPPORTED_SUFFIXES:
            continue
        rel = path.relative_to(root)
        if any(part in _IGNORED for part in rel.parts[:-1]):
            continue
        if ".test." in path.name or ".spec." in path.name or path.stat().st_size > 512_000:
            continue
        result.append(path)
    return sorted(result, key=lambda p: p.relative_to(root).as_posix())


def generate(
    root: str | Path,
    templates: Sequence[Mapping[str, Any]],
    *,
    max_candidates: int = 256,
) -> dict[str, Any]:
    """Generate single-site candidates from previously learned templates."""
    base = Path(root).resolve()
    candidates: list[dict[str, Any]] = []
    for path in _eligible_files(base):
        rel = path.relative_to(base).as_posix()
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        expected = hashlib.sha256(original.encode()).hexdigest()
        lines = original.splitlines(keepends=True)
        for line_index, line in enumerate(lines):
            for template in templates:
                replacement = apply_template_to_line(line, template)
                if replacement is None:
                    continue
                mutated_lines = list(lines)
                mutated_lines[line_index] = replacement
                mutated = "".join(mutated_lines)
                payload = {
                    "path": rel,
                    "line_index": line_index,
                    "template_digest": template["template_digest"],
                    "expected_sha256": expected,
                    "before_line": line.rstrip("\n"),
                    "after_line": replacement.rstrip("\n"),
                }
                cd = digest_of(payload)
                candidates.append({
                    "id": f"learned-{cd[:16]}",
                    "label": f"learned_template:{rel}:{line_index + 1}",
                    "provenance": {
                        "generator": "learned_line_rewrite",
                        "operator": "learned_template",
                        "template_digest": template["template_digest"],
                        "source_result_digest": template["source_result_digest"],
                        "external_model_calls": 0,
                    },
                    "mutations": [{
                        "path": rel,
                        "expected_sha256": expected,
                        "expected_absent": False,
                        "content_utf8": mutated,
                    }],
                    "candidate_digest": cd,
                })
                if len(candidates) >= max_candidates:
                    return {
                        "schema": TEMPLATE_SET_SCHEMA,
                        "candidate_count": len(candidates),
                        "truncated": True,
                        "external_model_calls": 0,
                        "candidates": candidates,
                    }
    return {
        "schema": TEMPLATE_SET_SCHEMA,
        "candidate_count": len(candidates),
        "truncated": False,
        "external_model_calls": 0,
        "candidates": candidates,
    }
