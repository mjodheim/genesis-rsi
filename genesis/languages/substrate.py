"""Language-neutral structural substrate for Genesis G1.

This module exposes source-code facts, not repair answers.  It deliberately uses
only the Python standard library and the existing Genesis toolchain registry so
the substrate remains cheap, deterministic and available without an external
model.

Python receives a real CPython AST view.  The other initial language families
receive a conservative lexical/structural view plus native-toolchain facts.  The
record states which backend produced it; Genesis must not pretend lexical
structure is a semantic compiler AST.

The common output is sufficient for language-neutral operators to refer to
tokens, declarations, calls, control flow and subscripts without owning six
independent repair engines.
"""
from __future__ import annotations

import ast
from bisect import bisect_right
from dataclasses import dataclass
import json
from pathlib import Path
import re
import tomllib
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from genesis.languages import toolchains
from genesis.trust_root import digest_of

DOCUMENT_SCHEMA = "genesis-language-document-v1"
PROJECT_SCHEMA = "genesis-language-substrate-project-v1"
DOCUMENTATION_REQUEST_SCHEMA = "genesis-documentation-request-v1"

_SUFFIX_LANGUAGE = {
    ".py": "python",
    ".java": "java",
    ".cs": "csharp",
    ".rs": "rust",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "typescript",
    ".jsx": "typescript",
    ".mjs": "typescript",
    ".cjs": "typescript",
}

_IGNORED_PARTS = {
    ".git", ".gradle", ".idea", ".pytest_cache", ".venv", "__pycache__",
    "bin", "build", "coverage", "dist", "node_modules", "obj", "target", "venv",
}

_KEYWORDS = {
    "abstract", "as", "async", "await", "bool", "boolean", "break", "case",
    "catch", "char", "class", "const", "continue", "def", "default", "do",
    "double", "else", "enum", "export", "extends", "false", "final", "finally",
    "float", "fn", "for", "from", "func", "function", "if", "implements",
    "import", "in", "int", "interface", "let", "long", "match", "namespace",
    "new", "null", "package", "private", "protected", "public", "record",
    "return", "static", "string", "struct", "switch", "throw", "throws", "true",
    "try", "type", "typeof", "using", "var", "void", "while", "with", "yield",
}

_TOKEN_RE = re.compile(
    r"(?P<space>\s+)"
    r"|(?P<linecomment>//[^\n]*|\#[^\n]*)"
    r"|(?P<blockcomment>/\*.*?\*/)"
    r"|(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
    r"|(?P<number>\b\d+(?:\.\d+)?\b)"
    r"|(?P<identifier>[A-Za-z_$][A-Za-z0-9_$]*)"
    r"|(?P<operator>===|!==|==|!=|<=|>=|=>|->|::|\+\+|--|&&|\|\||\.\.=|\.\.|[+\-*/%<>=!&|^?:])"
    r"|(?P<punctuation>[(){}\[\],.;@])"
    r"|(?P<other>.)",
    re.DOTALL,
)


@dataclass(frozen=True)
class SourceToken:
    kind: str
    value: str
    start: int
    end: int
    line: int
    column: int

    def record(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "value": self.value,
            "start": self.start,
            "end": self.end,
            "line": self.line,
            "column": self.column,
        }


def language_for_path(path: str | Path) -> str | None:
    return _SUFFIX_LANGUAGE.get(Path(path).suffix.lower())


def _line_starts(source: str) -> list[int]:
    result = [0]
    for match in re.finditer("\n", source):
        result.append(match.end())
    return result


def tokenize(source: str) -> tuple[SourceToken, ...]:
    """Return stable lexical tokens with absolute and line/column positions."""
    starts = _line_starts(source)
    result: list[SourceToken] = []
    for match in _TOKEN_RE.finditer(source):
        raw_kind = str(match.lastgroup)
        if raw_kind in {"space", "linecomment", "blockcomment"}:
            continue
        value = match.group(0)
        kind = raw_kind
        if kind == "identifier" and value in _KEYWORDS:
            kind = "keyword"
        line_index = bisect_right(starts, match.start()) - 1
        result.append(SourceToken(
            kind=kind,
            value=value,
            start=match.start(),
            end=match.end(),
            line=line_index + 1,
            column=match.start() - starts[line_index],
        ))
    return tuple(result)


