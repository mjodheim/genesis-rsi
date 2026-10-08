"""Synthetic controls only: flags are hypotheses, never scored vulnerabilities."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from genesis.insights import (
    InsightRegistry, PythonSecurityModule, JavaSecurityModule,
    PythonPerformanceModule, JavaPerformanceModule,
)
from genesis.languages.experience import ExperienceLedger
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry

JDK = Path("/home/anthony/tools/jdk11/bin")


def domain_registry() -> InsightRegistry:
    registry = InsightRegistry()
    for module in (PythonSecurityModule(), JavaSecurityModule(),
                   PythonPerformanceModule(), JavaPerformanceModule()):
        registry.register(module)
    return registry


class PythonDomainTests(unittest.TestCase):
    def test_python_flags_dynamic_exec_and_shell_true_without_running_code(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                "import subprocess as sp\n"
                "def run(user_code, argv):\n"
                "    result = eval(user_code)\n"
                "    return sp.run(argv, shell=True)\n"
            )
            output = domain_registry().inspect(source, languages=ModuleRegistry())
            self.assertEqual({f["rule_id"] for f in output["findings"]},
                {"dynamic-code-execution-review", "subprocess-shell-review"})
            self.assertTrue(all(not f["verified_problem"] for f in output["findings"]))
            self.assertEqual(output["checked_modules"],
                             ["performance.python.ast-v1", "security.python.ast-v1"])
            self.assertFalse(output["security_cleared"])

    def test_decoys_are_not_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                'def safe():\n'
                '    text = "eval(user_input); subprocess.run(x, shell=True)"\n'
                '    # eval(data)\n'
                '    return text\n'
            )
            output = domain_registry().inspect(source, languages=ModuleRegistry())
            self.assertEqual(output["findings"], [])

    def test_nested_loops_flagged_but_not_proven(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text(
                "def count(left, right):\n"
                "    for x in left:\n"
                "        for y in right:\n"
                "            pass\n"
            )
            output = domain_registry().inspect(source, languages=ModuleRegistry())
            findings = output["findings"]
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["rule_id"], "nested-iteration-review")
            self.assertEqual(findings[0]["line"], 3)
            self.assertFalse(output["performance_improvement_proven"])

    def test_csharp_is_explicitly_unsupported_not_security_cleared(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.cs"
            source.write_text('class X { void F() { string s = "eval(a)"; } }')
            output = domain_registry().inspect(source, languages=ModuleRegistry())
            self.assertEqual(output["checked_modules"], [])
            self.assertEqual(output["coverage_by_domain"]["security"], "not_supported")
            self.assertEqual(output["coverage_by_domain"]["performance"], "not_supported")
            self.assertEqual(output["findings"], [])
            self.assertFalse(output["security_cleared"])

    def test_ledger_persists_after_unplugging_domain_module(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "sample.py"
            source.write_text("def parse(code): return eval(code)\n")
            registry = domain_registry()
            ledger = ExperienceLedger(Path(temp) / "experience.db")
            first = registry.inspect(source, languages=ModuleRegistry(), ledger=ledger)
            self.assertEqual(len(first["findings"]), 1)
            before = ledger.knowledge_summary()
            self.assertEqual(before["observation_count"], 1)
            self.assertTrue(registry.remove("security.python.ast-v1"))
            self.assertEqual(
                ExperienceLedger(Path(temp) / "experience.db").knowledge_summary(),
                before
            )
            after = registry.inspect(source, languages=ModuleRegistry())
            self.assertEqual(after["findings"], [])

    def test_report_cannot_be_reused_after_file_changes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.py"
            path.write_text("def f(): return 0\n")
            languages = ModuleRegistry()
            observed = languages.analyze(path)
            path.write_text("def f(): return 1\n")
            with self.assertRaisesRegex(ValueError, "stale"):
                domain_registry().inspect(path, understanding=observed)

    def test_unsupported_module_identity_rejected(self):
        class InvalidModule:
            domain = "unknown"
            module_id = "invalid"
            language = "python"
            def supports(self, report): return True
            def scan(self, source, report): return []
        with self.assertRaises(ValueError):
            domain_registry().register(InvalidModule())


@unittest.skipUnless((JDK / "javac").exists(), "JDK 11 unavailable")
class JavaDomainTests(unittest.TestCase):
    def java(self, path: Path) -> dict:
        languages = ModuleRegistry()
        languages.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
        return domain_registry().inspect(path, languages=languages)

    def test_java_runtime_exec_and_nested_loops(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "Example.java"
            source.write_text(
                "class Example {\n"
                " void f(String command) throws Exception {\n"
                "  Runtime.getRuntime().exec(command);\n"
                "  for (int i=0;i<5;i++) {\n"
                "   for (int j=0;j<5;j++) {}\n"
                "  }\n"
                " }\n"
                "}\n"
            )
            output = self.java(source)
            self.assertEqual({f["rule_id"] for f in output["findings"]},
                             {"runtime-process-execution-review", "nested-iteration-review"})
            self.assertEqual({f["line"] for f in output["findings"]}, {3, 5})
            self.assertFalse(output["security_cleared"])
            self.assertFalse(output["performance_improvement_proven"])

    def test_java_fake_calls_in_string_are_not_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "Example.java"
            source.write_text(
                'class Example { String f() { String s = "Runtime.getRuntime().exec(data)";'
                ' return s; } }\n'
            )
            output = self.java(source)
            self.assertEqual(output["findings"], [])


if __name__ == "__main__":
    unittest.main()
