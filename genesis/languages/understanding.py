"""G11 pluggable language understanding with explicit evidence quality.

Any language adapter may implement LanguageModule; output is converted to a
common format. Removing an adapter does not change the separate experience
ledger. The base substrate supports six families, but only Python and the
optional JDK compiler adapter claim AST-level fidelity.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from genesis.languages import substrate
from genesis.trust_root import digest_of

SCHEMA = "genesis-language-understanding-v1"
CAPABILITIES = ("syntax", "types", "symbols", "branches", "calls", "variable_access")

# Mapping intentionally shallow: it expresses portable concepts, *not* a
# promise of equivalent runtime semantics across languages.
JAVA_KIND_MAP = {
    "CLASS": "type_declaration", "INTERFACE": "type_declaration",
    "METHOD": "function_declaration", "METHOD_INVOCATION": "call",
    "IF": "if_control", "WHILE_LOOP": "while_control",
    "FOR_LOOP": "for_control", "ENHANCED_FOR_LOOP": "for_control",
    "SWITCH": "switch_control", "RETURN": "return",
    "ASSIGNMENT": "assignment", "VARIABLE": "variable_declaration",
    "ARRAY_ACCESS": "subscript", "CONDITIONAL_EXPRESSION": "conditional_control",
    "TRY": "try_control", "THROW": "throw",
}


class LanguageModule(Protocol):
    """A language-specific sensor; it must never evaluate hidden benchmarks."""
    language: str
    module_id: str
    extensions: tuple[str, ...]

    def analyze(self, source: Path) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class JavaCompilerModule:
    java: Path
    javac: Path
    classpath: tuple[str, ...] = ()
    language: str = "java"
    module_id: str = "jdk-java-compiler-v2"
    extensions: tuple[str, ...] = (".java",)

    def analyze(self, source: Path) -> Mapping[str, Any]:
        from genesis.java_analysis import analyze
        return analyze(source, java=self.java, javac=self.javac, classpath=self.classpath)


def _features(nodes: Sequence[Mapping[str, Any]], *, calls: int, branches: int, accesses: int) -> dict[str, Any]:
    kinds = sorted({str(node["kind"]) for node in nodes if node.get("kind")})
    return {
        "node_kinds": kinds,
        "call_count": calls,
        "branch_count": branches,
        "access_count": accesses,
        "has_branch": branches > 0,
        "has_call": calls > 0,
    }


def _pack(source: Path, *, language: str, module_id: str, record: Mapping[str, Any]) -> dict[str, Any]:
    if record.get("schema") == "genesis-java-understanding-v2":
        raw_nodes = list(record.get("nodes") or [])
        nodes = [
            {"kind": JAVA_KIND_MAP.get(str(n["kind"]), str(n["kind"]).lower()),
             "start": n.get("start"), "end": n.get("end"),
             "name": n.get("name"), "type": n.get("type"),
             "symbol_id": n.get("symbol_id")}
            for n in raw_nodes
        ]
        diagnostics = [f"compiler error count: {record['error_count']}"] if record.get("error_count") else []
        calls = list(record.get("calls") or [])
        branches = list(record.get("branches") or [])
        accesses = list(record.get("accesses") or [])
        quality = "compiler_semantic_with_errors" if diagnostics else "compiler_semantic_partial"
        capabilities = {
            "syntax": True, "types": True, "symbols": True,
            "branches": True, "calls": True, "variable_access": True,
        }
        details = {"calls": calls, "branches": branches, "accesses": accesses}
        source_digest = record["source_sha256"]
        offset_unit = "utf16_code_units"
    elif record.get("schema") == "genesis-language-module-v1":
        # Adapters for *any* language can return this portable contract.
        nodes = list(record.get("nodes") or [])
        calls = list(record.get("calls") or [])
        branches = list(record.get("branches") or [])
        accesses = list(record.get("accesses") or [])
        capabilities = {k: bool((record.get("capabilities") or {}).get(k, False))
                        for k in CAPABILITIES}
        diagnostics = list(record.get("diagnostics") or [])
        quality = str(record.get("fidelity") or "module_declared")
        details = {"calls": calls, "branches": branches, "accesses": accesses}
        source_digest = digest_of({"source_bytes_sha256": __import__("hashlib").sha256(source.read_bytes()).hexdigest()})
        offset_unit = str(record.get("offset_unit") or "unknown")
    elif record.get("schema") == substrate.DOCUMENT_SCHEMA:
        nodes = list(record.get("nodes") or [])
        symbols = list(record.get("symbols") or [])
        diagnostics = list(record.get("diagnostics") or [])
        quality = str(record.get("structural_fidelity"))
        capabilities = {
            "syntax": quality == "ast" and bool(record.get("parse_ok")),
            "types": False, "symbols": False,
            "branches": True, "calls": True, "variable_access": False,
        }
        details = {"symbols": symbols}
        calls = [n for n in nodes if n.get("kind") == "call"]
        branches = [n for n in nodes if str(n.get("kind", "")).endswith("_control")]
        accesses = []
        source_digest = str(record.get("source_digest"))
        offset_unit = "python_codepoints" if quality == "lexical_structure" else "mixed_utf8_ast_lexical"
    else:
        raise ValueError("unsupported language module output schema")
    payload = {
        "schema": SCHEMA,
        "language": language,
        "module_id": module_id,
        "source_path": source.name,
        "source_digest": source_digest,
        "fidelity": quality,
        "capabilities": capabilities,
        "diagnostics": diagnostics,
        "offset_unit": offset_unit,
        "nodes": nodes,
        "details": details,
        "features": _features(nodes, calls=len(calls), branches=len(branches), accesses=len(accesses)),
        "external_model_calls": 0,
    }
    return {**payload, "analysis_digest": digest_of(payload)}


class ModuleRegistry:
    """Register/withdraw semantic modules; fallback stays available and honest."""

    def __init__(self) -> None:
        self._modules: dict[str, LanguageModule] = {}
        self._extensions: dict[str, str] = {}

    def register(self, module: LanguageModule) -> None:
        language = str(module.language)
        if not language or not str(module.module_id):
            raise ValueError("language modules require language and module_id")
        if not callable(getattr(module, "analyze", None)):
            raise ValueError("language module must provide analyze()")
        extensions = tuple(str(x).lower() for x in getattr(module, "extensions", ()))
        if not extensions or any(not x.startswith(".") for x in extensions):
            raise ValueError("language modules must declare file extensions")
        for suffix in extensions:
            if suffix in self._extensions and self._extensions[suffix] != language:
                raise ValueError(f"file extension already owned: {suffix}")
        old = self._modules.get(language)
        if old is not None:
            for suffix in old.extensions:
                self._extensions.pop(suffix, None)
        self._modules[language] = module
        for suffix in extensions:
            self._extensions[suffix] = language

    def remove(self, language: str) -> bool:
        module = self._modules.pop(language, None)
        if module is not None:
            for suffix in module.extensions:
                self._extensions.pop(suffix.lower(), None)
        return module is not None

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._modules))

    def analyze(self, source: str | Path, *, strict: bool = False) -> dict[str, Any]:
        path = Path(source).resolve(strict=True)
        language = self._extensions.get(path.suffix.lower()) or substrate.language_for_path(path)
        if language is None:
            raise ValueError(f"unknown language extension: {path.suffix}")
        if path.stat().st_size > 512_000:
            raise ValueError("source exceeds analysis limit")
        module = self._modules.get(language)
        if module is not None:
            try:
                return _pack(path, language=language,
                             module_id=module.module_id, record=module.analyze(path))
            except Exception as exc:
                # If a compiler is unavailable or fails, clearly report downgrade.
                if strict:
                    raise
                failure = f"module {module.module_id} unavailable: {type(exc).__name__}"
        else:
            failure = None
        if substrate.language_for_path(path) != language:
            raise ValueError(f"no fallback substrate for {language!r}")
        record = substrate.inspect_file(path)
        result = _pack(path, language=language, module_id="genesis-substrate-v1", record=record)
        if failure:
            payload = {k: v for k, v in result.items() if k != "analysis_digest"}
            payload["diagnostics"] = [*payload["diagnostics"], failure]
            return {**payload, "analysis_digest": digest_of(payload)}
        return result
