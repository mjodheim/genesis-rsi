from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from genesis import repair_strategist
from genesis.languages.experience import ExperienceLedger
from genesis.languages.understanding import JavaCompilerModule, ModuleRegistry
from scripts import run_autonomous_defects4j_lang as runner

JDK = Path("/home/anthony/tools/jdk11/bin")


@unittest.skipUnless((JDK / "javac").exists(), "JDK11 unavailable")
class G11PlannerTests(unittest.TestCase):
    def test_opt_in_ranking_and_persistent_use_without_baseline_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "src" / "A.java"
            file.parent.mkdir(parents=True)
            file.write_text(
                "class A {\n int f(int x) { if (x < 2) return 1; return 0; }\n}\n"
            )
            config = dict(
                include_prefixes=["src"],
                focus_paths=["src/A.java"],
                max_candidates=50,
                per_family_budget=50,
            )
            baseline = repair_strategist.generate(root, **config)
            registry = ModuleRegistry()
            registry.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
            ledger = ExperienceLedger(root/"observations.db")
            enhanced = repair_strategist.generate(
                root,
                understanding_registry=registry,
                understanding_ledger=ledger,
                understanding_rerank=True,
                **config,
            )
            self.assertNotIn("g11_understanding", baseline)
            self.assertGreater(baseline["candidate_count"], 0)
            self.assertEqual(enhanced["g11_understanding"]["analyzed_file_count"], 1)
            self.assertGreater(enhanced["g11_understanding"]["adjusted_atomic_plan_count"], 0)
            self.assertEqual(ledger.knowledge_summary()["observation_count"], 1)
            self.assertEqual(ledger.knowledge_summary()["independently_verified_full_suite_successes"], 0)
            self.assertEqual(
                repair_strategist.generate(root, **config)["strategy_digest"],
                baseline["strategy_digest"],
            )
            registry.remove("java")
            self.assertEqual(ExperienceLedger(root/"observations.db").knowledge_summary()["observation_count"], 1)

    def test_g11_shadow_mode_never_reorders_or_drops_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "src" / "A.java"
            source.parent.mkdir(parents=True)
            source.write_text(
                "class A { int f(int x) { if (x < 2) return 1; return 0; } }"
            )
            registry = ModuleRegistry()
            registry.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
            kwargs = dict(include_prefixes=["src"], focus_paths=["src/A.java"],
                          max_candidates=60, per_family_budget=60)
            baseline = repair_strategist.generate(root, **kwargs)
            shadow = repair_strategist.generate(
                root, understanding_registry=registry, **kwargs
            )
            self.assertEqual(
                [c["content_utf8"] for c in baseline["candidates"]],
                [c["content_utf8"] for c in shadow["candidates"]],
            )
            self.assertEqual(
                [c["plan"]["score"] for c in baseline["candidates"]],
                [c["plan"]["score"] for c in shadow["candidates"]],
            )
            self.assertEqual(shadow["g11_understanding"]["adjusted_atomic_plan_count"], 0)
            self.assertGreater(shadow["g11_understanding"]["potential_plan_count"], 0)
            self.assertFalse(shadow["g11_understanding"]["experimental_reranking_enabled"])

    def test_g11_reranking_without_analyzer_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "requires an understanding registry"):
                repair_strategist.generate(td, understanding_rerank=True)

    def test_domain_insights_in_planner_are_optional_and_read_only(self):
        from genesis.insights import InsightRegistry, JavaSecurityModule, JavaPerformanceModule
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            file = root / "src" / "A.java"
            file.parent.mkdir(parents=True)
            file.write_text(
                "class A { int f(int x) {"
                " for(int i=0;i<x;i++) { for(int j=0;j<x;j++) {} } return x; } }"
            )
            registry = ModuleRegistry()
            registry.register(JavaCompilerModule(java=JDK/"java", javac=JDK/"javac"))
            insights = InsightRegistry()
            insights.register(JavaSecurityModule())
            insights.register(JavaPerformanceModule())
            kwargs = dict(include_prefixes=["src"], focus_paths=["src/A.java"],
                          max_candidates=50, per_family_budget=50)
            baseline = repair_strategist.generate(root, **kwargs)
            report = repair_strategist.generate(
                root, understanding_registry=registry,
                insight_registry=insights, **kwargs
            )
            self.assertNotIn("g11_understanding", baseline)
            meta = report["g11_understanding"]["reports"][0]
            self.assertEqual(meta["domain_coverage"]["security"], "checked")
            self.assertEqual(meta["domain_coverage"]["performance"], "checked")
            self.assertTrue(any(f["rule_id"] == "nested-iteration-review"
                                for f in meta["domain_findings"]))
            self.assertEqual(repair_strategist.generate(root, **kwargs)["strategy_digest"],
                             baseline["strategy_digest"])

    def test_holdouts_are_excluded_and_already_selected_holdout_is_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            adapter = runner.LangDefects4JAdapter(Path(td))
            state = {
                "attempted_case_ids": [],
                "generation": 0,
                "campaign_id": "train-only-test",
                "machinery": {"machinery_digest": "m"},
            }
            with patch.object(runner, "_active_bug_ids", return_value=[23, 26, 34, 45]):
                selected = adapter.select_case(state)
            self.assertEqual(selected["case_id"], "34")
            state["current_case"] = {"case_id": "23"}
            with self.assertRaisesRegex(RuntimeError, "protected"):
                adapter.prepare_blind(state)


if __name__ == "__main__":
    unittest.main()
