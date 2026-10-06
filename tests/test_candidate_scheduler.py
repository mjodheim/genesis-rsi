from pathlib import Path

from genesis import candidate_scheduler, scalar_mutations


def test_target_scope_filters_memory_candidates_outside_prefix() -> None:
    candidates = [
        {"id": "a", "mutations": [{"path": "src/a.py", "content_utf8": "x"}]},
        {"id": "b", "mutations": [{"path": "other/b.py", "content_utf8": "x"}]},
    ]

    kept = candidate_scheduler.filter_target_scope(candidates, ["src/a.py"])

    assert [item["id"] for item in kept] == ["a"]


def test_fair_schedule_prevents_scalar_starvation() -> None:
    def items(prefix: str, count: int):
        return [
            {
                "id": f"{prefix}-{i}",
                "mutations": [{"path": f"src/{prefix}{i}.py", "content_utf8": str(i)}],
            }
            for i in range(count)
        ]

    scheduled = candidate_scheduler.fair_schedule(
        {
            "coordinated": items("c", 100),
            "scalar": items("s", 100),
            "learned": items("l", 100),
            "retained": items("r", 100),
            "exemplar": items("e", 100),
        },
        budget=256,
    )["candidates"]

    scalar_ids = [item["id"] for item in scheduled if item["id"].startswith("s-")]
    assert "s-72" in scalar_ids
    assert next(i for i, item in enumerate(scheduled, 1) if item["id"] == "s-72") <= 256


def test_composes_same_scalar_edit_across_two_files(tmp_path: Path) -> None:
    (tmp_path / "a.go").write_text("for i := 0; i <= retries; i++ {}\n", encoding="utf-8")
    (tmp_path / "b.go").write_text("for i := 0; i <= retries; i++ {}\n", encoding="utf-8")

    generated = scalar_mutations.generate(tmp_path, max_candidates=1000)["candidates"]
    coordinated = candidate_scheduler.compose_scalar_candidates(
        tmp_path,
        generated,
        max_sites=2,
        max_candidates=100,
    )["candidates"]

    winner = next(
        candidate
        for candidate in coordinated
        if candidate["provenance"]["operator"] == "comparison_boundary"
        and candidate["provenance"]["before"] == "<="
        and candidate["provenance"]["after"] == "<"
        and candidate["provenance"]["coordination_size"] == 2
    )

    assert len(winner["mutations"]) == 2
    assert all("i < retries" in item["content_utf8"] for item in winner["mutations"])


def test_composes_learned_template_across_distinct_files() -> None:
    learned = [
        {
            "id": "left",
            "provenance": {
                "generator": "learned_line_rewrite",
                "operator": "learned_template",
                "template_digest": "template-x",
            },
            "mutations": [
                {
                    "path": "a.go",
                    "expected_sha256": "a",
                    "content_utf8": "fixed a",
                }
            ],
        },
        {
            "id": "right",
            "provenance": {
                "generator": "learned_line_rewrite",
                "operator": "learned_template",
                "template_digest": "template-x",
            },
            "mutations": [
                {
                    "path": "b.go",
                    "expected_sha256": "b",
                    "content_utf8": "fixed b",
                }
            ],
        },
    ]

    result = candidate_scheduler.compose_learned_candidates(learned)

    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["provenance"]["strategy_origin"] == "prior_passing_evaluated_patch"
    assert [m["path"] for m in candidate["mutations"]] == ["a.go", "b.go"]
