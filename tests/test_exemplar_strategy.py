from pathlib import Path

from genesis import exemplar_strategy


def test_mines_observed_adjusted_subscripts_and_generates_analogy(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    target = source / "grid.js"
    target.write_text(
        "function a(x) { return rows[x]; }\n"
        "function b(x) { return rows[x - 1]; }\n",
        encoding="utf-8",
    )

    mined = exemplar_strategy.mine_subscript_exemplars(tmp_path)
    assert mined["x"][0]["delta"] == -1

    result = exemplar_strategy.generate(tmp_path)
    assert result["external_model_calls"] == 0
    assert result["candidate_count"] >= 1

    candidate = next(
        c for c in result["candidates"]
        if "return rows[x - 1]" in c["mutations"][0]["content_utf8"].splitlines()[0]
    )
    assert candidate["provenance"]["strategy_origin"] == "repository_observation"
    assert candidate["provenance"]["delta"] == -1


def test_does_not_invent_offset_when_repository_has_no_exemplar(tmp_path: Path) -> None:
    (tmp_path / "grid.js").write_text(
        "function a(x) { return rows[x]; }\n",
        encoding="utf-8",
    )

    result = exemplar_strategy.generate(tmp_path)

    assert result["candidate_count"] == 0


def test_acquires_identifier_agnostic_strategy_from_winner(tmp_path: Path) -> None:
    (tmp_path / "grid.js").write_text(
        "const a = rows[x];\nconst b = rows[x - 1];\n",
        encoding="utf-8",
    )
    generated = exemplar_strategy.generate(tmp_path)
    candidate = generated["candidates"][0]

    acquired = exemplar_strategy.acquire_strategy(candidate, result_digest="result123")

    assert acquired["kind"] == "subscript_identifier_delta"
    assert acquired["template_before"] == "[$IDENT]"
    assert acquired["template_after"] == "[$IDENT - 1]"
    assert acquired["source_of_transformation"] == "repository_observed_exemplar_plus_evaluator_selection"
    assert acquired["host_issue_specific_recipe"] is False
    assert len(acquired["strategy_digest"]) == 64
