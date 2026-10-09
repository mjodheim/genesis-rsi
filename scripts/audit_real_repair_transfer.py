#!/usr/bin/env python3
"""Check recorded real-development outcomes, cost accounting and memory lineage.

This is an evidence-integrity audit, not independent test execution replication.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of


def audit(directory):
    plan=json.loads((directory/'PLAN.json').read_text());checked(plan,'plan_digest')
    result=json.loads((directory/'RESULT.json').read_text());checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest']:raise ValueError('result/plan mismatch')
    for name,checksum in plan['machinery'].items():
        source=Path(plan['workspace'])/'machinery-snapshot'/name
        if hashlib.sha256(source.read_bytes()).hexdigest()!=checksum:raise ValueError('frozen source differs: '+name)
    probe=result['sandbox_probe'];checked(probe,'probe_digest')
    if probe.get('isolated') is not True:raise ValueError('sandbox not isolated')
    events=result['final_memory_events'];previous=''
    for event in events:
        if event['previous_digest']!=previous:raise ValueError('memory chain differs')
        previous=digest_of(event)
    if events[:len(plan['initial_memory'])]!=plan['initial_memory']:
        raise ValueError('historical memory overwritten')
    if digest_of(events)!=result['final_memory_digest']:raise ValueError('final memory digest differs')
    if [row['case'] for row in result['outcomes']]!=plan['cases']:raise ValueError('case set/order changed')
    validations=0;replays=0;gains=[];regressions=[]
    for row in result['outcomes']:
        checked(row['evidence'],'evidence_digest')
        for name in ['parent','child']:
            arm=row['arms'][name];checked(arm,'arm_digest')
            if arm['validated']!=len(arm['attempts']) or arm['validated']>plan['validation_budget']:
                raise ValueError('validation budget differs')
            for attempt in arm['attempts']:
                verdict=attempt['verdict'];checked(verdict,'verdict_digest')
                if verdict['candidate_digest']!=attempt['candidate']['candidate_digest']:
                    raise ValueError('candidate/verdict mismatch')
            solved=any(a['verdict']['plausible'] and a['verdict']['stopped_at']=='passed' for a in arm['attempts'])
            if solved!=arm['solved'] or arm['external_model_calls']!=0:raise ValueError('autonomous arm differs')
            validations+=arm['validated']
        before=row['arms']['parent'];after=row['arms']['child']
        if after['solved'] and (not before['solved'] or after['validated']<before['validated']):gains.append(row['case'])
        if before['solved'] and (not after['solved'] or after['validated']>before['validated']):regressions.append(row['case'])
        training=row['training']
        for verdict in training['verdicts']:checked(verdict,'verdict_digest')
        if training['solved']:
            candidate=row['accepted_candidate_digest']
            passing=[v for v in training['verdicts'] if v['plausible'] and v['stopped_at']=='passed' and v['candidate_digest']==candidate]
            recipes=[e['data'] for e in row['new_memory_events'] if e['kind']=='recipe' and e['data']['candidate_digest']==candidate]
            replay=row['replay']
            if not passing or not recipes or not row['success_recorded'] or not row['replay_verified']:
                raise ValueError('success not durably recorded and replayed')
            if replay['model_calls'] or not replay['reuse_without_llm']:
                raise ValueError('replay called a model')
            if not any(v['plausible'] and v['stopped_at']=='passed' and v['candidate_digest']==candidate for v in replay['verdicts']):
                raise ValueError('replay candidate differs')
            for v in replay['verdicts']:checked(v,'verdict_digest')
            replays+=1
    decision=result['decision'];checked(decision,'decision_digest')
    if decision['gains']!=gains or decision['regressions']!=regressions or decision['promoted']!=(bool(gains) and not regressions):
        raise ValueError('promotion decision differs')
    calls=[e['data'] for e in events[len(plan['initial_memory']):] if e['kind']=='call']
    known=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None)
    unknown=sum(c.get('cost_usd') is None for c in calls)
    summary=result['summary']
    expected_summary=dict(cases=len(result['outcomes']),
        parent_solved=sum(r['arms']['parent']['solved'] for r in result['outcomes']),
        child_solved=sum(r['arms']['child']['solved'] for r in result['outcomes']),
        training_solved=sum(r['training']['solved'] for r in result['outcomes']),
        successes_recorded=sum(r['success_recorded'] for r in result['outcomes']),
        search_policy_promoted=decision['promoted'],
        new_api_requests=sum(c.get('request_sent',True) for c in calls))
    if any(summary.get(key)!=value for key,value in expected_summary.items()):
        raise ValueError('outcome summary differs')
    if (not math.isclose(known,summary['known_api_cost_usd'],abs_tol=1e-12)
        or unknown!=summary['new_unknown_costs'] or summary['total_api_cost_usd']!=(None if unknown else known)
        or replays!=summary['verified_memory_replays']):raise ValueError('cost/replay summary differs')
    body=dict(plan_digest=plan['plan_digest'],result_digest=result['result_digest'],cases=len(plan['cases']),
        autonomous_validations=validations,verified_success_replays=replays,known_api_cost_usd=known,
        new_unknown_costs=unknown,memory_events=len(events),historical_prefix_unchanged=True,
        frozen_source_hashes_verified=True,decision_recomputed=True,
        scope='recorded-evidence integrity audit; not independent replication')
    verification=sealed(body,'verification_digest');_write_new(directory/'VERIFICATION.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    print(json.dumps(audit(parser.parse_args().directory),indent=2))
