import json
import pytest
from genesis.repair_lineage import SEED_GENOME, genome_digest
from genesis.repair_self_improvement import sealed
from genesis.repair_local_revision import paired_summary
from scripts.run_repair_transactions_trial import verify
from test_repair_feedback_trial import fixture


def transaction_fixture(folder, bad_mode=False):
    fixture(folder)
    plan = json.loads((folder / "PLAN.json").read_text())
    plan.pop("plan_digest")
    plan["seed_genome"] = SEED_GENOME
    plan = sealed(plan, "plan_digest")
    (folder / "PLAN.json").write_text(json.dumps(plan))
    result = json.loads((folder / "RESULT.json").read_text())
    result.pop("result_digest")
    result["plan_digest"] = plan["plan_digest"]
    row = result["rows"][0]
    journal = []
    for arm in ("parent", "child"):
        row[arm].pop("arm_digest")
        proposal = {"files": [{"path": "src/A.java"}]} if arm == "child" else {"edits": []}
        if bad_mode and arm == "child":
            proposal = {"edits": []}
        row[arm]["calls"][0]["submission_results"] = [proposal]
        row[arm] = sealed(row[arm], "arm_digest")
        journal.append(dict(case=row["case"], label=f"transactions-r1-{arm}",
                            genome=genome_digest(SEED_GENOME), call=row[arm]["calls"][0]))
    result["summary"] = paired_summary(result["rows"])
    (folder / "RESULT.json").write_text(json.dumps(sealed(result, "result_digest")))
    (folder / "JOURNAL.json").write_text(json.dumps(sealed(dict(calls=journal), "journal_digest")))


def test_transaction_trial_verifies_modes_genome_and_costs(tmp_path):
    transaction_fixture(tmp_path)
    assert verify(tmp_path)["verified"]


def test_child_using_single_file_submission_shape_is_rejected(tmp_path):
    transaction_fixture(tmp_path, bad_mode=True)
    with pytest.raises(ValueError, match="submission mode"):
        verify(tmp_path)
