#!/usr/bin/env python3
"""Standalone G11 smoke matrix on synthetic, never-graded source examples.

Reports positive-control detection AND negative-control false positives.
Lexical parsers are never reported as compiler-semantic understanding.
No benchmark cases, solution patches or hidden tests are consulted.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import sys

# Support both: python3 scripts/g11_language_smoke.py and python3 -m scripts.g11_language_smoke.
root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

from genesis.languages.understanding import ModuleRegistry, JavaCompilerModule
from genesis.trust_root import digest_of

JDK = Path("/home/anthony/tools/jdk11/bin")
CASES = {
    "python": (
        ".py",
        "def f(x):\n    if x < 0:\n        return abs(x)\n    return max(x, 1)\n",
        "def f():\n    message = 'if missing()'\n    # if broken()\n    return message\n",
        "def f(:\n    return 1\n",
    ),
    "java": (
        ".java",
        "class Sample { int f(int x) { if(x < 0) return Math.abs(x); return Math.max(x,1); } }\n",
        "class Sample { String f() { String s = \"if missing()\"; // if broken()\n return s; } }\n",
        "class Sample { int f( { return 1; } }\n",
    ),
    "csharp": (
        ".cs",
        "class Sample { int F(int x) { if(x < 0) return Math.Abs(x); return Math.Max(x,1); } }\n",
        "class Sample { string F() { string s = \"if missing()\"; // if broken()\n return s; } }\n",
        "class Sample { int F( { return 1; } }\n",
    ),
    "rust": (
        ".rs",
        "fn f(x:i32)->i32 { if x < 0 { return x.abs(); } x.max(1) }\n",
        "fn f()-> &'static str { let s = \"if missing()\"; // if broken()\n s }\n",
        "fn f( ->i32 { return 1; }\n",
    ),
    "go": (
        ".go",
        "package main\nfunc f(x int) int { if x < 0 { return abs(x) }; return max(x,1) }\n",
        "package main\nfunc f() string { s := \"if missing()\" // if broken()\n return s }\n",
        "package main\nfunc f( { return 1 }\n",
    ),
    "typescript": (
        ".ts",
        "function f(x: number): number { if(x < 0) return Math.abs(x); return Math.max(x,1); }\n",
        "function f(): string { const s = \"if missing()\"; // if broken()\n return s; }\n",
        "function f( { return 1; }\n",
    ),
}


def main() -> int:
    registry = ModuleRegistry()
    if (JDK / "javac").is_file() and (JDK / "java").is_file():
        registry.register(JavaCompilerModule(java=JDK / "java", javac=JDK / "javac"))
    reports = []
    with tempfile.TemporaryDirectory(prefix="g11-six-languages-") as folder:
        root = Path(folder)
        for language, (suffix, positive, decoy, malformed) in CASES.items():
            for role, code in (("branch_and_call", positive), ("comment_string_decoy", decoy), ("malformed_source", malformed)):
                path = root / f"Sample{suffix}"
                path.write_text(code, encoding="utf-8")
                result = registry.analyze(path, strict=True)
                observed = {
                    "has_branch": result["features"]["has_branch"],
                    "has_call": result["features"]["has_call"],
                    "has_diagnostics": bool(result["diagnostics"]),
                }
                if role == "branch_and_call":
                    expected = {"has_branch": True, "has_call": True}
                    passed = all(observed[key] == value for key, value in expected.items())
                elif role == "comment_string_decoy":
                    expected = {"has_branch": False, "has_call": False}
                    passed = all(observed[key] == value for key, value in expected.items())
                else:
                    # For compiler/AST adapters, malformed source MUST be flagged.
                    # For lexical adapters, mark inability as an explicit limitation.
                    expected = {"has_diagnostics": True} if result["fidelity"] != "lexical_structure" else {}
                    passed = all(observed[key] == value for key, value in expected.items())
                reports.append({
                    "language": language,
                    "scenario": role,
                    "module": result["module_id"],
                    "fidelity": result["fidelity"],
                    "expected": expected,
                    "observed": observed,
                    "test_passed": passed,
                    "parse_limit": "invalid syntax not necessarily detectable" if not expected else None,
                    "analysis_digest": result["analysis_digest"],
                })
    body = {
        "schema": "genesis-g11-language-smoke-v1",
        "case_count": len(reports),
        "assertion_count": sum(bool(item["expected"]) for item in reports),
        "assertions_passed": sum(bool(item["expected"]) and bool(item["test_passed"]) for item in reports),
        "test_failures": [f"{item['language']}/{item['scenario']}" for item in reports if not item["test_passed"]],
        "lexical_syntax_undetectable_count": sum(not item["expected"] for item in reports),
        "cases": reports,
    }
    print(json.dumps({**body, "report_digest": digest_of(body)}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not body["test_failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
