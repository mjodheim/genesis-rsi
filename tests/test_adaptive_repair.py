from pathlib import Path
import sqlite3
import pytest
from genesis.adaptive_repair import EconomicRouter, ModelOption, RepairExperience, solve_development, task_features
from genesis.repair_bench import Candidate
from genesis.trust_root import digest_of


def fixture(root, name='A.java'):
    (root/'src').mkdir(exist_ok=True); (root/'test').mkdir(exist_ok=True)
    text='class '+name[:-5]+' {\n'+ ''.join('  // padding %d\n'%i for i in range(12))
    text+='  int value() {\n    return 1;\n  }\n'+''.join('  // footer %d\n'%i for i in range(12))+'}\n'
    (root/'src'/name).write_text(text)
    evidence=dict(source_directory='src', test_directory='test', evidence_digest='development',
        production_source=[dict(path='src/'+name,numbered_source=text)],failing_tests=['T::value'],traces=[dict(trace='java.lang.AssertionError: value')])
    return evidence,Candidate('src/'+name,text.replace('return 1;','return 0;'),'model/demo','return the required value')


def verdict(candidate, passed=True):
    body=dict(candidate_digest=candidate.digest,plausible=passed,stopped_at='passed' if passed else 'full_suite')
    return {**body,'verdict_digest':digest_of(body)}


def test_transfer_to_another_file_is_revalidated_without_llm(tmp_path):
    evidence,candidate=fixture(tmp_path)
    store=RepairExperience(tmp_path/'memory.sqlite')
    store.retain(tmp_path,evidence,candidate,verdict(candidate),role='released_development')
    other,_=fixture(tmp_path,'B.java')
    router=EconomicRouter([ModelOption('cheap',.1,.5)],store)
    validated=[]
    def validate(c):
        validated.append(c)
        assert c.path=='src/B.java' and 'class B {' in c.content and 'return 0;' in c.content
        return verdict(c)
    def no_llm(*args,**kwargs): raise AssertionError('should reuse retained pattern')
    result=solve_development(tmp_path,other,router,validate,role='released_development',proposer_factory=no_llm)
    assert result['solved'] and result['reuse_without_llm'] and result['known_cost_usd']==0
    assert len(validated)==1 and result['model_calls']==[]
    assert 'return 1;' in (tmp_path/'src/B.java').read_text()


def test_failed_or_mismatched_verdict_cannot_teach_recipe(tmp_path):
    evidence,candidate=fixture(tmp_path); store=RepairExperience(tmp_path/'memory.sqlite')
    with pytest.raises(ValueError): store.retain(tmp_path,evidence,candidate,verdict(candidate,False),role='released_development')
    v=verdict(candidate);v['candidate_digest']='forged'
    with pytest.raises(ValueError): store.retain(tmp_path,evidence,candidate,v,role='released_development')
    with pytest.raises(ValueError): store.retain(tmp_path,evidence,candidate,verdict(candidate),role='held_out')
    assert store.events()==[]


def test_complexity_specific_outcomes_change_model_selection(tmp_path):
    evidence,_=fixture(tmp_path); store=RepairExperience(tmp_path/'memory.sqlite')
    options=[ModelOption('cheap',.1,.5),ModelOption('capable',.2,1)]
    router=EconomicRouter(options,store)
    assert router.rank(evidence,.2)[0]['option'].model=='cheap'
    complex_evidence={**evidence,'production_source':[dict(path=f'src/{i}.java',numbered_source='x'*6000) for i in range(4)]}
    for _ in range(10):
        store.record_attempt(task_features(complex_evidence),'cheap',.01,False,role='released_development')
        store.record_attempt(task_features(complex_evidence),'capable',.02,True,role='released_development')
    assert router.rank(complex_evidence,.2)[0]['option'].model=='capable'
    assert router.rank(evidence,.2)[0]['option'].model=='cheap'
    assert router.rank(evidence,.00000001)==[]


