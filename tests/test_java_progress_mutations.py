from pathlib import Path

from genesis import java_progress_mutations as jpm


def test_mines_progress_step_from_sibling_early_exit(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Parser.java"
    p.parent.mkdir()
    before = """package p;
class Parser {
    Object parse(Cursor cursor, boolean escaped) {
        int start = cursor.index();
        if (escaped && start == 0) {
            return null;
        }
        if (cursor.index() > 2) {
            advance(cursor);
            return null;
        }
        advance(cursor);
        return new Object();
    }
}
"""
    p.write_text(before, encoding="utf-8")
    result = jpm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    expected = """        if (escaped && start == 0) {
            advance(cursor);
            return null;
"""
    assert any(expected in c["content_utf8"] for c in result["candidates"])
    assert all(c["external_model_calls"] == 0 for c in result["candidates"])


def test_requires_source_local_pre_exit_exemplar(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Parser.java"
    p.parent.mkdir()
    p.write_text(
        """package p;
class Parser {
    Object parse(Cursor cursor) {
        if (cursor.index() == 0) {
            return null;
        }
        advance(cursor);
        Object result = new Object();
        return result;
    }
}
""",
        encoding="utf-8",
    )
    result = jpm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert result["candidate_count"] == 0


def test_round_robin_across_files(tmp_path: Path) -> None:
    for name in ("A", "B"):
        p = tmp_path / "src" / f"{name}.java"
        p.parent.mkdir(exist_ok=True)
        p.write_text(
            f"""class {name} {{
    Object parse(Cursor c, boolean x) {{
        if (x && c.index() == 0) {{
            return null;
        }}
        if (c.index() > 1) {{
            step(c);
            return null;
        }}
        step(c);
        return new Object();
    }}
}}
""",
            encoding="utf-8",
        )
    result = jpm.generate(tmp_path, include_prefixes=["src"], max_candidates=2)
    assert [c["path"] for c in result["candidates"]] == ["src/A.java", "src/B.java"]


def test_multiline_return_can_supply_progress_exemplar(tmp_path: Path) -> None:
    p = tmp_path / "src" / "Parser.java"
    p.parent.mkdir()
    p.write_text(
        """class Parser {
    Object parse(Cursor c, boolean flag) {
        int start = c.index();
        if (flag && start == 0) {
            return null;
        }
        if (c.index() > 1) {
            step(c);
            return make(
                c);
        }
        return null;
    }
}
""",
        encoding="utf-8",
    )
    result = jpm.generate(tmp_path, include_prefixes=["src"], max_candidates=100)
    assert any(
        """        if (flag && start == 0) {
            step(c);
            return null;
""" in candidate["content_utf8"]
        for candidate in result["candidates"]
    )
