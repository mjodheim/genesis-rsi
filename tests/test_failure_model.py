from pathlib import Path

from genesis.learning import failure_model


def _miss(*, scheduled: int = 0, charged: int = 0, budget: int = 64, **extra) -> dict:
    result = {
        "report_digest": "miss",
        "candidate_budget": budget,
        "charged_candidate_executions": charged,
        "winner": None,
        "schedule": {
            "scheduled_count": scheduled,
            "family_input_counts": {"learned": 0, "retained": 0},
            "family_scheduled_counts": {},
        },
    }
    result.update(extra)
    return result


def test_g3_distinguishes_missing_representation(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("value: 1\n", encoding="utf-8")

    result = failure_model.diagnose(
        tmp_path,
        _miss(),
        target_prefixes=["config.yaml"],
    )

    assert result["primary_failure_class"] == "representation"
    assert result["solution_visible"] is False
    assert result["external_model_calls"] == 0


def test_g3_distinguishes_missing_operator_from_missing_search(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    operator_gap = failure_model.diagnose(
        tmp_path,
        _miss(scheduled=0, charged=0, budget=64),
        target_prefixes=["logic.py"],
    )
    search_gap = failure_model.diagnose(
        tmp_path,
        _miss(scheduled=64, charged=64, budget=64),
        target_prefixes=["logic.py"],
    )

    assert operator_gap["primary_failure_class"] == "operator"
    assert search_gap["primary_failure_class"] == "search"
    assert operator_gap["recommended_interventions"] != search_gap["recommended_interventions"]


def test_g3_can_attribute_retrieval_failure(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    run = _miss()
    run["schedule"]["family_input_counts"] = {"learned": 2, "retained": 1}

    result = failure_model.diagnose(
        tmp_path,
        run,
        target_prefixes=["logic.py"],
        retrieval_report={"applicable_count": 3, "emitted_count": 0},
    )

    assert result["primary_failure_class"] == "retrieval"
    assert "repair_memory_index_or_applicability_matching" in result["recommended_interventions"]


def test_g3_toolchain_failure_preempts_operator_learning(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    result = failure_model.diagnose(
        tmp_path,
        _miss(),
        target_prefixes=["logic.py"],
        toolchain_report={
            "packs": [{"language": "python", "core_ready": False}],
        },
    )

    assert result["primary_failure_class"] == "toolchain"
    assert result["missing_toolchain_languages"] == ["python"]


def test_g3_returns_underdetermined_when_evidence_competes(tmp_path: Path) -> None:
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")

    result = failure_model.diagnose(
        tmp_path,
        _miss(scheduled=64, charged=64, budget=64, missing_documentation=True),
        target_prefixes=["logic.py"],
    )

    assert result["primary_failure_class"] in {"search", "underdetermined"}
    assert result["solution_visible"] is False
