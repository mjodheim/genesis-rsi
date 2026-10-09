import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

from genesis.adaptive_repair import RepairExperience
from genesis.repair_self_improvement import sealed
from genesis.trust_root import digest_of


def fixture(tmp_path,monkeypatch):
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'scripts'))
    spec=importlib.util.spec_from_file_location('promote_real_test',root/'scripts/run_promote_real_repair_experience.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'ROOT',tmp_path)
    canonical=RepairExperience(tmp_path/'canonical.sqlite')
    canonical.append('attempt',dict(model='historical',cost_usd=None,passed=False))
    initial=canonical.events()
    trial=RepairExperience(tmp_path/'trial.sqlite')
    with canonical.connect() as source,trial.connect() as destination:source.backup(destination)
    trial.append('attempt',dict(model='new',cost_usd=.001,passed=True));final=trial.events()
    pointer=sealed(dict(path=str(canonical.path),memory_digest=digest_of(initial),events=1,
        schema='genesis-active-development-repair-memory-v1'), 'pointer_digest')
    folder=tmp_path/'experiment/bench';folder.mkdir(parents=True)
    (folder/'ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').write_text(json.dumps(pointer))
    experiment=folder/'TRIAL';experiment.mkdir()
    plan=sealed(dict(initial_memory_digest=digest_of(initial),initial_memory=initial),'plan_digest')
    result=sealed(dict(final_memory_events=final,final_memory_digest=digest_of(final),
                       summary={'successes_recorded':1}), 'result_digest')
    (experiment/'PLAN.json').write_text(json.dumps(plan));(experiment/'RESULT.json').write_text(json.dumps(result))
    verification=dict(plan_digest=plan['plan_digest'],result_digest=result['result_digest'],verification_digest='checked')
    monkeypatch.setattr(module,'audit',lambda _:verification)
    return module,canonical,experiment,initial,final


def test_promotion_preserves_unknown_cost_and_appends_exact_history(tmp_path,monkeypatch):
    module,canonical,experiment,initial,final=fixture(tmp_path,monkeypatch)
    result=module.promote(experiment)
    assert canonical.events()==final
    assert canonical.events()[0]['data']['cost_usd'] is None
    assert result['historical_prefix_preserved'] and result['new_events']==1
    pointer=json.loads((tmp_path/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text())
    assert pointer['events']==2 and pointer['memory_digest']==digest_of(final)
    with pytest.raises(ValueError,match='repeated'):module.promote(experiment)


def test_concurrent_memory_change_is_never_overwritten(tmp_path,monkeypatch):
    module,canonical,experiment,_,_=fixture(tmp_path,monkeypatch)
    canonical.append('attempt',dict(model='concurrent',cost_usd=.002,passed=False))
    before=canonical.events()
    with pytest.raises(ValueError,match='concurrently'):module.promote(experiment)
    assert canonical.events()==before


def test_pointer_write_interruption_can_be_recovered(tmp_path,monkeypatch):
    module,canonical,experiment,initial,final=fixture(tmp_path,monkeypatch)
    canonical.append(final[-1]['kind'],final[-1]['data'])
    assert canonical.events()==final
    result=module.promote(experiment)
    assert result['current_events']==2 and canonical.events()==final
