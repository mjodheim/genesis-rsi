from __future__ import annotations

import tempfile
from pathlib import Path
import unittest

from genesis import java_expression_mutations
from genesis import repair_strategist
from genesis.repair_ir import compose, plan_from_candidate, render_candidate


class RepairIrTests(unittest.TestCase):
    def test_composes_non_overlapping_edits(self) -> None:
        original = "class X { int a = 1; int b = 2; }\n"
        left_text = original.replace("a = 1", "a = 3")
        right_text = original.replace("b = 2", "b = 4")
        left = plan_from_candidate(
            path="src/X.java",
            original=original,
            candidate={
                "id": "left",
                "candidate_digest": "a" * 64,
                "operator": "integer_delta",
                "content_utf8": left_text,
            },
            score=50,
        )
        right = plan_from_candidate(
            path="src/X.java",
            original=original,
            candidate={
                "id": "right",
                "candidate_digest": "b" * 64,
                "operator": "integer_delta",
                "content_utf8": right_text,
            },
            score=50,
        )
        self.assertIsNotNone(left)
        self.assertIsNotNone(right)
        plan = compose(left, right)
        self.assertIsNotNone(plan)
        rendered = render_candidate(original, plan)
        self.assertIn("a = 3", rendered["content_utf8"])
        self.assertIn("b = 4", rendered["content_utf8"])
        self.assertEqual(rendered["plan"]["depth"], 2)


class ExpressionMutationTests(unittest.TestCase):
    def _project(self, root: Path) -> Path:
        p = root / "src" / "Joiners.java"
        p.parent.mkdir(parents=True)
        p.write_text(
            """class Joiners {
    String one(Object[] values, int start, int end, String sep) {
        int count = end - start;
        if (count <= 0) return "";
        StringBuilder out = new StringBuilder(
            (values[start] == null ? 12 : values[start].toString().length()) + sep.length());
        return out.toString();
    }

    String two(Object[] items, int from, int to, String delimiter) {
        int size = to - from;
        if (size <= 0) return "";
        StringBuilder out = new StringBuilder(
            (items[from] == null ? 12 : items[from].toString().length()) + delimiter.length());
        return out.toString();
    }
}
""",
            encoding="utf-8",
        )
        return p

    def test_generates_coordinated_sibling_expression_rewrite(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._project(root)
            result = java_expression_mutations.generate(
                root, include_prefixes=["src"], max_candidates=100
            )
            coordinated = [
                c for c in result["candidates"]
                if c["detail"]["mode"] == "coordinated_sibling_methods"
            ]
            self.assertTrue(coordinated)
            text = coordinated[0]["content_utf8"]
            self.assertIn("count * 12", text)
            self.assertIn("size * 12", text)
            self.assertEqual(coordinated[0]["detail"]["site_count"], 2)


class StrategistTests(unittest.TestCase):
    def _write_scalar(self, root: Path, name: str) -> str:
        rel = f"src/{name}.java"
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            f"""class {name} {{
    boolean f(int x) {{
        if (x < 2) return true;
        return false;
    }}
}}
""",
            encoding="utf-8",
        )
        return rel

    def test_focus_paths_are_a_hard_causal_route(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_scalar(root, "A")
            focus = self._write_scalar(root, "B")
            result = repair_strategist.generate(
                root,
                include_prefixes=["src"],
                focus_paths=[focus],
                max_candidates=80,
                per_family_budget=80,
            )
            self.assertGreater(result["candidate_count"], 0)
            self.assertTrue(result["causal_routing_enabled"])
            self.assertTrue(all(c["path"] == focus for c in result["candidates"]))

    def test_planner_emits_bounded_compositions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            focus = self._write_scalar(root, "A")
            result = repair_strategist.generate(
                root,
                include_prefixes=["src"],
                focus_paths=[focus],
                max_candidates=100,
                per_family_budget=100,
                composition_fraction=0.5,
            )
            self.assertGreater(result["composed_candidate_count"], 0)
            self.assertLessEqual(result["max_plan_depth"], 2)
            self.assertTrue(
                any(c["plan"]["depth"] == 2 for c in result["candidates"])
            )

    def test_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            focus = self._write_scalar(root, "A")
            kwargs = dict(
                include_prefixes=["src"],
                focus_paths=[focus],
                max_candidates=80,
                per_family_budget=80,
            )
            first = repair_strategist.generate(root, **kwargs)
            second = repair_strategist.generate(root, **kwargs)
            self.assertEqual(
                [c["candidate_digest"] for c in first["candidates"]],
                [c["candidate_digest"] for c in second["candidates"]],
            )
            self.assertEqual(first["strategy_digest"], second["strategy_digest"])


if __name__ == "__main__":
    unittest.main()
