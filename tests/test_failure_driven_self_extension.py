from pathlib import Path

import pytest

from genesis import failure_driven_self_extension as self_extension
from genesis import structural_operators


def _autonomous_miss(*, report_digest: str = "auto-miss") -> dict:
    return {
        "report_digest": report_digest,
        "candidate_budget": 256,
        "charged_candidate_executions": 0,
        "winner": None,
        "autonomous_passed": False,
        "schedule": {
            "scheduled_count": 0,
            "family_input_counts": {
                "learned": 0,
                "retained": 0,
                "scalar": 0,
            },
            "family_scheduled_counts": {},
        },
    }


def test_failure_to_new_operator_to_zero_model_reuse(tmp_path: Path) -> None:
    source = tmp_path / "task1"
    source.mkdir()
    config = source / "config.yaml"
    before = """options:
  extra_pip_packages: ""
  log_level: "info"
"""
    after = """options:
  extra_pip_packages: "skill-ovos-date-time"
  log_level: "info"
"""
    config.write_text(before, encoding="utf-8")

    diagnosis = self_extension.diagnose_failure(
        source,
        _autonomous_miss(),
        target_prefixes=["config.yaml"],
    )
    assert "no_candidate_generated" in diagnosis["reasons"]
    assert "legacy_generator_text_kind_gap" in diagnosis["reasons"]
    assert diagnosis["operator_acquisition_recommended"] is True

    # Chronology matters: the failure is retained before the passing repair is used.
    memory0 = self_extension.empty_memory()
    memory1 = self_extension.retain_gap(memory0, diagnosis)

    passing_candidate = {
        "mutations": [{
            "path": "config.yaml",
            "expected_absent": False,
            "content_utf8": after,
        }]
    }
    learned = self_extension.acquire_from_passing_candidate(
        memory1,
        source,
        passing_candidate,
        diagnosis=diagnosis,
        passing_result_digest="frozen-evaluator-pass-task1",
    )
    memory2 = learned["memory"]

    assert memory2["generation"] == 2
    assert len(memory2["operators"]) == 1
    assert learned["external_model_calls"] == 0
    assert memory2["events"][0]["kind"] == "gap_observed"
    assert memory2["events"][1]["kind"] == "operator_acquired"
    assert memory2["events"][0]["diagnosis_digest"] == memory2["events"][1]["diagnosis_digest"]

    # A later repository/task presents the same structural need.  Genesis now
    # emits the repair from retained capability without a model call.
    fresh = tmp_path / "task2"
    fresh.mkdir()
    fresh_config = fresh / "service.yaml"
    fresh_config.write_text(before, encoding="utf-8")

    reuse = self_extension.generate_candidates(
        memory2,
        fresh,
        include_prefixes=["service.yaml"],
    )
    candidates = reuse["candidate_set"]["candidates"]

    assert reuse["external_model_calls"] == 0
    assert len(candidates) == 1
    assert candidates[0]["mutations"][0]["content_utf8"] == after
    assert candidates[0]["provenance"]["strategy_origin"] == "prior_passing_evaluated_patch"
    assert candidates[0]["provenance"]["source_result_digest"] == "frozen-evaluator-pass-task1"


def test_acquisition_refuses_solution_when_gap_was_not_retained(tmp_path: Path) -> None:
    target = tmp_path / "logic.py"
    target.write_text("def f(items):\n    return items[1]\n", encoding="utf-8")
    diagnosis = self_extension.diagnose_failure(
        tmp_path,
        _autonomous_miss(),
        target_prefixes=["logic.py"],
    )
    candidate = {
        "mutations": [{
            "path": "logic.py",
            "expected_absent": False,
            "content_utf8": "def f(items):\n    return items[0]\n",
        }]
    }

    with pytest.raises(
        self_extension.FailureDrivenSelfExtensionError,
        match="retained before solution use",
    ):
        self_extension.acquire_from_passing_candidate(
            self_extension.empty_memory(),
            tmp_path,
            candidate,
            diagnosis=diagnosis,
            passing_result_digest="passing-result",
        )


def test_tampered_retained_operator_is_rejected_before_reuse(tmp_path: Path) -> None:
    before = "def f(items):\n    return items[1]\n"
    after = "def f(items):\n    return items[0]\n"
    operator = structural_operators.synthesize_operator(
        before,
        after,
        source_result_digest="prior-pass",
        source_path="logic.py",
        context_lines=0,
    )
    tampered = dict(operator)
    tampered["source_result_digest"] = "forged"

    with pytest.raises(ValueError, match="does not reproduce its digest"):
        structural_operators.apply_operator_to_text(before, tampered)


def test_diagnosis_refuses_an_autonomous_winner(tmp_path: Path) -> None:
    target = tmp_path / "logic.ts"
    target.write_text("const x = items[1];\n", encoding="utf-8")
    result = _autonomous_miss()
    result["winner"] = {"id": "already-solved"}
    result["autonomous_passed"] = True

    with pytest.raises(
        self_extension.FailureDrivenSelfExtensionError,
        match="requires an autonomous miss",
    ):
        self_extension.diagnose_failure(
            tmp_path,
            result,
            target_prefixes=["logic.ts"],
        )
