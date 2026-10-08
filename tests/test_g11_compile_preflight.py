"""Compilation preflight only promotes syntax/type-valid candidates."""
from pathlib import Path
import tempfile
import unittest

from genesis.insights.compile_preflight import screen_candidates

JAVAC = Path("/home/anthony/tools/jdk11/bin/javac")


@unittest.skipUnless(JAVAC.is_file(), "JDK11 unavailable")
class CompilePreflightTests(unittest.TestCase):
    def test_invalid_patches_are_deprioritized_after_clean_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src" / "X.java"
            source.parent.mkdir(parents=True)
            text = "class X { int f(int x) { return x + 1; } }"
            source.write_text(text)
            import hashlib
            preimage = hashlib.sha256(text.encode()).hexdigest()
            candidates = [
                {"path": "src/X.java", "expected_sha256": preimage,
                 "content_utf8": text.replace("x + 1", "x + ;")},
                {"path": "src/X.java", "expected_sha256": preimage,
                 "content_utf8": text.replace("x + 1", "x + 2")},
                {"path": "src/X.java", "expected_sha256": preimage,
                 "content_utf8": text.replace("x + 1", "x - 1")},
            ]
            ranked, meta = screen_candidates(
                root, candidates, javac=JAVAC, classpath=(),
            )
            self.assertEqual(meta["valid_count"], 2)
            self.assertEqual(meta["invalid_count"], 1)
            self.assertEqual(meta["inconclusive_count"], 0)
            self.assertIn("x + 2", ranked[0]["content_utf8"])
            self.assertIn("x - 1", ranked[1]["content_utf8"])
            self.assertIn("x + ;", ranked[2]["content_utf8"])
            self.assertTrue(meta["candidate_content_unchanged"])
            self.assertFalse(meta["behavioral_correctness_proven"])
            self.assertEqual(len(ranked), len(candidates))
            again, again_meta = screen_candidates(
                root, candidates, javac=JAVAC, classpath=(),
            )
            self.assertEqual(meta["preflight_digest"], again_meta["preflight_digest"])
            self.assertEqual(
                [c["content_utf8"] for c in ranked],
                [c["content_utf8"] for c in again],
            )

    def test_absolute_project_paths_are_never_rewritten_or_compiled(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "Protected.java"
            source = "class Protected { int f() { return 1; } }"
            file.write_text(source)
            candidate = {"path": str(file), "content_utf8": source.replace("1", "2")}
            result, meta = screen_candidates(root, [candidate], javac=JAVAC, classpath=())
            self.assertEqual(meta["inconclusive_count"], 1)
            self.assertEqual(meta["valid_count"], 0)
            self.assertEqual(meta["invalid_count"], 0)
            self.assertEqual(file.read_text(), source)
            self.assertEqual(result[0]["content_utf8"], candidate["content_utf8"])

    def test_uncompilable_original_is_inconclusive_not_auto_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "X.java"
            file.write_text(
                "class X { int f(int x) { return new MissingDependency().f(x); } }"
            )
            c = [{"path": "X.java", "content_utf8": file.read_text().replace("x);", "x+1);")}]
            ranked, meta = screen_candidates(root, c, javac=JAVAC, classpath=())
            self.assertEqual(meta["inconclusive_count"], 1)
            self.assertEqual(meta["invalid_count"], 0)
            self.assertEqual(ranked[0]["content_utf8"], c[0]["content_utf8"])


if __name__ == "__main__":
    unittest.main()
