from pathlib import Path

import pytest

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


def test_rejects_relative_traversal_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "externe.py").write_text("x = 1\n", encoding="utf-8")
    result = {
        "report_digest": "miss-c",
        "candidate_budget": 256,
        "charged_candidate_executions": 0,
        "winner": None,
        "schedule": {
            "scheduled_count": 0,
            "family_input_counts": {"learned": 0, "retained": 0},
            "family_scheduled_counts": {},
        },
    }

    with pytest.raises(ValueError):
        capability_gaps.diagnose(root, result, target_prefixes=["../externe.py"])


def test_rejects_absolute_target_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "externe.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    result = {
        "report_digest": "miss-c",
        "candidate_budget": 256,
        "charged_candidate_executions": 0,
        "winner": None,
        "schedule": {
            "scheduled_count": 0,
            "family_input_counts": {"learned": 0, "retained": 0},
            "family_scheduled_counts": {},
        },
    }

    with pytest.raises(ValueError):
        capability_gaps.diagnose(root, result, target_prefixes=[str(outside)])


def test_rejects_symlink_to_file_outside_root(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "externe.py"
    outside.write_text("x = 1\n", encoding="utf-8")
    (root / "lien.py").symlink_to(outside)
    result = {
        "report_digest": "miss-c",
        "candidate_budget": 256,
        "charged_candidate_executions": 0,
        "winner": None,
        "schedule": {
            "scheduled_count": 0,
            "family_input_counts": {"learned": 0, "retained": 0},
            "family_scheduled_counts": {},
        },
    }

    with pytest.raises(ValueError):
        capability_gaps.diagnose(root, result, target_prefixes=["lien.py"])

def test_nested_symlink_outside_root_does_not_leak_suffix(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    directory = root / "inside"
    directory.mkdir(parents=True)
    outside = tmp_path / "external.xyz"
    outside.write_text("private", encoding="utf-8")
    (directory / "external.xyz").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes root") as error:
        capability_gaps._target_suffixes(root, ["inside"])
    assert ".xyz" not in str(error.value)


def test_regular_nested_file_remains_in_scope(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    directory = root / "inside"
    directory.mkdir(parents=True)
    (directory / "legitimate.py").write_text("ok", encoding="utf-8")
    assert capability_gaps._target_suffixes(root, ["inside"]) == [".py"]
