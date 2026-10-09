import pytest
from genesis.repair_bench import Candidate
from genesis.repair_quality_learning import operator_policy
from genesis.repair_self_improvement import sealed
from genesis.repair_stall_recovery import recover, diagnose


def verdict(c, stage):
    return sealed(dict(candidate_digest=c.digest, plausible=stage=='passed', stopped_at=stage), 'verdict_digest')


def test_failure_can_create_descendant_and_duplicates_are_not_validated_twice():
    bad=Candidate('src/A.java','bad','local'); good=Candidate('src/A.java','good','local')
    observed=[]
    def generate(size, history):
        observed.append(history)
        return [bad] if size==1 else [bad,good]
    result=recover(generate,operator_policy([]),lambda c:verdict(c,'passed' if c==good else 'compile'),generation_sizes=(1,2),budget=3)
    assert result['solved'] and result['validated']==2 and not result['promoted']
    assert observed[1][0][0]==bad
    assert result['generations'][1]['proposal']['cause']=='candidate_pool_exhausted'
    assert result['generations'][1]['proposal']['parent_generation_digest']==result['generations'][0]['proposal']['generation_digest']


def test_empty_generations_terminate_and_regressions_are_not_success():
    c=Candidate('src/A.java','regression','local')
    result=recover(lambda size,h: [] if size==1 else [c],operator_policy([]),lambda c:verdict(c,'full_suite'),generation_sizes=(1,2,3),budget=4)
    assert not result['solved'] and result['validated']==1
    assert result['generations'][0]['stop_reason']=='empty_candidate_pool'
    assert result['stop_reason']=='generation_budget_exhausted'


def test_global_budget_and_mismatched_receipt():
    cs=[Candidate('src/A.java',str(i),'local') for i in range(4)]
    result=recover(lambda n,h:cs,operator_policy([]),lambda c:verdict(c,'compile'),budget=2)
    assert result['validated']==2 and result['stop_reason']=='validation_budget_exhausted'
    with pytest.raises(ValueError,match='identity'):
        recover(lambda n,h:[cs[0]],operator_policy([]),lambda c:verdict(cs[1],'passed'))
    assert diagnose([],[],budget=2)=='empty_candidate_pool'
