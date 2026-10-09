#!/usr/bin/env python3
"""Append verified real-development experience without rewriting old history."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from audit_real_repair_transfer import audit
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of


def promote(experiment):
    verification=audit(experiment)
    plan=json.loads((experiment/'PLAN.json').read_text())
    result=json.loads((experiment/'RESULT.json').read_text())
    checked(plan,'plan_digest');checked(result,'result_digest')
    if (verification['plan_digest']!=plan['plan_digest']
        or verification['result_digest']!=result['result_digest']):
        raise ValueError('evidence changed after verification')
    if not result['summary']['successes_recorded']:
        raise ValueError('no validated success to admit')
    pointer_path=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json'
    pointer=json.loads(pointer_path.read_text());checked(pointer,'pointer_digest')
    archive=ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY_PREREAL_TRANSFER_20261009.json'
    if (experiment/'PROMOTION.json').exists():
        raise ValueError('completed promotion must not be repeated')
    if not archive.exists():_write_new(archive,pointer)
    old=json.loads(archive.read_text());checked(old,'pointer_digest')
    if pointer['path']!=old['path']:raise ValueError('canonical memory path changed')
    if old['memory_digest']!=plan['initial_memory_digest']:
        raise ValueError('plan did not start from archived canonical memory')
    initial=plan['initial_memory'];final=result['final_memory_events']
    backup=Path(pointer['path']).with_name('experience-prereal-transfer-20261009.sqlite')
    with sqlite3.connect(pointer['path']) as db:
        if not backup.exists():
            with sqlite3.connect(backup) as destination:db.backup(destination)
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute('SELECT payload,digest FROM events ORDER BY sequence').fetchall()
        current=[];previous=''
        for payload,checksum in rows:
            event=json.loads(payload)
            if event['previous_digest']!=previous or digest_of(event)!=checksum:
                raise ValueError('canonical memory integrity failure')
            current.append(event);previous=checksum
        if current==final:
            pass  # recover a pointer-write interruption after a completed DB transaction
        elif current==initial:
            for event in final[len(initial):]:
                if event['previous_digest']!=previous:raise ValueError('trial suffix does not extend canonical memory')
                checksum=digest_of(event)
                db.execute('INSERT INTO events(payload,digest) VALUES (?,?)',(json.dumps(event,sort_keys=True),checksum))
                previous=checksum
        else:raise ValueError('canonical memory changed concurrently; preserve both branches')
    body={k:v for k,v in old.items() if k!='pointer_digest'}
    body.update(source_trial=experiment.name,memory_digest=result['final_memory_digest'],events=len(final),
        verification_result=str((experiment/'VERIFICATION.json').relative_to(ROOT/'experiment/bench')),
        known_limitation='Historical rejected-request charges remain unknown; real search-order adaptation rejected; verified same-case reuse is not general transfer')
    updated=sealed(body,'pointer_digest')
    with tempfile.NamedTemporaryFile('w',dir=pointer_path.parent,prefix='.active-memory-',delete=False) as handle:
        json.dump(updated,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno());stage=handle.name
    os.replace(stage,pointer_path)
    record=sealed(dict(source_result_digest=result['result_digest'],verification_digest=verification['verification_digest'],
        previous_pointer_digest=old['pointer_digest'],pointer_digest=updated['pointer_digest'],
        previous_events=len(initial),current_events=len(final),new_events=len(final)-len(initial),
        previous_memory_digest=plan['initial_memory_digest'],current_memory_digest=result['final_memory_digest'],
        historical_prefix_preserved=True,source_trial=experiment.name,
        scope='released development experience only; search-policy promotion remains rejected'), 'promotion_digest')
    _write_new(experiment/'PROMOTION.json',record)
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',type=Path)
    print(json.dumps(promote(parser.parse_args().experiment.resolve()),indent=2))
