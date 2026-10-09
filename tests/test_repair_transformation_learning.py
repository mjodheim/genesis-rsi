from pathlib import Path
import pytest

from genesis.repair_transformation_learning import acquire, generate, feedback_order, tokens
from genesis.repair_bench import Candidate
from genesis.repair_self_improvement import sealed
from genesis.trust_root import digest_of


def recipe(before, after, origin='model/training'):
    verdict=sealed(dict(candidate_digest='source-candidate',plausible=True,stopped_at='passed'),'verdict_digest')
    return dict(kind='recipe',data=dict(path='src/Training.java',edits=[(before,after)],
        candidate_digest='source-candidate',verdict=verdict,origin=origin,explanation='verified repair'),
        scope='released_development',previous_digest='')


def setup(root,text):
    (root/'src').mkdir(exist_ok=True);(root/'test').mkdir(exist_ok=True)
    (root/'src/Other.java').write_text(text)
    return dict(source_directory='src',test_directory='test',suspect_locations=[('src/Other.java',1)])


def test_identifier_and_layout_transfer_preserves_repeated_binding(tmp_path):
    policy=acquire([recipe('if (raw.length != expected) {','if (raw.length < expected) {')])
    evidence=setup(tmp_path,'class Other { void f(byte[] bytes, int minimum) {\n if (bytes\n .length != minimum) { throw new IllegalArgumentException(); } } }')
    candidates=generate(tmp_path,evidence,policy)
    assert len(candidates)==1
    assert 'bytes . length < minimum' in candidates[0].content
    assert policy['rules'][0]['origin']=='model/training'
    assert '!=' in (tmp_path/'src/Other.java').read_text()
    repeated=acquire([recipe('return v != null ? v.text().trim() : "";',
                            'return v != null ? TextNode.normaliseWhitespace(v.text()).trim() : "";')])
    (tmp_path/'src/Other.java').write_text('class Other { TextNode n; String normaliseWhitespace; String f() { return a != null ? b.text().trim() : ""; } }')
    assert generate(tmp_path,evidence,repeated)==[]


def test_api_existence_comments_literals_and_production_boundary(tmp_path):
    policy=acquire([recipe('return v.text().trim();','return TextNode.normaliseWhitespace(v.text()).trim();')])
    evidence=setup(tmp_path,'class Other { String f() { return renamed.text().trim(); } }')
    assert generate(tmp_path,evidence,policy)==[]  # introduced API absent
    (tmp_path/'src/TextNode.java').write_text('class TextNode { String normaliseWhitespace(String s) { return s; } }')
    assert len(generate(tmp_path,evidence,policy))==1
    (tmp_path/'src/Other.java').write_text('class Other { String s="return renamed.text().trim();"; /* return renamed.text().trim(); */ }')
    assert generate(tmp_path,evidence,policy)==[]
    (tmp_path/'test/Evil.java').write_text('return renamed.text().trim();')
    with pytest.raises(ValueError): generate(tmp_path,{**evidence,'suspect_locations':[('test/Evil.java',1)]},policy)
    (tmp_path/'src/Link.java').symlink_to(tmp_path/'test/Evil.java')
    with pytest.raises(ValueError): generate(tmp_path,{**evidence,'suspect_locations':[('src/Link.java',1)]},policy)


def test_failed_unsealed_or_nongeneralizable_repairs_do_not_teach():
    event=recipe('if (x.length != n) {','if (x.length < n) {')
    event['data']['verdict']=sealed(dict(plausible=False,stopped_at='compile'),'verdict_digest')
    with pytest.raises(ValueError): acquire([event])
    event=recipe('return 1;','return 0;')
    assert acquire([event])['rules']==[]
    event['data']['verdict']['plausible']=False
    with pytest.raises(ValueError): acquire([event])


def test_feedback_changes_next_hypothesis_and_never_repeats():
    one=Candidate('src/A.java','class A {}','rule/one')
    same=Candidate('src/A.java','class A { int x; }','rule/one')
    other=Candidate('src/B.java','class B {}','rule/two')
    result=feedback_order([one,same,other],[(one,dict(stopped_at='failing_tests',feedback='assertion failed'))])
    assert result==[other,same]
    compile_history=[(one,dict(stopped_at='compile',feedback='symbol: variable MISSING'))]
    invalid=Candidate('src/C.java','class C { int x=MISSING; }','rule/three')
    assert feedback_order([invalid,other],compile_history)==[other,invalid]


def test_unsupported_lexical_input_is_rejected():
    with pytest.raises(ValueError): tokens('class Café {}')
    assert tokens('@Override void f() {}')


def test_descendant_adds_rule_without_erasing_parent():
    parent=acquire([recipe('if (x.length != n) {','if (x.length < n) {')])
    child=acquire([recipe('return x.text().trim();','return Helper.clean(x.text()).trim();')],parent)
    assert child['parent_policy_digest']==parent['policy_digest']
    assert child['rules'][0]==parent['rules'][0] and len(child['rules'])==2
    assert child['promoted'] is False


