from pathlib import Path
import tempfile
import unittest

from genesis import java_string_literal_mutations as jsl


class StringLiteralClosureTests(unittest.TestCase):
    def test_closes_ascii_case_variants_in_repeated_string_predicate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = root / "src" / "TokenParser.java"
            p.parent.mkdir(parents=True)
            p.write_text(
                """class TokenParser {
    boolean accepts(String token) {
        if (token.check("ab") || token.check("-ab")) {
            return true;
        }
        return false;
    }
}
""",
                encoding="utf-8",
            )
            result = jsl.generate(
                root, include_prefixes=["src"], max_candidates=100
            )
            self.assertEqual(result["candidate_count"], 1)
            text = result["candidates"][0]["content_utf8"]
            self.assertIn('token.check("AB")', text)
            self.assertIn('token.check("-AB")', text)
            self.assertEqual(
                result["candidates"][0]["external_model_calls"], 0
            )


if __name__ == "__main__":
    unittest.main()
