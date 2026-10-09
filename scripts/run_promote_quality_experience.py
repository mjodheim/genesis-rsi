#!/usr/bin/env python3
"""Admit audited quality history independently of policy promotion."""
from __future__ import annotations
import argparse,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_repair_quality_trial import audit
from scripts.run_promote_transformation_experience import append_suffix,atomic_write
from genesis.adaptive_repair import RepairExperience
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed


def promote(experiment):
    verification=audit(experiment)
    plan=json.loads((experiment/'PLAN.json').read_text());result=json.loads((experiment/'RESULT.json').read_text())
    if (experiment/'PROMOTION.json').exists():raise ValueError('completed admission must not be repeated')
    if verification['result_digest']!=result['result_digest']:raise ValueError('records changed after audit')
    if RepairExperience(Path(plan['memory'])).events()!=result['final_memory_events']:raise ValueError('trial database mismatch')
    target=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json'
    pointer=json.loads(target.read_text());checked(pointer,'pointer_digest')
    archive=experiment/'PREVIOUS_ACTIVE_MEMORY.json'
    if not archive.exists():_write_new(archive,pointer)
    old=json.loads(archive.read_text());checked(old,'pointer_digest')
    if old['memory_digest']!=plan['initial_memory_digest'] or old['path']!=pointer['path']:raise ValueError('canonical ancestor mismatch')
    policy_pointer=None;policy_target=None
    if result['decision']['promoted']:
        learning=json.loads((experiment/'LEARNING.json').read_text());checked(learning,'learning_digest')
        policy_pointer=sealed(dict(schema='genesis-active-repair-quality-policy-v1',expression_policy=learning['expression_policy'],
            operator_policy=learning['operator_policy'],source_trial=experiment.name,verification_digest=verification['verification_digest'],
            scope='released development only; combined change'), 'pointer_digest')
        policy_target=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_QUALITY_POLICY.json'
        if policy_target.exists() and json.loads(policy_target.read_text())!=policy_pointer:raise ValueError('active successor requires separate review')
    backup=Path(pointer['path']).with_name('experience-before-'+experiment.name.lower()+'.sqlite')
    if not backup.exists():
        with sqlite3.connect(pointer['path']) as source,sqlite3.connect(backup) as copy:source.backup(copy)
    append_suffix(Path(pointer['path']),plan['initial_memory'],result['final_memory_events'])
    body={k:v for k,v in old.items() if k!='pointer_digest'}
    body.update(source_trial=experiment.name,events=len(result['final_memory_events']),memory_digest=result['final_memory_digest'],
        verification_result=str((experiment/'VERIFICATION.json').relative_to(ROOT/'experiment/bench')),
        known_limitation='Historical unknown charges preserved; assisted acquisition attributed; quality policy gate separate; no general RSI claim')
    updated=sealed(body,'pointer_digest');atomic_write(target,updated)
    if policy_target:atomic_write(policy_target,policy_pointer)
    receipt=sealed(dict(source_trial=experiment.name,source_result_digest=result['result_digest'],verification_digest=verification['verification_digest'],
        previous_pointer_digest=old['pointer_digest'],pointer_digest=updated['pointer_digest'],previous_events=len(plan['initial_memory']),
        current_events=len(result['final_memory_events']),history_preserved=True,policy_promoted=result['decision']['promoted']), 'promotion_digest')
    _write_new(experiment/'PROMOTION.json',receipt);return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);print(json.dumps(promote(p.parse_args().experiment.resolve()),indent=2))
