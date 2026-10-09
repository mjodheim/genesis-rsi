from pathlib import Path
import pytest
from genesis.repair_bench import Candidate
from genesis.repair_self_improvement import sealed
from genesis.repair_quality_learning import operators,operator_policy,rank,refine,structural_screen,search,classify
from genesis.repair_transformation_learning import acquire,generate


def event(before,after):
    return dict(kind='recipe',scope='released_development',previous_digest='',data=dict(path='src/A.java',
        edits=[(before,after)],candidate_digest='training',verdict=sealed(dict(candidate_digest='training',plausible=True,stopped_at='passed'),'verdict_digest'),
        origin='teacher',explanation='verified development repair'))


def verdict(c,stage):return sealed(dict(candidate_digest=c.digest,plausible=stage=='passed',stopped_at=stage,feedback='illegal start of expression' if stage=='compile' else ''),'verdict_digest')


def test_smaller_expression_transfers_outside_if_statement(tmp_path):
    parent=acquire([event('if (raw.length != expected) {','if (raw.length < expected) {')])
    child=refine(parent)
    (tmp_path/'src').mkdir();text='class A { boolean f(byte[] payload,int size) { return payload.length != size; } }'
    (tmp_path/'src/A.java').write_text(text)
    evidence=dict(source_directory='src',suspect_locations=[('src/A.java',1)])
    assert generate(tmp_path,evidence,parent)==[]
    assert generate(tmp_path,evidence,child)
    assert len(child['rules'])==2 and child['rules'][1]['origin']=='teacher'


def test_smaller_wrapper_keeps_api_names_and_variable_binding(tmp_path):
    parent=acquire([event('return node != null ? node.text().trim() : "";',
        'return node != null ? TextNode.normaliseWhitespace(node.text()).trim() : "";')])
    child=refine(parent);assert len(child['rules'])==2
    (tmp_path/'src').mkdir();(tmp_path/'src/A.java').write_text('class A { TextNode t; String normaliseWhitespace; String f() { String value = item.text(); return value; } }')
    evidence=dict(source_directory='src',suspect_locations=[('src/A.java',1)])
    assert not generate(tmp_path,evidence,parent) and generate(tmp_path,evidence,child)


def test_operator_history_reorders_candidates_without_hiding_attempt_cost():
    bad=Candidate('src/A.java','bad','strategist',provenance=dict(component_operators=['invalid_modifier']))
    good=Candidate('src/A.java','good','strategist',provenance=dict(component_operators=['expression']))
    policy=operator_policy([(bad,verdict(bad,'compile'))])
    assert rank([bad,good],policy)==[good,bad]
    parent=search([bad,good],policy,lambda c:verdict(c,'passed' if c==good else 'compile'),budget=1,reactive=False)
    child=search([bad,good],policy,lambda c:verdict(c,'passed' if c==good else 'compile'),budget=1)
    assert not parent['solved'] and child['solved']
    assert parent['candidate_compilations']==child['candidate_compilations']==1
    assert child['steps'][0]['choice']['operators']==['expression']


def test_static_modifier_guard_preserves_literals_and_requires_type_evidence(tmp_path):
    (tmp_path/'src').mkdir();text='class A { int f() { return 1; } }';(tmp_path/'src/A.java').write_text(text)
    bad=Candidate('src/A.java',text.replace('return','static return'),'strategist')
    literal=Candidate('src/A.java','class A { String s="static return"; }','strategist')
    unresolved=Candidate('src/A.java',text.replace('1','2'),'learned-transformation:example')
    analysis=sealed(dict(reports={'src/A.java':{'nodes':[]}}),'analysis_digest')
    accepted,report=structural_screen(tmp_path,[bad,literal,unresolved],analysis)
    assert accepted==[literal] and len(report['rejected'])==2
    assert report['compiler_invocations']==0


def test_provenance_does_not_change_repair_identity():
    a=Candidate('src/A.java','class A {}','strategist')
    b=Candidate(a.path,a.content,a.origin,provenance=dict(component_operators=['operator']))
    assert a.digest==b.digest and operators(b)==('operator',)
    assert classify(verdict(a,'full_suite'))=='regression'


def test_compiler_node_guard_runs_inside_docker(tmp_path):
    import shutil,subprocess
    from genesis.defects4j_sandbox import Defects4JSandbox,SandboxLimits
    from genesis.repair_quality_learning import analyze_sources
    if not shutil.which('docker'):pytest.skip('Docker required')
    if subprocess.run(['docker','image','inspect','genesis-defects4j:8c16da8'],capture_output=True,timeout=10).returncode:pytest.skip('Build Defects4J image first')
    root=tmp_path/'fixture';(root/'src').mkdir(parents=True)
    text='class A { boolean f(byte[] data,int size) { return data.length != size; } }'
    (root/'src/A.java').write_text(text)
    evidence=dict(source_directory='src',suspect_locations=[('src/A.java',1)])
    sandbox=Defects4JSandbox(tmp_path,limits=SandboxLimits(timeout_seconds=30))
    analysis=analyze_sources(sandbox,'fixture',evidence)
    assert analysis['analysis_compiler_invocations']==1
    assert any(n['kind']=='NOT_EQUAL_TO' and n['type']=='boolean' for n in analysis['reports']['src/A.java']['nodes'])
    policy=refine(acquire([event('if (raw.length != expected) {','if (raw.length < expected) {')]))
    candidates=generate(root,evidence,policy)
    accepted,screen=structural_screen(root,candidates,analysis)
    assert accepted and screen['compiler_invocations']==0
    assert (root/'src/A.java').read_text()==text
