#!/usr/bin/env python3
"""Admit audited development history; keep policy promotion a separate decision."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.audit_repair_transformation_trial import audit
from genesis.adaptive_repair import RepairExperience
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of


def append_suffix(path,initial,final):
    """Commit the exact verified suffix, or refuse divergent/concurrent history."""
    if final[:len(initial)]!=initial:raise ValueError('trial rewrote its initial history')
    with sqlite3.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        current=[];previous=''
        for payload,checksum in db.execute('SELECT payload,digest FROM events ORDER BY sequence'):
            event=json.loads(payload)
            if event['previous_digest']!=previous or digest_of(event)!=checksum:raise ValueError('canonical chain corrupt')
            current.append(event);previous=checksum
        if current==final:return  # recover an interrupted pointer update
        if current!=initial:raise ValueError('canonical memory changed; preserve divergent trial')
        for event in final[len(initial):]:
            if event['previous_digest']!=previous or event['scope']!='released_development':raise ValueError('invalid trial suffix')
            checksum=digest_of(event)
            db.execute('INSERT INTO events(payload,digest) VALUES (?,?)',(json.dumps(event,sort_keys=True),checksum))
            previous=checksum


def atomic_write(path,value):
    with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.transformation-memory-',delete=False) as handle:
        json.dump(value,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno());temporary=handle.name
    os.replace(temporary,path)


def promote(experiment):
    verification=audit(experiment)
    plan=json.loads((experiment/'PLAN.json').read_text());result=json.loads((experiment/'RESULT.json').read_text())
    checked(plan,'plan_digest');checked(result,'result_digest')
    if (verification['plan_digest'],verification['result_digest'])!=(plan['plan_digest'],result['result_digest']):raise ValueError('records changed after audit')
    if (experiment/'PROMOTION.json').exists():raise ValueError('completed admission must not be repeated')
    if RepairExperience(Path(plan['memory'])).events()!=result['final_memory_events']:raise ValueError('trial database differs from evidence')
    pointer_path=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json'
    pointer=json.loads(pointer_path.read_text());checked(pointer,'pointer_digest')
    archive=experiment/'PREVIOUS_ACTIVE_MEMORY.json'
    if not archive.exists():_write_new(archive,pointer)
    old=json.loads(archive.read_text());checked(old,'pointer_digest')
    if old['memory_digest']!=plan['initial_memory_digest'] or pointer['path']!=old['path']:
        raise ValueError('trial is not canonical memory descendant')
    policy_pointer=None;policy_target=None
    if result['decision']['promoted']:
        policy_pointer=sealed(dict(schema='genesis-active-development-transformation-policy-v1',
            policy=plan['child_policy'],source_trial=experiment.name,
            source_result_digest=result['result_digest'],verification_digest=verification['verification_digest'],
            decision_digest=result['decision']['decision_digest'],scope='released development only; combined lexical/feedback change'), 'pointer_digest')
        policy_target=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_TRANSFORMATION_POLICY.json'
        if policy_target.exists() and json.loads(policy_target.read_text())!=policy_pointer:
            raise ValueError('existing active policy needs separate successor review')
    backup=Path(pointer['path']).with_name('experience-before-'+experiment.name.lower()+'.sqlite')
    with sqlite3.connect(pointer['path']) as source:
        if not backup.exists():
            with sqlite3.connect(backup) as target:source.backup(target)
    append_suffix(Path(pointer['path']),plan['initial_memory'],result['final_memory_events'])
    body={k:v for k,v in old.items() if k!='pointer_digest'}
    body.update(source_trial=experiment.name,events=len(result['final_memory_events']),memory_digest=result['final_memory_digest'],
        verification_result=str((experiment/'VERIFICATION.json').relative_to(ROOT/'experiment/bench')),
        known_limitation='Historical unknown charges preserved; lexical abstraction is authored; development policy gate is separate from memory admission; no general RSI claim')
    updated=sealed(body,'pointer_digest');atomic_write(pointer_path,updated)
    if policy_target is not None:atomic_write(policy_target,policy_pointer)
    receipt=sealed(dict(source_trial=experiment.name,source_result_digest=result['result_digest'],
        verification_digest=verification['verification_digest'],previous_pointer_digest=old['pointer_digest'],
        pointer_digest=updated['pointer_digest'],previous_events=len(plan['initial_memory']),current_events=len(result['final_memory_events']),
        new_events=len(result['final_memory_events'])-len(plan['initial_memory']),history_preserved=True,
        policy_promoted=result['decision']['promoted'],active_policy_pointer_digest=policy_pointer['pointer_digest'] if policy_pointer else None,
        scope='all verified development successes and failures; not independent RSI evidence'),'promotion_digest')
    _write_new(experiment/'PROMOTION.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',type=Path)
    print(json.dumps(promote(parser.parse_args().experiment.resolve()),indent=2))
