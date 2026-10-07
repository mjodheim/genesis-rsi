from pathlib import Path

from genesis import java_empty_segment_parser_mutations as jem


def test_completes_empty_middle_segment_from_source_local_shape(tmp_path: Path) -> None:
    p = tmp_path / "src" / "TokenParser.java"
    p.parent.mkdir()
    p.write_text(
        """class TokenParser {
    static Token parse(String text) {
        if (text.charAt(1) != ':') {
            throw new IllegalArgumentException();
        }
        char middle0 = text.charAt(2);
        char middle1 = text.charAt(3);
        if (middle0 < 'A' || middle1 > 'Z') {
            throw new IllegalArgumentException();
        }
        if (text.length() == 4) {
            return new Token(text.substring(0, 1), text.substring(2, 4));
        }
        return new Token(text.substring(0, 1), text.substring(2, 4), text.substring(5));
    }
}
""",
        encoding="utf-8",
    )
    result = jem.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 1
    source = result["candidates"][0]["content_utf8"]
    assert "if (middle0 == ':')" in source
    assert 'return new Token(text.substring(0, 1), "", text.substring(3));' in source
    assert result["candidates"][0]["external_model_calls"] == 0


def test_delimiter_and_identifiers_are_mined_not_hardcoded(tmp_path: Path) -> None:
    p = tmp_path / "src" / "RouteParser.java"
    p.parent.mkdir()
    p.write_text(
        """class RouteParser {
    static Route read(String raw) {
        if (raw.charAt(2) != '-') throw new IllegalArgumentException();
        char segment = raw.charAt(3);
        char next = raw.charAt(4);
        if (raw.length() == 5) return new Route(raw.substring(0, 2), raw.substring(3, 5));
        return new Route(raw.substring(0, 2), raw.substring(3, 5), raw.substring(6));
    }
}
""",
        encoding="utf-8",
    )
    result = jem.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 1
    source = result["candidates"][0]["content_utf8"]
    assert "if (segment == '-')" in source
    assert 'new Route(raw.substring(0, 2), "", raw.substring(4))' in source


def test_requires_three_component_constructor_shape(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Parser.java"
    p.parent.mkdir()
    p.write_text(
        """class Parser {
    static Object parse(String value) {
        if (value.charAt(1) != ':') throw new IllegalArgumentException();
        char part = value.charAt(2);
        return value;
    }
}
""",
        encoding="utf-8",
    )
    result = jem.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 0
