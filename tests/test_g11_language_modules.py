from __future__ import annotations
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from genesis.languages.experience import ExperienceLedger
from genesis.languages.understanding import ModuleRegistry, JavaCompilerModule

JDK = Path("/home/anthony/tools/jdk11/bin")


class ModuleRegistryTests(unittest.TestCase):
    def test_multilanguage_fallback_is_honest(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {
                "sample.py": "def func(x):\n    if x: return 2\n    return 0\n",
                "sample.cs": "public class Test { int M(int x) { if (x < 0) return 0; return x; } }",
                "sample.rs": "fn sample(x: i32) -> i32 { if x < 0 { 0 } else { x } }",
                "sample.go": "package main\nfunc sample(x int) int { if x < 0 { return 0 }; return x }",
                "sample.ts": "const greeting = (x: number) => x + 1;",
                "sample.java": "class Sample { int m(int x) { return x + 1; } }",
            }
            registry = ModuleRegistry()
            reports = []
            for name, source in files.items():
                path = root / name
                path.write_text(source)
                reports.append(registry.analyze(path))
            self.assertEqual({r["language"] for r in reports},
                             {"python", "csharp", "rust", "go", "typescript", "java"})
            self.assertTrue(all(r["module_id"] == "genesis-substrate-v1" for r in reports))
            self.assertTrue(all(r["fidelity"] == "lexical_structure" for r in reports if r["language"] != "python"))
            self.assertEqual(next(r for r in reports if r["language"] == "python")["fidelity"], "ast")

    @unittest.skipUnless((JDK / "javac").exists(), "JDK11 unavailable")
    def test_compiler_adapter_and_removal_preserve_experience(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "Example.java"
            path.write_text("class Example { int f(int x) { if (x < 1) return 0; return x + 1; } }")
            registry = ModuleRegistry()
            registry.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
            rich = registry.analyze(path, strict=True)
            self.assertEqual(rich["fidelity"], "compiler_semantic_partial")
            self.assertTrue(rich["features"]["has_branch"])
            self.assertGreater(rich["features"]["access_count"], 0)
            ledger = ExperienceLedger(root / "memory" / "experience.sqlite")
            ledger.record(rich, operator="guard-analysis")
            summary_before = ledger.knowledge_summary()
            self.assertEqual(summary_before["observation_count"], 1)
            self.assertEqual(summary_before["independently_verified_full_suite_successes"], 0)
            self.assertTrue(registry.remove("java"))
            fallback = registry.analyze(path)
            self.assertEqual(fallback["fidelity"], "lexical_structure")
            self.assertEqual(ExperienceLedger(root / "memory" / "experience.sqlite").knowledge_summary(),
                             summary_before)

    @unittest.skipUnless((JDK / "javac").exists(), "JDK11 unavailable")
    def test_java_shadowed_symbols_and_overloads(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "Overloads.java"
            path.write_text("""
class Overloads {
    int f(int x) { int y = x; { int z = y; y = z; } return y; }
    int f(String x) { return x.length(); }
}""")
            registry = ModuleRegistry()
            registry.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
            report = registry.analyze(path, strict=True)
            self.assertEqual(report["diagnostics"], [])
            methods = [n for n in report["nodes"] if n["kind"] == "function_declaration" and n["name"] == "f"]
            self.assertEqual(len(methods), 2)
            self.assertNotEqual(methods[0]["symbol_id"], methods[1]["symbol_id"])

    def test_arbitrary_language_module_can_be_unplugged(self):
        class RubyModule:
            language = "ruby"
            module_id = "ruby-stub-v1"
            extensions = (".rb",)
            def analyze(self, source):
                return {
                    "schema": "genesis-language-module-v1",
                    "fidelity": "synthetic-test-stub",
                    "capabilities": {"syntax": True},
                    "nodes": [{"kind": "function_declaration", "start": 0, "end": 3}],
                }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.rb"
            path.write_text("def f; end")
            registry = ModuleRegistry()
            registry.register(RubyModule())
            report = registry.analyze(path, strict=True)
            self.assertEqual(report["language"], "ruby")
            ledger = ExperienceLedger(Path(td) / "mem.db")
            ledger.record(report)
            self.assertTrue(registry.remove("ruby"))
            with self.assertRaises(ValueError):
                registry.analyze(path)
            self.assertEqual(ExperienceLedger(Path(td) / "mem.db").knowledge_summary()["observation_count"], 1)

    def test_reject_forged_evidence_and_check_ledger(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "hello.py"
            path.write_text("def f(): return 1\n")
            ledger = ExperienceLedger(Path(td) / "experiences.db")
            report = ModuleRegistry().analyze(path)
            with self.assertRaises(ValueError):
                ledger.record(report, verdict="full_suite_passed")
            tampered = dict(report)
            tampered["features"] = {}
            with self.assertRaises(ValueError):
                ledger.record(tampered)
            ledger.record(report)
            with sqlite3.connect(ledger.path) as db:
                db.execute("UPDATE g11_events SET payload_json = '{\"bad\":true}' WHERE sequence = 1")
            with self.assertRaises(ValueError):
                ledger.events()


if __name__ == "__main__":
    unittest.main()
