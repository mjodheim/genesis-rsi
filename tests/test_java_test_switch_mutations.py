from pathlib import Path

from genesis import java_test_switch_mutations as jts


def test_guides_missing_switch_case_from_literal_assertion(tmp_path: Path) -> None:
    src = tmp_path / "src" / "main" / "Escaper.java"
    test = tmp_path / "src" / "test" / "EscaperTest.java"
    src.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    src.write_text(
        """import java.io.Writer;
class Escaper {
    static void escape(Writer out, char ch) throws Exception {
        switch (ch) {
            case '"':
                out.write('\\\\');
                out.write('"');
                break;
            case '\\\\':
                out.write('\\\\');
                out.write('\\\\');
                break;
            default:
                out.write(ch);
                break;
        }
    }
}
""",
        encoding="utf-8",
    )
    test.write_text(
        """class EscaperTest {
    void testHash() {
        assertEquals("a\\\\#b", Escaper.escape("a#b"));
    }
}
""",
        encoding="utf-8",
    )
    result = jts.generate(tmp_path, include_prefixes=["src/main"], max_candidates=100)
    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert "case '#':" in candidate["content_utf8"]
    assert "out.write('#');" in candidate["content_utf8"]


def test_does_not_duplicate_existing_case(tmp_path: Path) -> None:
    src = tmp_path / "src" / "main" / "Escaper.java"
    test = tmp_path / "src" / "test" / "EscaperTest.java"
    src.parent.mkdir(parents=True)
    test.parent.mkdir(parents=True)
    src.write_text(
        """import java.io.Writer;
class Escaper {
    static void escape(Writer out, char ch) throws Exception {
        switch (ch) {
            case '#':
                out.write('\\\\');
                out.write('#');
                break;
            default:
                out.write(ch);
                break;
        }
    }
}
""",
        encoding="utf-8",
    )
    test.write_text(
        """class EscaperTest {
    void testHash() {
        assertEquals("a\\\\#b", Escaper.escape("a#b"));
    }
}
""",
        encoding="utf-8",
    )
    result = jts.generate(tmp_path, include_prefixes=["src/main"], max_candidates=100)
    assert result["candidate_count"] == 0


def test_requires_literal_test_evidence(tmp_path: Path) -> None:
    src = tmp_path / "src" / "main" / "Escaper.java"
    src.parent.mkdir(parents=True)
    src.write_text(
        """class Escaper {
    static void f(char ch) {
        switch (ch) {
            default:
                break;
        }
    }
}
""",
        encoding="utf-8",
    )
    result = jts.generate(tmp_path, include_prefixes=["src/main"], max_candidates=100)
    assert result["candidate_count"] == 0
