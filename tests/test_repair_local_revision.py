import copy,json
import pytest
from genesis.repair_lineage import SEED_GENOME,Envelope,Ledger
from genesis.repair_local_revision import changed_leaves,propose,paired_summary


def transport(genome):
    return lambda payload,timeout: {'usage':{'cost':.001},'choices':[{'message':{'tool_calls':[{'function':{'arguments':json.dumps(genome)}}]}}]}


def test_single_change_retains_parent_and_model_charge():
    child=copy.deepcopy(SEED_GENOME);child['playbook']='Check evidence before editing.'
    result=propose(SEED_GENOME,'training',Envelope(model='test'),Ledger(1),transport=transport(child))
    assert result['accepted_for_measurement'] and result['changed_leaves']==['playbook']
    assert result['calls'][0]['cost_usd']==.001 and not result['promoted']
    assert SEED_GENOME['playbook']==''


@pytest.mark.parametrize('changes',[{}, {'playbook':'x','instructions':'y'}, {'improver':'changed'}])
def test_invalid_revision_is_preserved_but_not_measured(changes):
    child={**copy.deepcopy(SEED_GENOME),**changes}
    result=propose(SEED_GENOME,'training',Envelope(model='test'),Ledger(1),transport=transport(child))
    assert result['genome'] is None and result['proposed_genome'] is not None
    assert not result['accepted_for_measurement'] and len(result['calls'])==1


def test_pairing_retains_regressions_and_unknown_cost():
    arm=lambda passed,cost:dict(solved=passed,calls=[dict(cost_usd=cost)])
    rows=[dict(case='A',replicate=1,parent=arm(False,.01),child=arm(True,.01)),
          dict(case='B',replicate=1,parent=arm(True,None),child=arm(False,.01))]
    result=paired_summary(rows)
    assert result['gains']==result['losses']==1 and not result['warrants_larger_test']
    assert result['unknown_cost_calls']==1 and not result['policy_promoted']
    with pytest.raises(ValueError):paired_summary(rows+[rows[0]])
