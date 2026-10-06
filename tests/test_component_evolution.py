from pathlib import Path

from genesis.evolution import component_evolution
from genesis.operators import universal
from genesis.trust_root import digest_of


ROOT = Path(__file__).resolve().parents[1]


def _operator() -> dict:
    before = "def pick(items):\n    return items[1]\n"
    after = "def pick(items):\n    return items[0]\n"
    return universal.learn_from_validated_pair(
        before,
        after,
        source_path="source.py",
        source_result_digest=digest_of({"before": before, "after": after, "passed": True}),
    )


def test_g6_diagnoses_same_role_anchor_overfit() -> None:
    parent_source = (ROOT / "genesis/operators/universal.py").read_text(encoding="utf-8")
    failed = component_evolution.TrainingExample(
        "method-call",
        "Program.cs",
        "class P { static int[] V()=>new[]{1,2}; static int F()=>V()[1]; }\n",
        True,
    )
    diagnosis = component_evolution.diagnose_context_overfit(
        parent_source,
        _operator(),
        failed,
    )

    assert diagnosis["diagnosis"] == "anchor_context_over_specific"
    assert diagnosis["parent_candidate_count"] == 0
    assert diagnosis["same_semantic_role_token_count"] >= 1
    assert diagnosis["hidden_holdout_visible"] is False
    assert diagnosis["external_model_calls"] == 0


def test_g6_evolves_material_descendant_from_prior_examples() -> None:
    parent_source = (ROOT / "genesis/operators/universal.py").read_text(encoding="utf-8")
    operator = _operator()
    examples = [
        component_evolution.TrainingExample(
            "direct",
            "A.cs",
            "class P { static int F(int[] x)=>x[1]; }\n",
            True,
        ),
        component_evolution.TrainingExample(
            "method",
            "A.cs",
            "class P { static int[] V()=>new[]{1,2}; static int F()=>V()[1]; }\n",
            True,
        ),
        component_evolution.TrainingExample(
            "decoy-equality",
            "A.cs",
            "class P { static bool F(int x)=>x==1; }\n",
            False,
        ),
        component_evolution.TrainingExample(
            "decoy-call",
            "A.cs",
            "class P { static int G(int x)=>x; static int F()=>G(1); }\n",
            False,
        ),
    ]
    result = component_evolution.evolve_component(
        parent_source,
        operator=operator,
        failed_example=examples[1],
        training_examples=examples,
    )

    selected = result["selected_descendant"]
    assert result["candidate_count"] >= 2
    assert result["training_evidence_only"] is True
    assert result["hidden_holdout_visible"] is False
    assert result["external_model_calls"] == 0
    assert selected["source_sha256"] != selected["parent_source_sha256"]
    assert selected["external_model_calls_for_generation"] == 0
    chosen = next(
        item for item in result["candidates"]
        if item["descendant_digest"] == selected["descendant_digest"]
    )
    assert chosen["training"]["all_passed"] is True


def test_g6_descendant_preserves_non_subscript_safety() -> None:
    parent_source = (ROOT / "genesis/operators/universal.py").read_text(encoding="utf-8")
    operator = _operator()
    failed = component_evolution.TrainingExample(
        "method",
        "A.cs",
        "class P { static int[] V()=>new[]{1,2}; static int F()=>V()[1]; }\n",
        True,
    )
    decoy = component_evolution.TrainingExample(
        "decoy",
        "A.cs",
        "class P { static bool F(int x)=>x<=1; }\n",
        False,
    )
    result = component_evolution.evolve_component(
        parent_source,
        operator=operator,
        failed_example=failed,
        training_examples=[failed, decoy],
    )
    selected = result["selected_descendant"]
    check = component_evolution.evaluate_training_examples(
        selected,
        operator=operator,
        examples=[decoy],
    )
    assert check["all_passed"] is True
