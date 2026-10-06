from __future__ import annotations

from pathlib import Path

from genesis import scalar_mutations


def test_generates_integer_boundary_and_boolean_candidates(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    target = source / "logic.py"
    target.write_text(
        "LIMIT = 30\n"
        "enabled = True\n"
        "def ok(x):\n"
        "    return x > LIMIT\n",
        encoding="utf-8",
    )

    result = scalar_mutations.generate(tmp_path, include_prefixes=["src"])

    assert result["external_model_calls"] == 0
    assert result["candidate_count"] > 0
    provenance = {item["provenance"]["operator"] for item in result["candidates"]}
    assert {"integer_delta", "boolean_toggle", "comparison_boundary"} <= provenance


def test_candidate_changes_exactly_one_source_site(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    target = source / "logic.js"
    original = "export const seats = capacity - 1;\n"
    target.write_text(original, encoding="utf-8")

    result = scalar_mutations.generate(tmp_path, include_prefixes=["src"])
    candidates = result["candidates"]

    assert candidates
    assert all(len(item["mutations"]) == 1 for item in candidates)
    assert all(item["mutations"][0]["path"] == "src/logic.js" for item in candidates)
    assert any("capacity - 0" in item["mutations"][0]["content_utf8"] for item in candidates)
    assert target.read_text(encoding="utf-8") == original


def test_excludes_tests_and_generated_directories(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "src" / "app.ts").write_text("const x = 1;\n", encoding="utf-8")
    (tmp_path / "tests" / "app.test.ts").write_text("const x = 2;\n", encoding="utf-8")
    (tmp_path / "node_modules" / "dep.js").write_text("const x = 3;\n", encoding="utf-8")

    result = scalar_mutations.generate(tmp_path)

    paths = {item["mutations"][0]["path"] for item in result["candidates"]}
    assert paths == {"src/app.ts"}


def test_candidate_budget_is_deterministic_hard_bound(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")

    first = scalar_mutations.generate(tmp_path, max_candidates=2)
    second = scalar_mutations.generate(tmp_path, max_candidates=2)

    assert first["candidate_count"] == 2
    assert first["truncated"] is True
    assert first["candidates"] == second["candidates"]
