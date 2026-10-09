import json
from pathlib import Path
import shutil
import pytest
from scripts.audit_repair_stall_trial import audit
from genesis.repair_self_improvement import sealed

SOURCE=Path(__file__).resolve().parents[1]/'experiment/bench/DEV_REPAIR_STALL_RECOVERY1'


def test_public_audit_is_read_only_and_consistent():
    assert audit(SOURCE)['stored_evidence_consistent']
    assert not (SOURCE/'experience.sqlite').exists()


def test_resealed_success_claim_cannot_override_case_receipts(tmp_path):
    (tmp_path/'PLAN.json').write_bytes((SOURCE/'PLAN.json').read_bytes())
    shutil.copytree(SOURCE/'snapshot',tmp_path/'snapshot')
    result=json.loads((SOURCE/'RESULT.json').read_text())
    result.pop('result_digest');result['all_solved']=False
    (tmp_path/'RESULT.json').write_text(json.dumps(sealed(result,'result_digest')))
    with pytest.raises(ValueError,match='success count'):
        audit(tmp_path)
