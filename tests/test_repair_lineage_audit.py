import json

import pytest

from audit_repair_lineage import audit_lineage
from genesis.repair_lineage import SEED_GENOME, checked_genome, genome_digest
from genesis.trust_root import digest_of

ENVELOPE = {"validations_per_case": 6, "model_requests_per_case": 8}


def seal(path, body, key):
    path.write_text(json.dumps({**body, key: digest_of(body)}))


def evaluation(genome, solved):
    cases = {name: {"solved": flag, "validated": 1, "calls": [{}]} for name, flag in solved.items()}
    return {"genome_digest": genome_digest(genome), "cases": cases, "solved": sum(solved.values()), "cost_usd": 0.01}


def lineage(folder, child_solved, decision):
    seed = checked_genome(SEED_GENOME)
    child = checked_genome({**SEED_GENOME, "playbook": "Read before proposing."})
    plan = {"training_cases": ["t1"], "selection_cases": ["s1"], "seed_genome": seed,
            "seed_genome_digest": genome_digest(seed), "envelope": ENVELOPE}
    seal(folder / "PLAN.json", plan, "plan_digest")
    seal(folder / "GEN0_EVALUATION.json", evaluation(seed, {"t1": False, "s1": True}), "evaluation_digest")
    seal(folder / "GEN1_EVALUATION.json", evaluation(child, child_solved), "evaluation_digest")
    final = child if decision == "promoted" else seed
    seal(folder / "LINEAGE.json", {
        "plan_digest": digest_of(plan), "seed_genome_digest": genome_digest(seed),
        "generations": [{"generation": 1, "parent_generation": 0, "parent_digest": genome_digest(seed),
                         "decision": decision, "genome": child, "genome_digest": genome_digest(child)}],
        "final_generation": 1 if decision == "promoted" else 0, "final_genome": final,
        "final_genome_digest": genome_digest(final),
    }, "lineage_digest")


def test_audit_recomputes_a_promotion(tmp_path):
    lineage(tmp_path, {"t1": True, "s1": True}, "promoted")
    report = audit_lineage(tmp_path)
    assert report["final_generation"] == 1 and report["solved_per_evaluated_generation"] == {0: 1, 1: 2}


def test_audit_refuses_a_promotion_the_records_do_not_support(tmp_path):
    lineage(tmp_path, {"t1": True, "s1": False}, "promoted")
    with pytest.raises(AssertionError):
        audit_lineage(tmp_path)


def test_audit_refuses_an_edited_record(tmp_path):
    lineage(tmp_path, {"t1": False, "s1": True}, "rejected")
    assert audit_lineage(tmp_path)["final_generation"] == 0
    path = tmp_path / "GEN1_EVALUATION.json"
    path.write_text(path.read_text().replace('"solved": 1', '"solved": 2'))
    with pytest.raises(AssertionError):
        audit_lineage(tmp_path)