def test_search_feedback_uses_own_outcomes_and_equal_budget(tmp_path):
    from genesis.repair_transformation_learning import search
    evidence=setup(tmp_path,'class Other {}')
    first=Candidate('src/Other.java','class Other { int a; }','one')
    similar=Candidate('src/Other.java','class Other { int b; }','one')
    distinct=Candidate('src/Other.java','class Other { int c; }','two')
    class Empty:
        def candidates(self,*args):return []
    calls=[]
    def validate(candidate):
        calls.append(candidate.digest)
        passed=candidate==distinct
        return sealed(dict(candidate_digest=candidate.digest,plausible=passed,
            stopped_at='passed' if passed else 'failing_tests',feedback='failed contract'),'verdict_digest')
    parent=search(tmp_path,evidence,None,Empty(),[first,similar,distinct],validate,budget=2,reactive=False)
    calls.clear()
    child=search(tmp_path,evidence,None,Empty(),[first,similar,distinct],validate,budget=2,reactive=True)
    assert not parent['solved'] and child['solved']
    assert parent['validated']==child['validated']==2
    assert calls==[first.digest,distinct.digest]
    assert child['steps'][1]['choice']['prior_verdict_digests']==[child['steps'][0]['verdict']['verdict_digest']]


def test_authored_transfer_gates_execute_java_in_isolation(tmp_path):
    import shutil
    import subprocess
    if not shutil.which('docker'):
        pytest.skip('Docker is required for the executable Java gate')
    available=subprocess.run(['docker','image','inspect','genesis-defects4j:8c16da8'],capture_output=True,timeout=10)
    if available.returncode:
        pytest.skip('Build deploy/defects4j before running the executable Java gate')
    from genesis.defects4j_sandbox import Defects4JSandbox, SandboxLimits
    from scripts.run_repair_transformation_trial import exercise_source,java_verdict
    policy=acquire([
        recipe('if (raw.length != expected) {','if (raw.length < expected) {'),
        recipe('return v != null ? v.text().trim() : "";', 'return v != null ? TextNode.normaliseWhitespace(v.text()).trim() : "";'),
        recipe('CSVRecord r = this.current;\nthis.current = null;', 'CSVRecord r = CSVParser.this.current;\nCSVParser.this.current = null;')])
    sandbox=Defects4JSandbox(tmp_path,limits=SandboxLimits(timeout_seconds=30))
    for family in sorted({r['family'] for r in policy['rules']}):
        for control in (False,True):
            main,text=exercise_source(family,control,2)
            directory=family+str(control);project=tmp_path/directory
            (project/'src').mkdir(parents=True);(project/'classes').mkdir()
            path='src/'+main+'.java';(project/path).write_text(text)
            baseline=java_verdict(sandbox,directory,Candidate(path,text,'baseline'),main)
            assert baseline['stopped_at']!='compile' and baseline['plausible']==control
            evidence=dict(source_directory='src',suspect_locations=[(path,i+1) for i,line in enumerate(text.splitlines()) if '!=' in line or 'this.current' in line])
            candidates=generate(project,evidence,policy)
            assert candidates
            verdicts=[java_verdict(sandbox,directory,c,main) for c in candidates]
            assert all(v['stopped_at']!='compile' for v in verdicts)
            assert any(v['plausible'] for v in verdicts)==(not control)
            assert (project/path).read_text()==text


def test_adaptive_service_retains_success_and_proposes_general_rule(tmp_path):
    from genesis.adaptive_repair import RepairExperience,EconomicRouter,ModelOption,solve_development
    evidence=setup(tmp_path,'class Other { void f(byte[] bytes,int minimum) { if (bytes.length != minimum) {} } }')
    evidence.update(production_source=[dict(path='src/Other.java',numbered_source=(tmp_path/'src/Other.java').read_text())],
        failing_tests=['T::contract'],traces=[],evidence_digest='released')
    policy=acquire([recipe('if (raw.length != expected) {','if (raw.length < expected) {')])
    store=RepairExperience(tmp_path/'memory.sqlite');router=EconomicRouter([ModelOption('unused',.1,.5)],store)
    def validate(c):return sealed(dict(candidate_digest=c.digest,plausible=True,stopped_at='passed'),'verdict_digest')
    result=solve_development(tmp_path,evidence,router,validate,role='released_development',allow_llm=False,
        transformation_policy=policy,local_feedback_rounds=4,learn_transformation_proposals=True)
    assert result['solved_without_llm'] and result['candidate'].origin.startswith('learned-transformation:')
    assert any(e['kind']=='recipe' for e in RepairExperience(store.path).events())
    proposals=[e for e in store.events() if e['kind']=='transformation_proposal']
    assert len(proposals)==1 and proposals[0]['data']['promoted'] is False
    again=solve_development(tmp_path,evidence,router,validate,role='released_development',allow_llm=False)
    assert again['reuse_without_llm'] and again['candidate'].digest==result['candidate'].digest
