#!/usr/bin/env python3
"""Admit audited development outcomes without promoting a failed search policy."""
import argparse,json,sqlite3,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import RepairExperience
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of
from scripts.audit_repair_stall_trial import audit
from scripts.run_promote_transformation_experience import append_suffix,atomic_write


def promote(experiment, runtime):
    if (experiment/'PROMOTION.json').exists():raise ValueError('already admitted')
    verification=audit(runtime)
    result=json.loads((runtime/'RESULT.json').read_text());checked(result,'result_digest')
    if json.loads((experiment/'RESULT.json').read_text())!=result:raise ValueError('published result mismatch')
    target=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json'
    pointer=json.loads(target.read_text());checked(pointer,'pointer_digest')
    initial=result['initial_events']
    if digest_of(initial)!=pointer['memory_digest']:raise ValueError('canonical ancestor mismatch')
    memory=runtime/'admitted-experience.sqlite'
    if not memory.exists():
        with sqlite3.connect(runtime/'experience.sqlite') as source,sqlite3.connect(memory) as dest:source.backup(dest)
        store=RepairExperience(memory)
        for row in result['outcomes']:
            for generation in row['local']['generations']:
                store.append('search_generation',dict(case=row['case'],**generation['proposal']))
                for attempt in generation['attempts']:
                    store.append('local_validation',dict(case=row['case'],**attempt))
        store.append('stall_recovery_trial',dict(result_digest=result['result_digest'],all_solved=result['all_solved'],policy_promoted=False))
    events=RepairExperience(memory).events()
    _write_new(experiment/'PREVIOUS_ACTIVE_MEMORY.json',pointer)
    backup=Path(pointer['path']).with_name('experience-before-'+experiment.name.lower()+'.sqlite')
    if not backup.exists():
        with sqlite3.connect(pointer['path']) as source,sqlite3.connect(backup) as dest:source.backup(dest)
    _write_new(experiment/'VERIFICATION.json',verification)
    _write_new(experiment/'ADMITTED_MEMORY.json',sealed(dict(events=events,memory_digest=digest_of(events)), 'record_digest'))
    append_suffix(Path(pointer['path']),initial,events)
    body={k:v for k,v in pointer.items() if k!='pointer_digest'}
    body.update(source_trial=experiment.name,events=len(events),memory_digest=digest_of(events),
        verification_result=experiment.name+'/VERIFICATION.json',known_limitation='Assisted exposed-case repairs; exact replay; failed local searches preserved; no general RSI')
    updated=sealed(body,'pointer_digest');atomic_write(target,updated)
    _write_new(experiment/'PROMOTION.json',sealed(dict(previous_events=len(initial),current_events=len(events),
        previous_pointer_digest=pointer['pointer_digest'],pointer_digest=updated['pointer_digest'],
        policy_promoted=False,source_result_digest=result['result_digest']), 'promotion_digest'))
    print('Admitted',len(initial),'->',len(events),'policy unpromoted')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('experiment',type=Path);p.add_argument('runtime',type=Path)
    args=p.parse_args();promote(args.experiment.resolve(),args.runtime.resolve())
