"""Potential performance hot spots; no automatic complexity or speed claims."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class PythonPerformanceModule:
    module_id: str = "performance.python.ast-v1"
    domain: str = "performance"
    language: str = "python"

    def supports(self, report: Mapping[str, Any]) -> bool:
        return report["fidelity"] == "ast" and not report["diagnostics"]

    def scan(self, source: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
        tree = ast.parse(source.read_text(encoding="utf-8"))
        findings: list[dict[str, Any]] = []

        def scan(node: ast.AST, depth: int) -> None:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                depth = 0  # nested functions are separate runtime scopes
            if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
                if depth >= 1:
                    findings.append({
                        "rule_id": "nested-iteration-review",
                        "line": node.lineno,
                        "confidence": "low",
                        "level": "informational",
                        "reason": "Nested iteration may grow with input sizes; benchmark before optimizing.",
                    })
                depth += 1
            for child in ast.iter_child_nodes(node):
                scan(child, depth)
        scan(tree, 0)
        return findings


@dataclass(frozen=True)
class JavaPerformanceModule:
    module_id: str = "performance.java.compiler-v1"
    domain: str = "performance"
    language: str = "java"

    def supports(self, report: Mapping[str, Any]) -> bool:
        return str(report["fidelity"]).startswith("compiler_semantic") and not report["diagnostics"]

    def scan(self, source: Path, report: Mapping[str, Any]) -> list[dict[str, Any]]:
        contents = source.read_text(encoding="utf-8")
        if not contents.isascii():
            return []  # javac positions use UTF-16 units; be conservative
        loops = [
            node for node in report["nodes"]
            if node["kind"] in {"for_control", "while_control", "do_while_loop"}
            and isinstance(node.get("start"), int)
            and isinstance(node.get("end"), int)
            and node["start"] >= 0
        ]
        findings = []
        for nested in loops:
            if any(parent["start"] < nested["start"] and nested["end"] <= parent["end"] for parent in loops):
                findings.append({
                    "rule_id": "nested-iteration-review",
                    "line": contents.count("\n", 0, nested["start"]) + 1,
                    "confidence": "low",
                    "level": "informational",
                    "reason": "Nested iteration may scale with input sizes; benchmark before optimizing.",
                })
        return findings
