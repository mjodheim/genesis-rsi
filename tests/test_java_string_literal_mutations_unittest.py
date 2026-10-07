from pathlib import Path
import tempfile
import unittest

from genesis import java_string_literal_mutations as jsl
from genesis import repair_strategist


class StringLiteralClosureTests(unittest.TestCase):
    def test_adds_missing_ascii_case_variants_without_literal_hardcoding(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"src"/"Parser.java"
            p.parent.mkdir()
            p.write_text(
                'class Parser { boolean f(String s) {\n'
                '  if (s.matches("ab") || s.matches("-ab")) {\n'
                '    return true;\n'
                '  }\n'
                '  return false;\n'
                '} }\n',
                encoding="utf-8",
            )
            result=jsl.generate(root,include_prefixes=["src"],max_candidates=20)
            self.assertEqual(result["candidate_count"],1)
            text=result["candidates"][0]["content_utf8"]
            self.assertIn('s.matches("AB")',text)
            self.assertIn('s.matches("-AB")',text)
            self.assertEqual(result["candidates"][0]["external_model_calls"],0)

    def test_requires_repeated_same_predicate_in_or_chain(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"src"/"Parser.java"
            p.parent.mkdir()
            p.write_text(
                'class Parser { boolean f(String s) {\n'
                '  if (s.matches("ab")) { return true; }\n'
                '  return false;\n'
                '} }\n',
                encoding="utf-8",
            )
            result=jsl.generate(root,include_prefixes=["src"],max_candidates=20)
            self.assertEqual(result["candidate_count"],0)

    def test_strategist_routes_new_family_through_repair_plan(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            p=root/"src"/"Parser.java"
            p.parent.mkdir()
            p.write_text(
                'class Parser { boolean f(String s) {\n'
                '  if (s.matches("xy") || s.matches("-xy")) {\n'
                '    return true;\n'
                '  }\n'
                '  return false;\n'
                '} }\n',
                encoding="utf-8",
            )
            result=repair_strategist.generate(
                root,include_prefixes=["src"],focus_paths=["src/Parser.java"],
                max_candidates=50,composition_fraction=0.2,
            )
            self.assertTrue(result["family_activation"]["java_string_literal"]["activated"])
            self.assertTrue(any(
                "java_string_literal_case_closure" in c["plan"]["component_operators"]
                for c in result["candidates"]
            ))
            self.assertEqual(result["external_model_calls"],0)


if __name__=="__main__":
    unittest.main()
