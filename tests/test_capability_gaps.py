from pathlib import Path

from genesis import capability_gaps


def test_diagnoses_zero_candidate_yaml_as_generator_coverage_gap(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    target.write_text('options:\n  extra: ""\n', encoding="utf-8")
    result = {
        "report_digest": "miss-a",
        "candidate_budget": 256,
        "charged_candidate_executions": 0,
        "winner": None,
        "schedule": {
            "scheduled_count": 0,
            "family_input_counts": {
                "learned": 0,
                "retained": 0,
            },
            "family_scheduled_counts": {},
        },
    }

    diagnosis = capability_gaps.diagnose(
        tmp_path,
        result,
        target_prefixes=["config.yaml"],
    )

    assert "no_candidate_generated" in diagnosis["reasons"]
    assert "legacy_generator_text_kind_gap" in diagnosis["reasons"]
    assert diagnosis["legacy_unsupported_suffixes"] == [".yaml"]
    assert diagnosis["operator_acquisition_recommended"] is True
    assert diagnosis["external_model_calls"] == 0


def test_diagnoses_exhausted_budget_as_expressivity_or_search_gap(tmp_path: Path) -> None:
    target = tmp_path / "logic.ts"
    target.write_text("const x = items[1];\n", encoding="utf-8")
    result = {
        "report_digest": "miss-b",
        "candidate_budget": 256,
        "charged_candidate_executions": 256,
        "winner": None,
        "schedule": {
            "scheduled_count": 256,
            "family_input_counts": {
                "learned": 0,
                "retained": 0,
                "scalar": 900,
            },
            "family_scheduled_counts": {
                "scalar": 200,
            },
        },
    }

    diagnosis = capability_gaps.diagnose(
        tmp_path,
        result,
        target_prefixes=["logic.ts"],
    )

    assert "budget_exhausted_without_passing_candidate" in diagnosis["reasons"]
    assert "expressivity_or_search_gap" in diagnosis["reasons"]
    assert diagnosis["operator_acquisition_recommended"] is True