def _balanced(tokens: tuple[SourceToken, ...]) -> tuple[bool, list[str]]:
    opens = {"(": ")", "[": "]", "{": "}"}
    closes = {value: key for key, value in opens.items()}
    stack: list[SourceToken] = []
    diagnostics: list[str] = []
    for token in tokens:
        if token.value in opens:
            stack.append(token)
        elif token.value in closes:
            if not stack or stack[-1].value != closes[token.value]:
                diagnostics.append(f"unmatched {token.value!r} at line {token.line}")
                return False, diagnostics
            stack.pop()
    if stack:
        token = stack[-1]
        diagnostics.append(f"unclosed {token.value!r} at line {token.line}")
        return False, diagnostics
    return True, diagnostics


def _node(kind: str, token: SourceToken, **fields: object) -> dict[str, object]:
    return {
        "kind": kind,
        "start": token.start,
        "end": token.end,
        "line": token.line,
        "column": token.column,
        **fields,
    }


def _lexical_structure(
    tokens: tuple[SourceToken, ...], *, language: str | None = None
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    nodes: list[dict[str, object]] = []
    symbols: list[dict[str, object]] = []
    # One linear pass for parenthesis partners prevents O(n²) lookahead
    # on large C# files containing many calls and signatures.
    paren_close: dict[int, int] = {}
    open_parens: list[int] = []
    if language == "csharp":
        for index, item in enumerate(tokens):
            if item.value == "(":
                open_parens.append(index)
            elif item.value == ")" and open_parens:
                paren_close[open_parens.pop()] = index

    declaration_keywords = {"class", "interface", "struct", "enum", "record", "type"}
    function_keywords = {"def", "fn", "func", "function"}
    control_keywords = {"if", "for", "while", "switch", "match", "catch"}
    import_keywords = {"import", "from", "using", "package"}
    variable_keywords = {"let", "const", "var"}

    for index, token in enumerate(tokens):
        previous = tokens[index - 1] if index else None
        following = tokens[index + 1] if index + 1 < len(tokens) else None

        if token.kind == "keyword" and token.value in declaration_keywords and following and following.kind == "identifier":
            nodes.append(_node("type_declaration", token, name=following.value))
            symbols.append({"kind": "type", "name": following.value, "line": following.line})
            continue

        if token.kind == "keyword" and token.value in function_keywords and following and following.kind == "identifier":
            nodes.append(_node("function_declaration", token, name=following.value))
            symbols.append({"kind": "function", "name": following.value, "line": following.line})
            continue

        if token.kind == "keyword" and token.value in control_keywords:
            nodes.append(_node(f"{token.value}_control", token))
            continue

        if token.kind == "keyword" and token.value in import_keywords:
            nodes.append(_node("import", token, keyword=token.value))
            continue

        if token.kind == "keyword" and token.value in variable_keywords and following and following.kind == "identifier":
            symbols.append({"kind": "variable", "name": following.value, "line": following.line})
            continue

        if token.value == "[" and following and index + 2 < len(tokens):
            close = tokens[index + 2]
            if close.value == "]" and following.kind in {"number", "string", "identifier"}:
                base = previous.value if previous and previous.kind == "identifier" else None
                nodes.append(_node(
                    "subscript",
                    token,
                    base=base,
                    index_kind=following.kind,
                    index_value=following.value,
                    index_start=following.start,
                    index_end=following.end,
                ))
            continue

        if token.kind == "identifier" and following and following.value == "(":
            # C# declarations also look like identifier(...); unlike calls,
            # they have a return type immediately before and a body after ')'.
            # This is ONLY a conservative lexical heuristic, not Roslyn.
            is_csharp_declaration = False
            if language == "csharp" and previous and previous.value != ".":
                if previous.kind in {"identifier", "keyword"} and previous.value not in {
                    "return", "throw", "new", "await", "if", "for", "while",
                }:
                    closing_index = paren_close.get(index + 1)
                    if closing_index is not None:
                        after = tokens[closing_index + 1] if closing_index + 1 < len(tokens) else None
                        is_csharp_declaration = bool(after and after.value in {"{", "=>"})
            if is_csharp_declaration:
                nodes.append(_node("function_declaration", token, name=token.value))
                symbols.append({"kind": "function", "name": token.value, "line": token.line})
            elif not previous or previous.value not in function_keywords | control_keywords:
                nodes.append(_node("call", token, name=token.value))
            continue

        if token.kind == "operator" and token.value in {"<", "<=", ">", ">=", "==", "!=", "===", "!==", "+", "-", "*", "/", "%"}:
            nodes.append(_node("binary_operator", token, operator=token.value))

    return nodes, symbols


def _python_ast(source: str, tokens: tuple[SourceToken, ...]) -> tuple[bool, list[dict[str, object]], list[dict[str, object]], list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return False, [], [], [f"{exc.msg} at line {exc.lineno}:{exc.offset}"]

    starts = _line_starts(source)
    nodes: list[dict[str, object]] = []
    symbols: list[dict[str, object]] = []

    kind_map = {
        ast.FunctionDef: "function_declaration",
        ast.AsyncFunctionDef: "function_declaration",
        ast.ClassDef: "type_declaration",
        ast.If: "if_control",
        ast.For: "for_control",
        ast.AsyncFor: "for_control",
        ast.While: "while_control",
        ast.Return: "return",
        ast.Call: "call",
        ast.Assign: "assignment",
        ast.AnnAssign: "assignment",
        ast.Compare: "comparison",
        ast.BinOp: "binary_expression",
        ast.Subscript: "subscript",
        ast.Import: "import",
        ast.ImportFrom: "import",
    }

    def offset(line: int | None, col: int | None) -> int:
        if not line or line < 1:
            return 0
        return starts[min(line - 1, len(starts) - 1)] + int(col or 0)

    for item in ast.walk(tree):
        mapped = next((name for cls, name in kind_map.items() if isinstance(item, cls)), None)
        if mapped:
            record: dict[str, object] = {
                "kind": mapped,
                "start": offset(getattr(item, "lineno", None), getattr(item, "col_offset", None)),
                "end": offset(getattr(item, "end_lineno", None), getattr(item, "end_col_offset", None)),
                "line": int(getattr(item, "lineno", 1) or 1),
                "column": int(getattr(item, "col_offset", 0) or 0),
            }
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                record["name"] = item.name
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
                record["name"] = item.func.id
            if isinstance(item, ast.Subscript):
                segment = ast.get_source_segment(source, item.slice)
                if segment is not None:
                    index_start = offset(getattr(item.slice, "lineno", None), getattr(item.slice, "col_offset", None))
                    record.update({
                        "index_value": segment,
                        "index_start": index_start,
                        "index_end": index_start + len(segment),
                    })
            nodes.append(record)

        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append({"kind": "function", "name": item.name, "line": item.lineno})
            for arg in item.args.args:
                entry: dict[str, object] = {"kind": "parameter", "name": arg.arg, "line": getattr(arg, "lineno", item.lineno)}
                if arg.annotation is not None:
                    entry["type"] = ast.get_source_segment(source, arg.annotation)
                symbols.append(entry)
        elif isinstance(item, ast.ClassDef):
            symbols.append({"kind": "type", "name": item.name, "line": item.lineno})
        elif isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
            symbols.append({"kind": "variable", "name": item.id, "line": item.lineno})
        elif isinstance(item, ast.Import):
            for alias in item.names:
                symbols.append({"kind": "import", "name": alias.name, "line": item.lineno})
        elif isinstance(item, ast.ImportFrom):
            module = item.module or ""
            symbols.append({"kind": "import", "name": module, "line": item.lineno})

    # Keep the lexical subscript span because it is exact and language-neutral.
    lexical_nodes, _ = _lexical_structure(tokens)
    exact_subscripts = [node for node in lexical_nodes if node["kind"] == "subscript"]
    nodes.extend(exact_subscripts)

    return True, nodes, symbols, []


def inspect_source(source: str, *, path: str) -> dict[str, object]:
    """Describe one source file through a canonical language-neutral record."""
    language = language_for_path(path)
    if language is None:
        raise ValueError(f"unsupported source language for {path!r}")

    tokens = tokenize(source)
    balanced, balance_diagnostics = _balanced(tokens)

    if language == "python":
        parse_ok, nodes, symbols, diagnostics = _python_ast(source, tokens)
        backend = "cpython_ast+genesis_lexical_v1"
        fidelity = "ast"
        diagnostics = [*balance_diagnostics, *diagnostics]
        parse_ok = parse_ok and balanced
    else:
        nodes, symbols = _lexical_structure(tokens, language=language)
        parse_ok = balanced
        diagnostics = balance_diagnostics
        backend = "genesis_lexical_structure_v1"
        fidelity = "lexical_structure"

    payload = {
        "schema": DOCUMENT_SCHEMA,
        "path": str(path),
        "language": language,
        "parser_backend": backend,
        "structural_fidelity": fidelity,
        "parse_ok": bool(parse_ok),
        "diagnostics": diagnostics,
        "source_digest": digest_of({"source": source}),
        "tokens": [token.record() for token in tokens],
        "nodes": nodes,
        "symbols": symbols,
        "external_model_calls": 0,
    }
    return {**payload, "document_digest": digest_of(payload)}


def inspect_file(path: str | Path, *, relative_path: str | None = None) -> dict[str, object]:
    source_path = Path(path)
    return inspect_source(
        source_path.read_text(encoding="utf-8"),
        path=relative_path or source_path.name,
    )


def _source_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file() or language_for_path(path) is None:
            continue
        relative = path.relative_to(root)
        if any(part in _IGNORED_PARTS for part in relative.parts[:-1]):
            continue
        if path.stat().st_size > 512_000:
            continue
        yield path


def _doc_request(ecosystem: str, package: str, version: str, source: str) -> dict[str, object]:
    payload = {
        "schema": DOCUMENTATION_REQUEST_SCHEMA,
        "ecosystem": ecosystem,
        "package": package,
        "version": version,
        "source": source,
        "network_fetched": False,
    }
    return {**payload, "request_digest": digest_of(payload)}


def documentation_requests(root: str | Path) -> list[dict[str, object]]:
    """Describe versioned documentation needs without performing network access."""
    base = Path(root)
    requests: list[dict[str, object]] = []

    package_json = base / "package.json"
    if package_json.is_file():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
            for section in ("dependencies", "devDependencies"):
                for name, version in sorted((data.get(section) or {}).items()):
                    requests.append(_doc_request("npm", str(name), str(version), "package.json"))
        except (json.JSONDecodeError, OSError):
            pass

    cargo = base / "Cargo.toml"
    if cargo.is_file():
        try:
            data = tomllib.loads(cargo.read_text(encoding="utf-8"))
            for name, value in sorted((data.get("dependencies") or {}).items()):
                version = value if isinstance(value, str) else str((value or {}).get("version", ""))
                requests.append(_doc_request("cargo", str(name), str(version), "Cargo.toml"))
        except (tomllib.TOMLDecodeError, OSError, AttributeError):
            pass

    pyproject = base / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            for requirement in (data.get("project") or {}).get("dependencies") or []:
                raw = str(requirement)
                name = re.split(r"[<>=!~\[ ;]", raw, maxsplit=1)[0]
                version = raw[len(name):].strip()
                if name:
                    requests.append(_doc_request("pypi", name, version, "pyproject.toml"))
        except (tomllib.TOMLDecodeError, OSError):
            pass

    go_mod = base / "go.mod"
    if go_mod.is_file():
        try:
            for line in go_mod.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("//") or stripped in {"require (" , ")"}:
                    continue
                if stripped.startswith("require "):
                    stripped = stripped[len("require "):].strip()
                parts = stripped.split()
                if len(parts) >= 2 and ("/" in parts[0] or "." in parts[0]):
                    requests.append(_doc_request("go", parts[0], parts[1], "go.mod"))
        except OSError:
            pass

    for csproj in sorted(base.glob("*.csproj")):
        try:
            tree = ET.parse(csproj)
            for item in tree.findall(".//PackageReference"):
                name = item.attrib.get("Include") or item.attrib.get("Update")
                version = item.attrib.get("Version") or (item.findtext("Version") or "")
                if name:
                    requests.append(_doc_request("nuget", name, version, csproj.name))
        except (ET.ParseError, OSError):
            pass

    pom = base / "pom.xml"
    if pom.is_file():
        try:
            tree = ET.parse(pom)
            for item in tree.findall(".//{*}dependency"):
                group = item.findtext("{*}groupId") or ""
                artifact = item.findtext("{*}artifactId") or ""
                version = item.findtext("{*}version") or ""
                if artifact:
                    requests.append(_doc_request("maven", f"{group}:{artifact}".strip(":"), version, "pom.xml"))
        except (ET.ParseError, OSError):
            pass

    unique = {str(item["request_digest"]): item for item in requests}
    return [unique[key] for key in sorted(unique)]


def inspect_project(root: str | Path, *, max_files: int = 256) -> dict[str, object]:
    if max_files < 1 or max_files > 10_000:
        raise ValueError("max_files must be in [1, 10000]")
    base = Path(root).resolve()
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    documents: list[dict[str, object]] = []
    files = sorted(_source_files(base), key=lambda item: item.relative_to(base).as_posix())
    for path in files[:max_files]:
        try:
            documents.append(inspect_file(path, relative_path=path.relative_to(base).as_posix()))
        except UnicodeDecodeError:
            continue

    payload = {
        "schema": PROJECT_SCHEMA,
        "project_root": str(base),
        "languages": sorted({str(item["language"]) for item in documents}),
        "document_count": len(documents),
        "truncated": len(files) > max_files,
        "documents": documents,
        "documentation_requests": documentation_requests(base),
        "toolchains": toolchains.capability_report(base),
        "external_model_calls": 0,
    }
    return {**payload, "project_digest": digest_of(payload)}
