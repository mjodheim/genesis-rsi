"""G11 predictions are source-derived, falsifiable and never oracle-fed."""
from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from genesis.insights.hypotheses import infer_for_candidate
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry
from genesis.trust_root import digest_of

JDK = Path("/home/anthony/tools/jdk11/bin")


@unittest.skipUnless((JDK / "javac").is_file(), "JDK 11 unavailable")
class HypothesisTests(unittest.TestCase):
    def make(self, directory: str, original: str, mutated: str):
        path = Path(directory) / "Trial.java"
        path.write_text(original, encoding="utf-8")
        registry = ModuleRegistry()
        registry.register(JavaCompilerModule(java=JDK / "java", javac=JDK / "javac"))
        report = registry.analyze(path, strict=True)
        self.assertEqual(report["diagnostics"], [])
        candidate = {
            "path": "Trial.java",
            "content_utf8": mutated,
            "expected_sha256": hashlib.sha256(original.encode()).hexdigest(),
            "operator": "synthetic-predicate-edit",
        }
        return path, report, candidate

    def test_boundary_comparator_has_falsifiable_values(self):
        with tempfile.TemporaryDirectory() as d:
            before = "class Trial { int f(int x) { if (x < 5) return 1; return 0; } }\n"
            after = before.replace("x < 5", "x <= 5")
            path, report, c = self.make(d, before, after)
            result = infer_for_candidate(path=path, understanding=report, candidate=c)
            self.assertEqual(result["hypothesis_count"], 1)
            hyp = result["hypotheses"][0]
            self.assertEqual(hyp["kind"], "comparison_boundary_behavior_change")
            self.assertEqual(hyp["subject"], "x")
            self.assertEqual(hyp["before_comparison"], {"operator": "<", "limit": "5"})
            self.assertEqual(hyp["after_comparison"], {"operator": "<=", "limit": "5"})
            self.assertEqual(
                [p["value"] for p in hyp["suggested_probe_values"]],
                [4, 5, 6],
            )
            self.assertFalse(hyp["correct_fix_proven"])
            self.assertFalse(hyp["hidden_tests_seen"])
            unsigned = {k: v for k, v in hyp.items() if k != "hypothesis_digest"}
            self.assertEqual(hyp["hypothesis_digest"], digest_of(unsigned))

    def test_numeric_threshold_shift_has_two_probe_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            before = "class Trial { int f(int x) { if (x > 9) return 1; return 0; } }\n"
            after = before.replace("x > 9", "x > 10")
            path, report, c = self.make(d, before, after)
            result = infer_for_candidate(path=path, understanding=report, candidate=c)
            self.assertEqual(result["hypothesis_count"], 1)
            hyp = result["hypotheses"][0]
            self.assertEqual(hyp["kind"], "numeric_threshold_behavior_change")
            self.assertEqual({p["value"] for p in hyp["suggested_probe_values"]},
                             {8, 9, 10, 11})

    def test_null_guard_has_null_probes(self):
        with tempfile.TemporaryDirectory() as d:
            before = "class Trial { String f(String x) { if (x == null) return null; return x.trim(); } }\n"
            after = before.replace("x == null", "x != null")
            path, report, c = self.make(d, before, after)
            result = infer_for_candidate(path=path, understanding=report, candidate=c)
            self.assertEqual(result["hypothesis_count"], 1)
            hyp = result["hypotheses"][0]
            self.assertEqual(hyp["kind"], "null_guard_behavior_change")
            self.assertEqual([x["kind"] for x in hyp["suggested_probe_values"]],
                             ["null", "non_null_representative"])

    def test_change_outside_condition_is_not_misrepresented_as_guard(self):
        with tempfile.TemporaryDirectory() as d:
            before = "class Trial { int f(int x) { if (x < 5) return 1; return 0; } }\n"
            after = before.replace("return 1", "return 2")
            path, report, c = self.make(d, before, after)
            self.assertEqual(
                infer_for_candidate(path=path, understanding=report, candidate=c)["hypothesis_count"],
                0,
            )

    def test_string_decoy_is_not_a_java_ast_branch(self):
        with tempfile.TemporaryDirectory() as d:
            before = 'class Trial { String f() { return "if (x < 5)"; } }\n'
            after = before.replace("x < 5", "x <= 5")
            path, report, c = self.make(d, before, after)
            self.assertEqual(
                infer_for_candidate(path=path, understanding=report, candidate=c)["hypothesis_count"],
                0,
            )

    def test_stale_source_analysis_refused(self):
        with tempfile.TemporaryDirectory() as d:
            before = "class Trial { int f(int x) { if (x < 5) return 1; return 0; } }\n"
            path, report, c = self.make(d, before, before.replace("x < 5", "x <= 5"))
            path.write_text(before.replace("5", "6"), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "stale"):
                infer_for_candidate(path=path, understanding=report, candidate=c)

    def test_non_ascii_source_not_assumed_to_have_python_offsets(self):
        with tempfile.TemporaryDirectory() as d:
            before = 'class Trial { String name="café"; int f(int x) { if (x < 5) return 1; return 0; } }\n'
            path, report, c = self.make(d, before, before.replace("x < 5", "x <= 5"))
            with self.assertRaisesRegex(ValueError, "non-ASCII"):
                infer_for_candidate(path=path, understanding=report, candidate=c)


if __name__ == "__main__":
    unittest.main()
