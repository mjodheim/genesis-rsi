import sqlite3
import pytest

from genesis.adaptive_repair import RepairExperience
from scripts.run_promote_transformation_experience import append_suffix


def chain(tmp_path):
    source=RepairExperience(tmp_path/'source.sqlite')
    source.append('call',dict(cost_usd=None,request_sent=True))
    initial=source.events()
    source.append('transformation_trial',dict(policy_promoted=False,failed_cases=['A-1']))
    return initial,source.events()


def test_negative_evidence_and_unknown_charges_are_preserved(tmp_path):
    initial,final=chain(tmp_path);target=RepairExperience(tmp_path/'canonical.sqlite')
    target.append('call',dict(cost_usd=None,request_sent=True))
    append_suffix(target.path,initial,final)
    assert target.events()==final and target.events()[0]['data']['cost_usd'] is None
    append_suffix(target.path,initial,final)
    assert target.events()==final  # pointer-update interruption recovery


def test_divergent_memory_and_rewritten_prefix_are_refused(tmp_path):
    initial,final=chain(tmp_path);target=RepairExperience(tmp_path/'canonical.sqlite')
    target.append('call',dict(cost_usd=None,request_sent=True))
    target.append('other',dict(concurrent=True));before=target.events()
    with pytest.raises(ValueError,match='changed'):append_suffix(target.path,initial,final)
    assert target.events()==before
    with pytest.raises(ValueError,match='rewrote'):append_suffix(target.path,initial,final[1:])
    assert target.events()==before


def test_invalid_suffix_rolls_back_whole_transaction(tmp_path):
    initial,final=chain(tmp_path);target=RepairExperience(tmp_path/'canonical.sqlite')
    target.append('call',dict(cost_usd=None,request_sent=True))
    invalid=final+[dict(kind='bad',previous_digest='wrong',scope='released_development',data={})]
    with pytest.raises(ValueError,match='suffix'):append_suffix(target.path,initial,invalid)
    assert target.events()==initial
