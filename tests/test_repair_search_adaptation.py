from copy import deepcopy

import pytest

from genesis.repair_search_adaptation import derive_search_descendant, search_promotion, seed_search
from genesis.repair_self_improvement import sealed, seed_policy


def evidence():
    capabilities=seed_policy();parent=seed_search(capabilities);rounds=[];searches={}
    for index in range(2):
        candidates=[{'candidate_digest':'old','provenance':{'generator':'retained_acquired_strategy'}},
                    {'candidate_digest':'new','provenance':{'generator':'repository_exemplar_mutations'}}]
        search=sealed(dict(task_digest=f'task-{index}',policy_digest='training-policy',
                           discover=True,candidates=candidates),'search_digest')
        searches[search['search_digest']]=search
        attempts=[sealed(dict(candidate_digest=key,passed=passed,role='released_training',host_graded=True),
                         'receipt_digest') for key,passed in [('old',False),('new',True)]]
        training=sealed(dict(task_id=f'train-{index}',task_digest=f'task-{index}',role='released_training',
            policy_digest='training-policy',search_digest=search['search_digest'],attempts=attempts), 'evaluation_digest')
        rounds.append({'training':training})
    result=sealed(dict(final_policy=capabilities,rounds=rounds),'result_digest')
    return parent,result,searches


def comparison(parent,child,before=4,after=1,role='promotion'):
    def outcome(policy,count):
        return sealed(dict(task_id='next-task',role=role,search_policy_digest=policy['search_policy_digest'],
            candidate_budget=4,passed=True,attempt_count=count,external_model_calls=0),'evaluation_digest')
    return dict(task_id='next-task',parent=outcome(parent,before),child=outcome(child,after))


def test_repeated_training_waste_proposes_search_policy_change():
    parent,result,searches=evidence();proposal=derive_search_descendant(parent,result,searches)
    assert proposal['child']['ordering']=='observed_first'
    assert proposal['child']['parent_search_digest']==parent['search_policy_digest']
    assert len(proposal['diagnosis']['examples'])==2


def test_evaluation_outcome_and_insufficient_evidence_cannot_adapt():
    parent,result,searches=evidence()
    body={k:v for k,v in result.items() if k!='result_digest'}
    short=deepcopy(body);short['rounds']=short['rounds'][:1]
    with pytest.raises(ValueError,match='insufficient'):
        derive_search_descendant(parent,sealed(short,'result_digest'),searches)
    changed=deepcopy(body);training=changed['rounds'][0]['training']
    training['role']='final_evaluation'
    changed['rounds'][0]['training']=sealed({k:v for k,v in training.items() if k!='evaluation_digest'},'evaluation_digest')
    with pytest.raises(ValueError,match='evaluation'):
        derive_search_descendant(parent,sealed(changed,'result_digest'),searches)


def test_efficiency_improvement_is_gated_and_slowdown_rejected():
    parent,result,searches=evidence();child=derive_search_descendant(parent,result,searches)['child']
    decision=search_promotion(parent,child,[comparison(parent,child)],budget=4)
    assert decision['promoted']
    decision=search_promotion(parent,child,[comparison(parent,child,1,2)],budget=4)
    assert not decision['promoted'];assert decision['regressions']==['next-task']
    decision=search_promotion(parent,child,[comparison(parent,child,1,1)],budget=4)
    assert not decision['promoted']


def test_final_evaluation_cannot_promote():
    parent,result,searches=evidence();child=derive_search_descendant(parent,result,searches)['child']
    with pytest.raises(ValueError,match='incomparable'):
        search_promotion(parent,child,[comparison(parent,child,role='final_evaluation')],budget=4)
