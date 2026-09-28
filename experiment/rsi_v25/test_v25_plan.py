from pathlib import Path

PLAN = Path(__file__).with_name("V25_TRANSFER_DIAGNOSIS_AND_PROSPECTIVE_PLAN.md")

def test_v25_plan_preserves_v24_negative_and_forbids_reuse():
    text = PLAN.read_text(encoding="utf-8")
    assert "valid negative L5 result" in text
    assert "V24 BrewTrack/Brewstead holdout tasks are forbidden" in text
    assert "no post-observation tuning" in text

def test_v25_requires_behavioral_and_causal_gates():
    text = PLAN.read_text(encoding="utf-8")
    assert "behavioral-diversity gate" in text
    assert "mechanism ablation" in text
    assert "zero tolerance" in text
