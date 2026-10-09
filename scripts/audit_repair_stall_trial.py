#!/usr/bin/env python3
"""Check stored recovery records; not an independent execution replication."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import RepairExperience
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of


def audit(path):
    plan=json.loads((path/'PLAN.json').read_text());checked(plan,'plan_digest')
    result=json.loads((path/'RESULT.json').read_text());checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest']:raise ValueError('plan mismatch')
    for name,identity in plan['machinery'].items():
        source=path/'snapshot'/name
        if not source.exists():source=ROOT/name
        if hashlib.sha256(source.read_bytes()).hexdigest()!=identity:raise ValueError('snapshot mismatch; use archived machinery or its source commit')
    if result['all_solved']!=all(r['solved'] for r in result['outcomes']):raise ValueError('success count mismatch')
    if [r['case'] for r in result['outcomes']]!=plan['cases']:raise ValueError('case order mismatch')
    initial=result['initial_events'];events=result['events']
    if digest_of(initial)!=plan['initial_memory_digest'] or events[:len(initial)]!=initial:raise ValueError('history changed')
    if digest_of(events)!=result['final_memory_digest']:raise ValueError('memory digest mismatch')
    previous=''
    for event in events:
        if event['previous_digest']!=previous:raise ValueError('memory chain mismatch')
        previous=digest_of(event)
    database=path/'experience.sqlite'
    if database.exists() and RepairExperience(database).events()!=events:raise ValueError('database mismatch')
    for row in result['outcomes']:
        local=row['local'];seen=set();prior=[];parent=None
        for generation in local['generations']:
            proposal=generation['proposal'];checked(proposal,'generation_digest')
            if proposal['parent_generation_digest']!=parent or proposal['prior_verdict_digests']!=prior:raise ValueError('generation lineage mismatch')
            if proposal['promoted']:raise ValueError('unauthorised promotion')
            parent=proposal['generation_digest']
            for attempt in generation['attempts']:
                verdict=attempt['verdict'];checked(verdict,'verdict_digest')
                identity=attempt['candidate_digest']
                if identity in seen or verdict['candidate_digest']!=identity:raise ValueError('duplicate or mismatched attempt')
                seen.add(identity);prior.append(verdict['verdict_digest'])
        if len(seen)!=local['validated'] or len(seen)>plan['local_validation_budget']:raise ValueError('budget mismatch')
        teacher=row['teacher']
        if teacher and teacher['known_cost_usd']>plan['teacher_budget_usd']:raise ValueError('cost budget exceeded')
        if row['solved']:
            replay=row['replay'];checked(replay,'verdict_digest')
            if not replay['plausible'] or replay['stopped_at']!='passed':raise ValueError('missing successful replay')
            if not any(e['kind']=='recipe' and e['data']['candidate_digest']==replay['candidate_digest'] for e in events[len(initial):]):raise ValueError('success not retained')
    return sealed(dict(result_digest=result['result_digest'],cases=len(result['outcomes']),
        stored_evidence_consistent=True,independent_execution_replication=False), 'verification_digest')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('experiment',type=Path)
    print(json.dumps(audit(parser.parse_args().experiment),indent=2))
