import json
import pytest

from genesis.repair_local_revision import paired_summary
from genesis.repair_self_improvement import sealed
from scripts.run_repair_feedback_trial import verify


def fixture(folder, requests=1, ceiling=.2):
    plan = sealed(dict(cases=["Case-1"], replicates=1,
                       envelope=dict(validations_per_case=6, model_requests_per_case=8),
                       spending_ceiling_usd=ceiling), "plan_digest")
    (folder / "PLAN.json").write_text(json.dumps(plan))
    calls = [dict(cost_usd=.001) for _ in range(requests)]
    parent = sealed(dict(validated=1, solved=False, calls=calls), "arm_digest")
    child = sealed(dict(validated=1, solved=True, calls=calls), "arm_digest")
    rows = [dict(case="Case-1", replicate=1, order=["parent", "child"], parent=parent, child=child)]
    result = sealed(dict(plan_digest=plan["plan_digest"], rows=rows, summary=paired_summary(rows)), "result_digest")
    (folder / "RESULT.json").write_text(json.dumps(result))
    receipts = [dict(case="Case-1", label=f"feedback-r1-{arm}", call=call)
                for arm in ("parent", "child") for call in calls]
    (folder / "JOURNAL.json").write_text(json.dumps(sealed(dict(calls=receipts), "journal_digest")))


def test_complete_receipts_and_budgets(tmp_path):
    fixture(tmp_path)
    assert verify(tmp_path) == dict(verified=True, calls=2, independently_replicated=False)


def test_sealed_result_with_excessive_requests_is_rejected(tmp_path):
    fixture(tmp_path, requests=9)
    with pytest.raises(ValueError, match="request budget"):
        verify(tmp_path)


def test_sealed_result_with_excessive_spending_is_rejected(tmp_path):
    fixture(tmp_path, ceiling=.0001)
    with pytest.raises(ValueError, match="spending ceiling"):
        verify(tmp_path)


def test_sealed_journal_missing_a_paid_call_is_rejected(tmp_path):
    fixture(tmp_path)
    (tmp_path / "JOURNAL.json").write_text(json.dumps(sealed(dict(calls=[]), "journal_digest")))
    with pytest.raises(ValueError, match="journal differs"):
        verify(tmp_path)
