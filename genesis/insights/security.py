"""Conservative static *review* hints for Python and Java source.

Does not assert exploitable vulnerabilities: attacker influence and runtime
context require independent evidence. Does not run analyzed source code.
"""
from __future__ import annotations
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PythonSecurityModule:
    module_id: str = "security.python.ast-v1"
    domain: str = "security"
    language: str = "python"

    def supports(self, report: Mapping[str, Any]) -> bool:
        return report["fidelity"] == "ast" and not report["diagnostics"]

    def scan(self, source: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        imported_subprocess: set[str] = set()
        imported_run: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_subprocess.update(
                    alias.asname or "subprocess" for alias in node.names if alias.name == "subprocess"
                )
            elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                imported_run.update(alias.asname or alias.name for alias in node.names
                                    if alias.name in {"run", "Popen", "call", "check_output", "check_call"})
        findings: list[dict[str, Any]] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                # Literal code is not evidence of injection. Warn only when the
                # expression is non-literal; even then, no taint is established.
                if node.args and not isinstance(node.args[0], ast.Constant):
                    findings.append({
                        "rule_id": "dynamic-code-execution-review",
                        "line": node.lineno,
                        "confidence": "medium",
                        "level": "review",
                        "reason": "Dynamic expression evaluated as code; assess source trust and alternatives.",
                    })
            shell = any(k.arg == "shell" and isinstance(k.value, ast.Constant)
                        and k.value.value is True for k in node.keywords)
            is_subprocess = (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in imported_subprocess
                and node.func.attr in {"run", "Popen", "call", "check_output", "check_call"}
            ) or (isinstance(node.func, ast.Name) and node.func.id in imported_run)
            if shell and is_subprocess:
                findings.append({
                    "rule_id": "subprocess-shell-review",
                    "line": node.lineno,
                    "confidence": "medium",
                    "level": "review",
                    "reason": "Shell execution enabled; assess command composition and input trust.",
                })
        return findings


@dataclass(frozen=True)
class JavaSecurityModule:
    module_id: str = "security.java.compiler-v1"
    domain: str = "security"
    language: str = "java"

    def supports(self, report: Mapping[str, Any]) -> bool:
        return str(report["fidelity"]).startswith("compiler_semantic") and not report["diagnostics"]

    def scan(self, source: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
        # Rely on compiler-resolved target, not regex/name-only matching.
        # A local variable or unrelated "exec()" is NOT Runtime.exec.
        contents = source.read_text(encoding="utf-8")
        line_breaks = [i for i, c in enumerate(contents) if c == "\n"]
        findings = []
        for call in report.get("details", {}).get("calls", []):
            target = str(call.get("target_id") or "")
            if "METHOD:java.lang.Runtime:exec(" not in target:
                continue
            start = call.get("start")
            if not isinstance(start, int) or start < 0:
                continue
            if not contents.isascii():
                # javac offsets are UTF-16: avoid bogus position reporting.
                continue
            line = 1 + sum(position < start for position in line_breaks)
            findings.append({
                "rule_id": "runtime-process-execution-review",
                "line": line,
                "confidence": "medium",
                "level": "review",
                "reason": "Resolved Runtime.exec invocation; assess argument trust and process use.",
            })
        return findings
