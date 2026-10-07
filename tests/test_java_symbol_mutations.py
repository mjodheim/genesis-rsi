from pathlib import Path

from genesis import java_symbol_mutations as jsm


def test_coordinated_sibling_symbol_substitution(tmp_path: Path) -> None:
    p = tmp_path / "src" / "ClockUtil.java"
    p.parent.mkdir()
    before = """class ClockUtil {
    int compare(Clock a, Clock b) {
        int hint = Clock.HOUR_OF_DAY;
        return a.get(Clock.HOUR) == b.get(Clock.HOUR) ? hint : 0;
    }
}
"""
    p.write_text(before, encoding="utf-8")
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    expected = "return a.get(Clock.HOUR_OF_DAY) == b.get(Clock.HOUR_OF_DAY) ? hint : 0;"
    hits = [c for c in result["candidates"] if expected in c["content_utf8"]]
    assert hits
    assert hits[0]["detail"]["mode"] == "coordinated_line"
    assert hits[0]["detail"]["site_count"] == 2


def test_does_not_invent_unseen_sibling_symbol(tmp_path: Path) -> None:
    p = tmp_path / "src" / "ClockUtil.java"
    p.parent.mkdir()
    p.write_text(
        """class ClockUtil {
    int read(Clock a) {
        return a.get(Clock.HOUR);
    }
}
""",
        encoding="utf-8",
    )
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 0


def test_single_site_variant_is_generated(tmp_path: Path) -> None:
    p = tmp_path / "src" / "ModeUtil.java"
    p.parent.mkdir()
    p.write_text(
        """class ModeUtil {
    int choose(Mode m) {
        int fallback = Mode.SAFE;
        return m.code(Mode.FAST);
    }
}
""",
        encoding="utf-8",
    )
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert any(
        "return m.code(Mode.SAFE);" in c["content_utf8"]
        and c["detail"]["mode"] == "single_site"
        for c in result["candidates"]
    )


def test_round_robin_across_files(tmp_path: Path) -> None:
    for name in ("A", "B"):
        p = tmp_path / "src" / f"{name}.java"
        p.parent.mkdir(exist_ok=True)
        p.write_text(
            f"""class {name} {{
    int f(K x, K y) {{
        int other = K.BETA;
        return x.get(K.ALPHA) == y.get(K.ALPHA) ? other : 0;
    }}
}}
""",
            encoding="utf-8",
        )
    result = jsm.generate(tmp_path, include_prefixes=["src"], max_candidates=2)
    assert [c["path"] for c in result["candidates"]] == ["src/A.java", "src/B.java"]
