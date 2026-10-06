from pathlib import Path

from run_g1_g5_foundation_demo import build_demo


ROOT = Path(__file__).resolve().parents[1]


def test_g1_g5_foundation_demo_composes_without_external_model() -> None:
    result = build_demo(ROOT)

    assert result["external_model_calls"] == 0
    assert result["g1"]["language"] == "python"
    assert result["g2"]["source_language"] == "python"
    assert {
        item["language"] for item in result["g2"]["transfers"]
    } == {"java", "typescript", "csharp"}
    assert all(
        item["candidate_count"] >= 1
        for item in result["g2"]["transfers"]
    )
    assert result["g3"]["primary_failure_class"] == "operator"
    assert set(result["g4"]["candidate_component_ids"]) == {
        "structural_operator_engine",
        "universal_operator_ir",
    }
    assert result["g4"]["selected_component_id"] is None
    assert set(result["g5"]["target_component_ids"]) == {
        "structural_operator_engine",
        "universal_operator_ir",
    }
    assert result["g5"]["arm_count"] >= 3
    assert result["g5"]["fresh_case_contents_visible_to_lineage"] is False
    assert result["g5"]["mutable_lineage_owns_verdict"] is False
