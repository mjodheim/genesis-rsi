"""Check the independent read-only auditor also detects digest and statistic tampering."""
from __future__ import annotations

from copy import deepcopy
import pytest

from tools.audit_circuit2_frozen_record import EvidenceError, read_json, verify, ROOT
from genesis.trust_root import digest_of


@pytest.fixture(scope="module")
def original():
    return (
        read_json(ROOT / "experiment/engine/CIRCUIT2/PLAN.json"),
        read_json(ROOT / "experiment/engine/CIRCUIT2/RESULT.json")
    )


def test_published_records_reconstruct_with_verified_historical_machinery(original):
    report = verify(*original)
    assert report["total_lineages"] == 125
    assert report["historical_machinery_files_checked"] == 4
    assert report["paired_checks"]["learned2_against_explore"] == {
        "wins": 7, "losses": 13, "ties": 10,
    }


def test_tampered_aggregate_fails_even_with_recomputed_outer_digest(original):
    plan, result = deepcopy(original)
    result["H2"]["learning_gain_mean"]["learned2"] += 0.5
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="mean mismatch"):
        verify(plan, result)


def test_tampered_pair_p_value_fails_even_with_recomputed_outer_digest(original):
    plan, result = deepcopy(original)
    result["H2"]["learned2_against_explore"]["one_sided_sign_test_p"] = 0.01
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="p-value mismatch"):
        verify(plan, result)


def test_wrong_historical_machinery_digest_fails_even_if_plan_resealed(original):
    plan, result = deepcopy(original)
    plan["machinery_digests"]["genesis/circuit_tasks.py"] = "0"*64
    plan["plan_digest"] = digest_of({k:v for k,v in plan.items() if k!="plan_digest"})
    result["plan_digest"] = plan["plan_digest"]
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="machinery digest mismatch"):
        verify(plan, result)


def test_wrong_ledger_link_refused(original):
    plan, result = deepcopy(original)
    result["plan_digest"] = "f"*64
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="not linked to plan"):
        verify(plan, result)



def test_forged_ridge_feature_vector_is_refused_even_when_resealed(original):
    plan, result = deepcopy(original)
    result["rankers"]["learned10"]["weights"].pop()
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="13-feature coefficients"):
        verify(plan, result)


def test_forged_per_trial_gain_is_refused_even_when_resealed(original):
    plan, result = deepcopy(original)
    result["H2"]["gain_per_trial"]["learned2"] = 0.99
    result["result_digest"] = digest_of({k:v for k,v in result.items() if k!="result_digest"})
    with pytest.raises(EvidenceError, match="per-trial gain mismatch"):
        verify(plan, result)
