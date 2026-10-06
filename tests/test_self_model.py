from pathlib import Path

from genesis.core import self_model
from genesis.learning import failure_model


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_g4_builds_content_addressed_self_model() -> None:
    model = self_model.build_self_model(_repo_root())

    assert model["component_count"] >= 8
    assert model["external_model_calls"] == 0
    assert "trust_root" in model["trust_root_component_ids"]
    assert "language_substrate" in model["mutable_component_ids"]
    assert self_model.validate_self_model(model) == model


def test_g4_trust_root_is_never_a_mutable_target(tmp_path: Path) -> None:
    model = self_model.build_self_model(_repo_root())
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    diagnosis = failure_model.diagnose(
        tmp_path,
        {
            "report_digest": "eval-fail",
            "candidate_budget": 1,
            "charged_candidate_executions": 0,
            "winner": None,
            "evaluator_status": "invalid",
            "schedule": {
                "scheduled_count": 0,
                "family_input_counts": {},
                "family_scheduled_counts": {},
            },
        },
        target_prefixes=["logic.py"],
    )

    target = self_model.choose_intervention_target(model, diagnosis)

    assert diagnosis["primary_failure_class"] == "evaluation"
    assert target["selected_component_id"] is None
    assert target["trust_root_modification_allowed"] is False
    assert "lineage_must_not_modify_it" in target["reason"]


def test_g4_maps_operator_failure_to_operator_machinery(tmp_path: Path) -> None:
    model = self_model.build_self_model(_repo_root())
    (tmp_path / "logic.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    diagnosis = failure_model.diagnose(
        tmp_path,
        {
            "report_digest": "op-fail",
            "candidate_budget": 64,
            "charged_candidate_executions": 0,
            "winner": None,
            "schedule": {
                "scheduled_count": 0,
                "family_input_counts": {"learned": 0, "retained": 0},
                "family_scheduled_counts": {},
            },
        },
        target_prefixes=["logic.py"],
    )

    target = self_model.choose_intervention_target(model, diagnosis)

    assert diagnosis["primary_failure_class"] == "operator"
    assert target["selected_component_id"] is None
    assert set(target["candidate_component_ids"]) == {
        "structural_operator_engine",
        "universal_operator_ir",
    }
    assert target["reason"] == "multiple_mutable_components_match_failure"


def test_g4_source_identity_changes_when_component_bytes_change(tmp_path: Path) -> None:
    root = tmp_path
    path = root / "genesis/languages"
    path.mkdir(parents=True)
    target = path / "substrate.py"
    target.write_text("x = 1\n", encoding="utf-8")

    # Other declared components may be missing in this fixture; their status is
    # recorded rather than hidden.
    first = self_model.build_self_model(root)
    target.write_text("x = 2\n", encoding="utf-8")
    second = self_model.build_self_model(root)

    first_component = next(
        item for item in first["components"] if item["component_id"] == "language_substrate"
    )
    second_component = next(
        item for item in second["components"] if item["component_id"] == "language_substrate"
    )

    assert first_component["source_identity"]["sha256"] != second_component["source_identity"]["sha256"]
    assert first["self_model_digest"] != second["self_model_digest"]
