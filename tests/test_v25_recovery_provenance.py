"""Recovery cannot silently replace a canonical negative or claim fresh transfer."""
import copy
import json

import pytest

from scripts import replicate_v25_consumed_result as recovery


def observed():
    return json.loads(recovery.OBSERVED.read_text())


def test_replication_must_match_the_original_negative():
    record = observed()
    recovery.require_same_negative(record, record["original_adjudication"])
    changed = copy.deepcopy(record["original_adjudication"])
    changed["fresh_global_utilities"]["g3"][1] += 1
    with pytest.raises(ValueError, match="never rescore"):
        recovery.require_same_negative(record, changed)


def test_replication_cannot_upgrade_or_call_a_consumed_bank_fresh():
    record = observed()
    changed = copy.deepcopy(record["original_adjudication"])
    changed["v25_l5_positive"] = True
    with pytest.raises(ValueError):
        recovery.require_same_negative(record, changed)
    record["holdout_consumed"] = False
    with pytest.raises(ValueError):
        recovery.require_same_negative(record, record["original_adjudication"])


def test_recovered_traces_keep_their_explicit_origin():
    if not recovery.REPLICATION.exists():
        pytest.skip("Recovery has not executed")
    replication = json.loads(recovery.REPLICATION.read_text())
    if replication["status"] != "COMPLETED":
        pytest.skip("Recovery is partial and cannot claim completion")
    attempt = json.loads(recovery.ATTEMPT.read_text())
    assert attempt["original_raw_traces_unavailable"] is True
    assert attempt["canonical_attempts"] == attempt["recovery_replication_runs"] == 1
    assert attempt["new_fresh_scientific_attempt"] is False
    assert attempt["evidence_provenance"] == "RAW_TRACES_FROM_DECLARED_REPLICATION_OF_ALREADY_CONSUMED_BANK"
    assert attempt["recovery_matches_observed_negative"] is True
