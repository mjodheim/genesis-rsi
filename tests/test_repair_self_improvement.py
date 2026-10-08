from copy import deepcopy
import importlib.util
from pathlib import Path

import pytest

from genesis.repair_self_improvement import (decide_promotion, propose, propose_descendant,
                                            sealed, seed_policy, validate_policy)
from genesis.trust_root import digest_of


def learned(tmp_path, delta=-1):
    root = tmp_path/'training'; root.mkdir()
    (root/'subject.py').write_text(f'def pick(a, i): return a[i]\ndef neighbor(a, i): return a[i {delta:+d}]\n')
    parent=seed_policy(); candidate=propose(root,parent,discover=True)[0]
    receipt=sealed(dict(candidate_digest=candidate['candidate_digest'],role='released_training',
        passed=True,host_graded=True,timed_out=False,returncode=0), 'receipt_digest')
    child=propose_descendant(parent,candidate,receipt,role='released_training')
    return parent,child,candidate,receipt


def row(task,parent,child,before=False,after=True):
    def outcome(policy,passed):
        return sealed(dict(task_id=task,role='promotion',policy_digest=policy['policy_digest'],
            candidate_budget=4,passed=passed,attempt_count=1,external_model_calls=0), 'evaluation_digest')
    return dict(task_id=task,parent=outcome(parent,before),child=outcome(child,after))


def test_acquired_rule_transfers_across_identifier_and_language_without_exemplar(tmp_path):
    parent,child,_,_=learned(tmp_path)
    target=tmp_path/'new';target.mkdir()
    (target/'different.js').write_text('function take(values, position) { return values[position]; }\n')
    assert propose(target,parent,discover=False)==[]
    candidates=propose(target,child,discover=False)
    assert len(candidates)==1
    assert 'values[position - 1]' in candidates[0]['mutations'][0]['content_utf8']
    assert candidates[0]['provenance']['external_model_calls']==0


def test_failed_or_evaluation_receipt_cannot_train(tmp_path):
    parent,_,candidate,receipt=learned(tmp_path)
    for change in [dict(passed=False),dict(host_graded=False),dict(role='final_evaluation'),
                   dict(candidate_digest='another'),dict(timed_out=True),dict(returncode=1)]:
        body={k:v for k,v in receipt.items() if k!='receipt_digest'};body.update(change)
        with pytest.raises(ValueError):
            propose_descendant(parent,candidate,sealed(body,'receipt_digest'),role='released_training')


def test_parent_and_strategy_tampering_rejected(tmp_path):
    _,child,_,_=learned(tmp_path)
    tampered=deepcopy(child);tampered['strategies'][0]['delta']=5
    with pytest.raises(ValueError):validate_policy(tampered)
    rule=tampered['strategies'][0]
    rule['strategy_digest']=digest_of({k:v for k,v in rule.items() if k!='strategy_digest'})
    tampered['policy_digest']=digest_of({k:v for k,v in tampered.items() if k!='policy_digest'})
    with pytest.raises(ValueError,match='template'):validate_policy(tampered)


def test_gain_promotes_and_regression_rejects(tmp_path):
    parent,child,_,_=learned(tmp_path)
    decision=decide_promotion(parent,child,[row('new',parent,child)],training_ids={'training'},candidate_budget=4)
    assert decision['promoted']
    assert not decision['new_semantic_primitive_invented']
    decision=decide_promotion(parent,child,[row('new',parent,child),row('old',parent,child,True,False)],
        training_ids={'training'},candidate_budget=4)
    assert not decision['promoted']
    assert decision['regressions']==['old']


def test_equal_scores_overlap_and_budget_mismatch(tmp_path):
    parent,child,_,_=learned(tmp_path)
    decision=decide_promotion(parent,child,[row('same',parent,child,True,True)],training_ids=set(),candidate_budget=4)
    assert not decision['promoted']
    with pytest.raises(ValueError,match='overlap'):
        decide_promotion(parent,child,[row('training',parent,child)],training_ids={'training'},candidate_budget=4)
    with pytest.raises(ValueError,match='incomparable'):
        decide_promotion(parent,child,[row('same',parent,child)],training_ids=set(),candidate_budget=2)


def test_recursive_child_preserves_parent_rules(tmp_path):
    _,parent,_,_=learned(tmp_path)
    root=tmp_path/'second';root.mkdir()
    (root/'subject.py').write_text('def pick(a, n): return a[n]\ndef neighbor(a, n): return a[n + 2]\n')
    candidates=propose(root,parent,discover=True)
    candidate=next(c for c in candidates if c['provenance']['generator']=='repository_exemplar_mutations')
    receipt=sealed(dict(candidate_digest=candidate['candidate_digest'],role='released_training',passed=True,
                        host_graded=True,timed_out=False,returncode=0),'receipt_digest')
    child=propose_descendant(parent,candidate,receipt,role='released_training')
    assert child['generation']==2
    assert child['strategies'][:-1]==parent['strategies']


def test_host_grader_rejects_candidate_success_flag():
    path=Path(__file__).resolve().parents[1]/'scripts/run_repair_self_improvement.py'
    spec=importlib.util.spec_from_file_location('repair_loop_script',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    task={'expected':[1,2,3]}
    base=dict(returncode=0,timed_out=False,stdout='{"passed": true}')
    assert not module.grade(base,task)['passed']
    assert not module.grade({**base,'stdout':'[true,2,3]'},task)['passed']
    assert module.grade({**base,'stdout':'[1,2,3]'},task)['passed']
