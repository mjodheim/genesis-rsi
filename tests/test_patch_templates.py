from pathlib import Path

from genesis import patch_templates


def test_learns_numeric_delta_and_reuses_identifier() -> None:
    t = patch_templates.learn_template(
        "var depth = 0;\n",
        "var depth = 1;\n",
        source_digest="result-a",
    )
    out = patch_templates.apply_template_to_line("var height = 0;\n", t)
    assert out == "var height = 1;\n"


def test_learns_inserted_subscript_delta_syntax() -> None:
    t = patch_templates.learn_template(
        "return currentArray[xPos];\n",
        "return currentArray[xPos - 1];\n",
        source_digest="result-b",
    )
    out = patch_templates.apply_template_to_line("return rows[index];\n", t)
    assert out == "return rows[index - 1];\n"


def test_learns_range_start_change() -> None:
    t = patch_templates.learn_template(
        "for _ in 1..RETRY_ATTEMPTS {\n",
        "for _ in 0..RETRY_ATTEMPTS {\n",
        source_digest="result-c",
    )
    out = patch_templates.apply_template_to_line("for attempt in 1..MAX_ATTEMPTS {\n", t)
    assert out == "for attempt in 0..MAX_ATTEMPTS {\n"


def test_learn_from_texts_rejects_line_count_change() -> None:
    assert patch_templates.learn_from_texts(
        "a = 1\n",
        "a = 1\nb = 2\n",
        source_digest="x",
    ) == ()


def test_generate_creates_candidate_without_touching_source(tmp_path: Path) -> None:
    target = tmp_path / "logic.cs"
    target.write_text("var depth = 0;\n", encoding="utf-8")
    t = patch_templates.learn_template(
        "var count = 0;\n",
        "var count = 1;\n",
        source_digest="r",
    )
    result = patch_templates.generate(tmp_path, [t])
    assert result["candidate_count"] == 1
    assert "var depth = 1;" in result["candidates"][0]["mutations"][0]["content_utf8"]
    assert target.read_text() == "var depth = 0;\n"
