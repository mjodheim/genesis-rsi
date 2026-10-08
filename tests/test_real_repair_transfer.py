from pathlib import Path

import pytest

from genesis.real_repair_transfer import candidate_pool, order_pool
from genesis.repair_bench import Candidate
from genesis.repair_search_adaptation import seed_search
from genesis.repair_self_improvement import sealed, seed_policy


def policies():
    capability=seed_policy();parent=seed_search(capability)
    child=sealed(dict(schema=parent['schema'],generation=1,ordering='observed_first',
        capability_policy_digest=capability['policy_digest'],parent_search_digest=parent['search_policy_digest'],
        evidence_digest='released-training-diagnosis'), 'search_policy_digest')
    return capability,parent,child


def test_ordering_compares_same_pool_and_deduplicates_repairs():
    capability,parent,child=policies()
    retained=Candidate('src/A.java','a','retained');observed=Candidate('src/A.java','b','observed')
    groups={'retained':[retained],'observed':[observed],'strategist':[observed,Candidate('src/A.java','c','strategist')]}
    before=order_pool(groups,capability,parent,budget=3)
    after=order_pool(groups,capability,child,budget=3)
    assert [c.content for c in before]==['a','b','c']
    assert [c.content for c in after]==['b','a','c']
    assert {c.digest for c in before}=={c.digest for c in after}


def test_exemplars_use_only_causal_production_source(tmp_path,monkeypatch):
    (tmp_path/'src').mkdir();(tmp_path/'tests').mkdir()
    original='function pick(v, i) { return v[i]; }\nfunction neighbor(v, i) { return v[i + 2]; }\n'
    (tmp_path/'src/A.js').write_text(original)
    (tmp_path/'tests/Secret.js').write_text('const example=v[i + 77];')
    (tmp_path/'src/Unrelated.js').write_text('const example=v[i + 99];')
    monkeypatch.setattr('genesis.real_repair_transfer.strategist_proposer',lambda _:lambda *args:[])
    evidence=dict(source_directory='src',suspect_locations=[['src/A.js',1]])
    groups=candidate_pool(tmp_path,evidence,seed_policy())
    assert groups['observed']
    assert all('delta=2' in c.description for c in groups['observed'])
    assert all(c.path=='src/A.js' for c in groups['observed'])
    assert (tmp_path/'src/A.js').read_text()==original


def test_tests_and_symlinks_cannot_enter_source_view(tmp_path,monkeypatch):
    (tmp_path/'src').mkdir();(tmp_path/'tests').mkdir()
    (tmp_path/'tests/T.java').write_text('class T {}')
    (tmp_path/'src/Link.java').symlink_to(tmp_path/'tests/T.java')
    for path in ['tests/T.java','src/Link.java','../outside.java']:
        with pytest.raises(ValueError):
            candidate_pool(tmp_path,dict(source_directory='src',suspect_locations=[[path,1]]),seed_policy())


def test_changes_far_from_failure_do_not_consume_validation_budget(tmp_path,monkeypatch):
    (tmp_path/'src').mkdir()
    (tmp_path/'src/A.js').write_text('// near failure\n'+'\n'*100+
        'function pick(v, i) { return v[i]; }\nfunction neighbor(v, i) { return v[i + 2]; }\n')
    monkeypatch.setattr('genesis.real_repair_transfer.strategist_proposer',lambda _:lambda *args:[])
    groups=candidate_pool(tmp_path,dict(source_directory='src',suspect_locations=[['src/A.js',1]]),seed_policy())
    assert groups['observed']==[]