def test_unknown_cost_stops_escalation_and_is_durable(tmp_path):
    evidence,_=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    router=EconomicRouter([ModelOption('a',.1,.5),ModelOption('b',.2,1)],store)
    calls=[]
    def factory(model,count,ledger,**kwargs):
        calls.append(model)
        def proposer(*args):
            ledger.append(dict(model=model,request_sent=True,cost_usd=None,call_failed=True))
            return []
        return proposer
    result=solve_development(tmp_path,evidence,router,lambda c: verdict(c),role='released_development',proposer_factory=factory)
    assert result['unknown_cost'] and len(calls)==1
    assert RepairExperience(store.path).events()[0]['kind']=='call'
    assert router.rank(evidence,.2)[0]['option'].model=='b'


def test_corrupt_memory_fails_closed(tmp_path):
    store=RepairExperience(tmp_path/'memory.sqlite');store.append('attempt',dict(model='a'))
    with store.connect() as db:db.execute("UPDATE events SET payload='{}'")
    with pytest.raises(ValueError,match='integrity'):store.events()


def test_failed_memory_candidate_requires_fallback_validation(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    store.retain(tmp_path,evidence,candidate,verdict(candidate),role='released_development')
    router=EconomicRouter([ModelOption('cheap',.1,.5)],store);seen=[]
    def validate(c):seen.append(c);return verdict(c,False)
    result=solve_development(tmp_path,evidence,router,validate,role='released_development',budget_usd=.00000001)
    assert not result['solved'] and not result['reuse_without_llm'] and len(seen)==1


def test_quality_threshold_prevents_buying_many_cheap_failed_attempts(tmp_path):
    evidence,_=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    for passed in (False,False,True):
        store.record_attempt({'complexity':'any'},'cheap',.001,passed,role='released_development')
    for _ in range(3):store.record_attempt({'complexity':'any'},'reliable',.004,True,role='released_development')
    options=[ModelOption('cheap',.1,.5),ModelOption('reliable',.1,.5)]
    assert EconomicRouter(options,store).rank(evidence,.05)[0]['option'].model=='reliable'
    assert EconomicRouter(options,store,minimum_observed_success_rate=0).rank(evidence,.05)[0]['option'].model=='cheap'


def test_archived_patch_context_must_match_exactly():
    from run_adaptive_repair import apply_archived_patch
    patch='--- a/A.java\n+++ b/A.java\n@@ -1,2 +1,2 @@\n alpha\n-old\n+new\n'
    assert apply_archived_patch('alpha\nold\n',patch)=='alpha\nnew\n'
    with pytest.raises(ValueError,match='context'):apply_archived_patch('alpha\ndifferent\n',patch)


def test_online_success_teaches_next_invocation_without_model(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    router=EconomicRouter([ModelOption('cheap',.1,.5)],store);requested=[]
    def factory(model,count,ledger,**kwargs):
        requested.append(model)
        def proposer(*args):
            ledger.append(dict(model=model,request_sent=True,cost_usd=.001))
            return [candidate]
        return proposer
    first=solve_development(tmp_path,evidence,router,verdict,role='released_development',proposer_factory=factory)
    assert first['solved'] and first['total_cost_usd']==.001 and not first['reuse_without_llm']
    second=solve_development(tmp_path,evidence,router,verdict,role='released_development',proposer_factory=factory)
    assert second['solved'] and second['reuse_without_llm'] and second['total_cost_usd']==0
    assert requested==['cheap']
    assert any(e['kind']=='recipe' and e['data']['explanation']==candidate.description for e in store.events())


def test_local_success_is_learned_before_any_model_call(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    router=EconomicRouter([ModelOption('cheap',.1,.5)],store)
    local=Candidate(candidate.path,candidate.content,'strategist','local operator')
    def no_model(*args,**kwargs):raise AssertionError('local success must skip LLM')
    result=solve_development(tmp_path,evidence,router,verdict,role='released_development',
        local_proposer=lambda *args:[local],proposer_factory=no_model)
    assert result['solved_without_llm'] and not result['reuse_without_llm']
    assert any(e['kind']=='recipe' and e['data']['origin']=='strategist' for e in store.events())
    replay=solve_development(tmp_path,evidence,router,verdict,role='released_development',allow_llm=False)
    assert replay['reuse_without_llm'] and replay['candidate'].digest==local.digest


def test_model_feedback_round_uses_remaining_budget_and_learns_success(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    router=EconomicRouter([ModelOption('cheap',.1,.5)],store);limits=[]
    better=Candidate(candidate.path,candidate.content.replace('return 0;','return 2;'),'model/demo')
    def factory(model,count,ledger,**kwargs):
        limits.append(kwargs['max_round_usd'])
        def proposer(root,evidence,history,remaining):
            ledger.append(dict(model=model,cost_usd=.001,request_sent=True))
            return [candidate if not history else better]
        return proposer
    result=solve_development(tmp_path,evidence,router,
        lambda c:verdict(c,'return 2;' in c.content),role='released_development',
        budget_usd=.01,max_rounds_per_model=2,proposer_factory=factory)
    assert result['solved'] and result['total_cost_usd']==.002
    assert limits==pytest.approx([.01,.009])
    assert sum(e['kind']=='recipe' for e in store.events())==1


def test_proven_transport_review_reenables_model_without_erasing_unknown_bill(tmp_path):
    evidence,_=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    store.record_attempt({'complexity':'any'},'anthropic/claude-haiku-5.5',.001,True,role='released_development')
    store.append('call',dict(model='anthropic/claude-haiku-5.5',http_status=404,step=4,cost_usd=None))
    store.record_attempt(task_features(evidence),'anthropic/claude-haiku-5.5',None,False,role='released_development')
    original=store.events();attempt_digest=digest_of(original[-1])
    router=EconomicRouter([ModelOption('anthropic/claude-haiku-5.5',.1,.5)],store)
    assert router.rank(evidence,.05)==[]
    body=dict(endpoints=[dict(supports_tool_choice={'function':False})],checks=[
        dict(tool_choice={'type':'function'},status=404,message='unsupported tool_choice'),
        dict(tool_choice='auto',status=200)])
    diagnostic={**body,'diagnostic_digest':digest_of(body)}
    store.review_transport_failure(attempt_digest,diagnostic,role='released_development')
    assert router.rank(evidence,.05)[0]['option'].model=='anthropic/claude-haiku-5.5'
    assert store.events()[:len(original)]==original and store.events()[-2]['data']['cost_usd'] is None
    assert store.events()[-1]['data']['billing_resolved'] is False
    store.review_transport_failure(attempt_digest,diagnostic,role='released_development')
    assert len(store.events())==len(original)+1
    with pytest.raises(ValueError):store.review_transport_failure('a'*64,diagnostic,role='released_development')
    bad={**body,'checks':[dict(tool_choice='auto',status=200)]}
    with pytest.raises(ValueError):store.review_transport_failure(attempt_digest,{**bad,'diagnostic_digest':digest_of(bad)},role='released_development')


def test_memory_replays_dependency_not_present_in_trace_including_legacy_recipe(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    (tmp_path/'src/Facade.java').write_text('class Facade {}\n')
    trace_evidence={**evidence,'production_source':[{'path':'src/Facade.java','numbered_source':'class Facade {}'}]}
    v=verdict(candidate);v['path']=candidate.path
    v['verdict_digest']=digest_of({k:value for k,value in v.items() if k!='verdict_digest'})
    store.retain(tmp_path,trace_evidence,candidate,v,role='released_development')
    recipe=store.events()[-1]['data'];assert recipe['path']=='src/A.java'
    assert store.candidates(tmp_path,trace_evidence)[0].digest==candidate.digest
    legacy=RepairExperience(tmp_path/'legacy.sqlite')
    legacy.append('recipe',{k:value for k,value in recipe.items() if k!='path'})
    replay=solve_development(tmp_path,trace_evidence,EconomicRouter([ModelOption('cheap',.1,.5)],legacy),
        verdict,role='released_development',allow_llm=False)
    assert replay['reuse_without_llm'] and replay['candidate'].digest==candidate.digest


def test_another_projects_remembered_path_cannot_escape_current_source_roots(tmp_path):
    evidence,candidate=fixture(tmp_path);store=RepairExperience(tmp_path/'memory.sqlite')
    store.retain(tmp_path,evidence,candidate,verdict(candidate),role='released_development')
    recipe=store.events()[-1]['data']
    store.append('recipe',{**recipe,'path':'../../outside.java'})
    # Invalid legacy/cross-project paths are skipped, not read or used to abort safe matching.
    assert store.candidates(tmp_path,evidence)[0].digest==candidate.digest
