import json
import pytest

from genesis.repair_lineage import SEED_GENOME, genome_digest
from genesis.repair_self_improvement import sealed
from genesis.repair_local_revision import paired_summary
from scripts.run_repair_branches_trial import verify


def fixture(folder, ungraded=False):
    plan = sealed(dict(cases=["Case-1"], replicates=1, seed_genome=SEED_GENOME,
                       envelope=dict(validations_per_case=6, model_requests_per_case=8),
                       spending_ceiling_usd=.2), "plan_digest")
    base = dict(files=[dict(path="src/A.java")], applicable=True)
    first = dict(base, parent="", candidate_digest="first", complete_paths=["src/A.java"])
    second = dict(base, parent="unknown" if ungraded else "first", candidate_digest="second", complete_paths=["src/A.java"])
    parent = sealed(dict(solved=False, validated=1, verdicts=[dict(candidate_digest="base")],
                         calls=[dict(round=1, cost_usd=.001, submission_results=[base])]), "arm_digest")
    child = sealed(dict(solved=True, validated=2,
                        verdicts=[dict(candidate_digest="first"), dict(candidate_digest="second")],
                        calls=[dict(round=1, cost_usd=.001, submission_results=[first]),
                               dict(round=2, cost_usd=.001, submission_results=[second])]), "arm_digest")
    rows = [dict(case="Case-1", replicate=1, order=["parent", "child"], parent=parent, child=child)]
    result = sealed(dict(plan_digest=plan["plan_digest"], rows=rows, summary=paired_summary(rows)), "result_digest")
    journal = [dict(case="Case-1", label=f"branches-r1-{arm}", genome=genome_digest(SEED_GENOME), call=c)
               for arm in ("parent", "child") for c in rows[0][arm]["calls"]]
    for name, body in (("PLAN.json", plan), ("RESULT.json", result),
                       ("JOURNAL.json", sealed(dict(calls=journal), "journal_digest"))):
        (folder / name).write_text(json.dumps(body))


def test_stored_branch_receipts_verify_parent_relationships(tmp_path):
    fixture(tmp_path)
    assert verify(tmp_path)["calls"] == 3


def test_ungraded_parent_reference_fails_verification(tmp_path):
    fixture(tmp_path, ungraded=True)
    with pytest.raises(ValueError, match="graded earlier"):
        verify(tmp_path)
