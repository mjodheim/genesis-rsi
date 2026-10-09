import json
from pathlib import Path
import pytest
from genesis.repair_contract_learning import acquire,generate
from genesis.repair_self_improvement import sealed

ROOT=Path(__file__).resolve().parents[1]


def policy():
    events=json.loads((ROOT/'experiment/bench/DEV_REPAIR_STALL_RECOVERY1/ADMITTED_MEMORY.json').read_text())['events']
    return acquire(events)


def fixture(tmp_path,text):
    (tmp_path/'src').mkdir();(tmp_path/'src/Holder.java').write_text(text)
    return dict(source_directory='src')


def test_real_verified_insertion_becomes_attributed_rule():
    p=policy();assert len(p['rules'])==1 and not p['promoted']
    rule=p['rules'][0]
    assert rule['origin']=='openrouter:anthropic/claude-haiku-5.5'
    assert rule['training_checked_parameters']==['checksum','in']


def test_binding_transfers_without_field_or_class_names_and_requires_contract(tmp_path):
    evidence=fixture(tmp_path,'class Holder { Object stored; public Holder(Object renamed) { this.stored = renamed; } }')
    p=policy();assert generate(tmp_path,evidence,p,{})==[]
    candidates=generate(tmp_path,evidence,p,{'src/Holder.java':{'Holder':['renamed']}})
    assert len(candidates)==1 and 'if (renamed == null)' in candidates[0].content
    assert not candidates[0].provenance['semantic_guard_inferred']
    assert 'checksum' not in candidates[0].content


@pytest.mark.parametrize('constructor,parameter',[
 ('public Holder(int count) { }','count'),
 ('public Holder(Object x) { if (x == null) {} }','x'),
 ('public Holder(Object x) { super(); }','x'),
 ('public Holder(Object x) { this(x,1); }','x'),
 ('public void Holder(Object x) { }','x'),
 ('public Holder(Object x) { }','unknown'),
])
def test_unsupported_or_already_guarded_sites_are_declined(tmp_path,constructor,parameter):
    evidence=fixture(tmp_path,'class Holder { '+constructor+' }')
    assert not generate(tmp_path,evidence,policy(),{'src/Holder.java':{'Holder':[parameter]}})


def test_failed_training_and_test_paths_cannot_teach_or_mutate(tmp_path):
    events=json.loads((ROOT/'experiment/bench/DEV_REPAIR_STALL_RECOVERY1/ADMITTED_MEMORY.json').read_text())['events']
    e=next(e for e in events if e['kind']=='recipe');e['data']['verdict']=sealed(dict(candidate_digest=e['data']['candidate_digest'],plausible=False,stopped_at='full_suite'),'verdict_digest')
    with pytest.raises(ValueError):acquire([e])
    evidence=fixture(tmp_path,'class Holder {}')
    with pytest.raises(ValueError):generate(tmp_path,evidence,policy(),{'../Holder.java':{'Holder':['x']}})
