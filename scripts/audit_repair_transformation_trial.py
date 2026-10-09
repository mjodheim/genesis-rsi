#!/usr/bin/env python3
"""Audit stored development evidence; does not independently rerun Java tests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_transformation_learning import acquire,validate_policy
from genesis.trust_root import digest_of


def audit(output):
    read=lambda name:json.loads((output/name).read_text())
    plan=read('PLAN.json');result=read('RESULT.json')
    checked(plan,'plan_digest');checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest']:raise ValueError('plan linkage mismatch')
    if (output/'ABORTED.json').exists():raise ValueError('aborted trial cannot pass')
    snapshot=Path(plan['workspace'])/'machinery-snapshot'
    for name,checksum in plan['machinery'].items():
        if hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=checksum:raise ValueError('snapshot mismatch')
    split=json.loads((ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json').read_text());checked(split,'split_digest')
    if split['split_digest']!=plan['split_digest']:raise ValueError('split changed')
    expected=[next(c for c in split['development'] if c.startswith(p+'-') and c not in plan['excluded_cases']) for p in ('Jsoup','Math','Compress')]
    if plan['cases']!=expected or len(set(expected))!=3:raise ValueError('case selection mismatch')
    initial=plan['initial_memory'];final=result['final_memory_events']
    if digest_of(initial)!=plan['initial_memory_digest'] or final[:len(initial)]!=initial:
        raise ValueError('historical prefix changed')
    previous=''
    for event in final:
        if event['previous_digest']!=previous or event['scope']!='released_development':raise ValueError('invalid memory chain')
        previous=digest_of(event)
    if digest_of(final)!=result['final_memory_digest']:raise ValueError('final memory mismatch')
    regenerated=[];parent=None
    for index,event in enumerate(initial):
        if event['kind']!='recipe':continue
        child=acquire(initial[:index+1],parent)
        if parent is None and not child['rules']:continue
        if parent is not None and len(parent['rules'])==len(child['rules']):continue
        regenerated.append(child);parent=child
    if regenerated!=plan['generations'] or parent!=plan['child_policy']:raise ValueError('acquisition mismatch')
    validate_policy(parent)
    gates=result['gates']
    for index,gate in enumerate(gates,1):
        checked(gate,'gate_digest')
        if gate!=read(f'GENERATION{index}.GATE.json') or gate['policy_digest']!=regenerated[index-1]['policy_digest']:
            raise ValueError('generation gate mismatch')
        for test in gate['tests']:
            checked(test['baseline'],'verdict_digest')
            if test['baseline']['stopped_at']=='compile' or test['baseline']['plausible']!=test['control']:
                raise ValueError('invalid baseline control')
            passed=False
            for attempt in test['attempts']:
                verdict=attempt['verdict'];checked(verdict,'verdict_digest')
                if verdict['candidate_digest']!=attempt['candidate']['candidate_digest']:raise ValueError('candidate verdict mismatch')
                for run in (verdict['compile_run'],verdict['test_run']):
                    if run is not None:checked(run,'run_digest')
                if verdict['plausible']:
                    if verdict['stopped_at']!='passed' or not verdict['test_run'] or verdict['test_run']['returncode']!=0:raise ValueError('invalid passing run')
                    passed=True
            active=any(r['family']==test['family'] for r in regenerated[index-1]['rules'])
            expected_success=active and not test['control']
            if test['solved']!=passed or passed!=expected_success or not test['source_restored']:
                raise ValueError('gate test mismatch')
        if gate['negative_controls_accepted']!=0:raise ValueError('negative control accepted')
        if gate['positives_solved']!=sum(t['solved'] for t in gate['tests'] if not t['control']):raise ValueError('gate summary mismatch')
    probe=read('SANDBOX_PROBE.json');checked(probe,'probe_digest')
    if not probe['isolated']:raise ValueError('sandbox failed')
    outcomes=result['outcomes']
    if [row['case'] for row in outcomes]!=plan['cases']:raise ValueError('cases mismatch')
    for row in outcomes:
        case=row['case'];pool=read(case+'.POOL.json');checked(pool,'pool_digest')
        candidates={c['candidate_digest']:c for key in ('exact','learned','local') for c in pool[key]}
        for name,arm in row['arms'].items():
            checked(arm,'arm_digest')
            if arm!=read(case+'.'+name+'.ARM.json') or arm['external_model_calls']!=0 or arm['api_cost_usd']!=0:
                raise ValueError('arm mismatch')
            if arm['validated']!=len(arm['steps']) or arm['validated']>plan['validation_budget']:raise ValueError('budget mismatch')
            prior=[];seen=set();passed=[]
            for index,step in enumerate(arm['steps'],1):
                verdict=step['verdict'];checked(verdict,'verdict_digest');choice=step['choice'];checked(choice,'choice_digest')
                identity=step['candidate']['candidate_digest']
                if identity not in candidates or identity in seen or identity!=verdict['candidate_digest'] or identity!=choice['candidate_digest']:
                    raise ValueError('invalid trial candidate')
                if choice['prior_verdict_digests']!=prior or choice['index']!=index:raise ValueError('feedback lineage mismatch')
                if choice!=read(case+'.'+name+f'.CHOICE{index}.json'):raise ValueError('choice publication mismatch')
                attempt=read(case+'.'+name+f'.ATTEMPT{index}.json');checked(attempt,'attempt_digest')
                if {k:v for k,v in attempt.items() if k!='attempt_digest'}!=step:raise ValueError('attempt mismatch')
                prior.append(verdict['verdict_digest']);seen.add(identity)
                if verdict['plausible']:
                    if verdict['stopped_at']!='passed':raise ValueError('invalid plausible verdict')
                    passed.append(identity)
            if arm['solved']!=bool(passed) or row['accepted_candidate_digest'][name]!=(passed[-1] if passed else None):raise ValueError('success mismatch')
        if row['success_recorded']:
            identity=row['accepted_candidate_digest']['child'] or row['accepted_candidate_digest']['parent']
            if not any(e['kind']=='recipe' and e['data']['candidate_digest']==identity for e in final[len(initial):]):raise ValueError('success not durable')
            checked(row['replay'],'verdict_digest')
            if not row['replay_verified'] or not row['replay']['plausible'] or row['replay']['candidate_digest']!=identity:
                raise ValueError('replay mismatch')
    gains=[r['case'] for r in outcomes if r['arms']['child']['solved'] and not r['arms']['parent']['solved']]
    regressions=[r['case'] for r in outcomes if r['arms']['parent']['solved'] and not r['arms']['child']['solved']]
    pv=sum(r['arms']['parent']['validated'] for r in outcomes);cv=sum(r['arms']['child']['validated'] for r in outcomes)
    decision=result['decision'];checked(decision,'decision_digest')
    if decision!=read('DECISION.json') or decision['gains']!=gains or decision['regressions']!=regressions or decision['promoted']!=(bool(gains) and not regressions and cv<=pv):
        raise ValueError('promotion mismatch')
    expected_summary=dict(cases=3,parent_solved=sum(r['arms']['parent']['solved'] for r in outcomes),
        child_solved=sum(r['arms']['child']['solved'] for r in outcomes),parent_validations=pv,child_validations=cv,
        successes_recorded=sum(r['success_recorded'] for r in outcomes),verified_replays=sum(r['replay_verified'] for r in outcomes),
        acquired_rules=len(parent['rules']),acquisition_generations=len(regenerated),policy_promoted=decision['promoted'],
        external_model_calls=0,api_cost_usd=0,general_rsi_demonstrated=False,final_memory_events=len(final))
    if result['summary']!=expected_summary:raise ValueError('summary mismatch')
    if any(e['kind']=='call' for e in final[len(initial):]):raise ValueError('unexpected external model call')
    verification=sealed(dict(plan_digest=plan['plan_digest'],result_digest=result['result_digest'],
        summary=expected_summary,history_preserved=True,machinery_snapshot_verified=True,
        stored_evidence_verified=True,independent_execution_replication=False),'verification_digest')
    if (output/'VERIFICATION.json').exists():
        if read('VERIFICATION.json')!=verification:raise ValueError('prior audit changed')
    else:_write_new(output/'VERIFICATION.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('experiment',type=Path)
    print(json.dumps(audit(parser.parse_args().experiment.resolve()),indent=2))
