"""Recovery must retain the original transport failure and every scientific byte."""
import copy
import json

import pytest

from experiment.rsi_v31 import campaign
from scripts import check_rsi_v31_transport_recovery as recovery


def test_metadata_recovery_preserves_original_failure_and_exact_raw():
    assert recovery.check() == {"metadata_finalization_verified": True, "original_index_preserved": True,
                                "raw_and_verdict_byte_exact": True, "candidate_evaluations_rerun": 0}
    original = json.loads(recovery.ORIGINAL.read_text())
    current = json.loads(campaign.ATTEMPT.read_text())
    assert original["status"] == "STARTED" and current["status"] == "COMPLETED"
    assert campaign.read_attempt()["status"] == "COMPLETED"


@pytest.mark.parametrize("part", ("original", "current", "receipt", "raw", "verdict"))
def test_metadata_recovery_rejects_edited_evidence(part):
    original = json.loads(recovery.ORIGINAL.read_text())
    current = json.loads(campaign.ATTEMPT.read_text())
    receipt = json.loads(recovery.RECEIPT.read_text())
    raw, verdict = campaign.RAW.read_bytes(), campaign.VERDICT.read_bytes()
    if part == "original":
        original["record_sha256"] = "0" * 64
    elif part == "current":
        current["canonical_attempts"] = 2
    elif part == "receipt":
        receipt["candidate_evaluations_rerun"] = 1
    elif part == "raw":
        raw = raw[:-10]
    else:
        verdict = verdict.replace(b"true", b"false", 1)
    with pytest.raises(Exception):
        recovery.validate(original, current, receipt, raw, verdict)


def test_completion_metadata_cannot_be_finalized_twice():
    with pytest.raises(ValueError, match="overwrite"):
        recovery.finalize("unused")
