"""Portable source-fairness checks, independent of benchmark identities."""
from collections import Counter
from pathlib import Path
import tempfile
import unittest

from genesis import repair_strategist


class SourceBalancingTests(unittest.TestCase):
    def test_balance_spreads_frontier_without_changing_legacy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = []
            for name in ("A", "B"):
                src = root / "src" / (name + ".java")
                src.parent.mkdir(parents=True, exist_ok=True)
                src.write_text(
                    f"class {name} {{ int f(int x) {{ "
                    f"if (x < 2) return 1; if (x > 10) return 0; "
                    f"return x + 1; }} }}"
                )
                paths.append("src/" + name + ".java")
            opts = dict(include_prefixes=["src"], focus_paths=paths,
                        max_candidates=80, per_family_budget=80)
            normal = repair_strategist.generate(root, **opts)
            spread = repair_strategist.generate(
                root, source_balance_experimental=True, **opts
            )
            dist = Counter(x["path"] for x in spread["candidates"][:8])
            self.assertGreater(dist[paths[0]], 0)
            self.assertGreater(dist[paths[1]], 0)
            self.assertTrue(set(dist) <= set(paths))
            self.assertNotIn("source_balance_experimental", normal)
            self.assertEqual(
                normal["strategy_digest"],
                repair_strategist.generate(root, **opts)["strategy_digest"],
            )

    def test_balance_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "src" / "A.java"
            file.parent.mkdir(parents=True)
            file.write_text("class A { int f(int x) { if(x>2)return 1; return 0; } }")
            opts = dict(include_prefixes=["src"], focus_paths=["src/A.java"],
                        max_candidates=50, source_balance_experimental=True)
            a = repair_strategist.generate(root, **opts)
            b = repair_strategist.generate(root, **opts)
            self.assertEqual(a["strategy_digest"], b["strategy_digest"])


@unittest.skipUnless(Path("/home/anthony/tools/jdk11/bin/javac").is_file(), "requires JDK11")
class ProjectClasspathTests(unittest.TestCase):
    def test_compiler_sees_cross_file_types_with_project_classpath(self):
        import subprocess
        from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry

        java = Path("/home/anthony/tools/jdk11/bin/java")
        javac = Path("/home/anthony/tools/jdk11/bin/javac")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dependency = root / "Dependency.java"
            dependency.write_text(
                "public class Dependency { int f(int x) { return x * 2; } }"
            )
            consumer = root / "Consumer.java"
            consumer.write_text(
                "public class Consumer { int f(int x) {"
                " if(x>2) return new Dependency().f(x); return 0; } }"
            )
            classes = root / "classes"
            classes.mkdir()
            subprocess.run(
                [str(javac), "-proc:none", "-d", str(classes), str(dependency)],
                check=True, capture_output=True, text=True,
            )
            without = ModuleRegistry()
            without.register(JavaCompilerModule(java=java, javac=javac))
            self.assertTrue(without.analyze(consumer)["diagnostics"])
            with_cp = ModuleRegistry()
            with_cp.register(JavaCompilerModule(
                java=java, javac=javac, classpath=(str(classes),),
            ))
            report = with_cp.analyze(consumer, strict=True)
            self.assertEqual(report["diagnostics"], [])
            self.assertEqual(report["fidelity"], "compiler_semantic_partial")
            self.assertTrue(report["features"]["has_call"])
