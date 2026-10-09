import json
from pathlib import Path
import pytest
from genesis.repair_self_improvement import sealed
from scripts.audit_repair_contract_trial import audit
SOURCE=Path(__file__).resolve().parents[1]/'experiment/bench/DEV_REPAIR_CONTRACT_TRANSFER1'


def test_recorded_gates_have_twelve_compilations():
    result=audit(SOURCE)
    assert result['positive_cases']==result['negative_cases']==3
    assert result['candidate_compilations']==12
    assert not result['independent_execution_replication']


def test_resealed_false_summary_is_rejected(tmp_path):
    (tmp_path/'PLAN.json').write_bytes((SOURCE/'PLAN.json').read_bytes())
    result=json.loads((SOURCE/'RESULT.json').read_text());result.pop('result_digest')
    result['positive_transfer_cases']=4
    (tmp_path/'RESULT.json').write_text(json.dumps(sealed(result,'result_digest')))
    with pytest.raises(ValueError,match='summary'):audit(tmp_path)
