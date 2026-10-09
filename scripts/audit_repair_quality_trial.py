#!/usr/bin/env python3
"""Verify saved quality/teacher evidence; no independent execution replication."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_quality_learning import classify,refine
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_transformation_learning import acquire
from genesis.trust_root import digest_of


def audit(output):
    read=lambda n:json.loads((output/n).read_text())
    plan=read('PLAN.json');result=read('RESULT.json');checked(plan,'plan_digest');checked(result,'result_digest')
    if (output/'ABORTED.json').exists() or result['plan_digest']!=plan['plan_digest']:raise ValueError('aborted/mismatched trial')
    for name,checksum in plan['machinery'].items():
        if hashlib.sha256((Path(plan['workspace'])/'machinery-snapshot'/name).read_bytes()).hexdigest()!=checksum:raise ValueError('snapshot changed')
    split=json.loads((ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json').read_text());checked(split,'split_digest')
    expected=[next(c for c in split['development'] if c.startswith(p+'-') and c not in plan['excluded_cases']) for p in ('Jsoup','Math','Compress')]
    if expected!=plan['cases'] or plan['split_digest']!=split['split_digest']:raise ValueError('selection mismatch')
    final=result['final_memory_events'];initial=plan['initial_memory'];previous=''
    if final[:len(initial)]!=initial or digest_of(initial)!=plan['initial_memory_digest']:raise ValueError('initial prefix changed')
    for event in final:
        if event['previous_digest']!=previous or event['scope']!='released_development':raise ValueError('invalid chain')
        previous=digest_of(event)
    if digest_of(final)!=result['final_memory_digest']:raise ValueError('final chain mismatch')
    learning=read('LEARNING.json');checked(learning,'learning_digest')
    transfer=read('TRANSFER_MEMORY.json');checked(transfer,'memory_record_digest')
    if digest_of(transfer['events'])!=transfer['memory_digest'] or learning['training_memory_digest']!=transfer['memory_digest']:raise ValueError('transfer memory mismatch')
    if final[:len(transfer['events'])]!=transfer['events']:raise ValueError('transfer memory prefix changed')
    if acquire(transfer['events'])!=learning['source_policy'] or refine(learning['source_policy'])!=learning['expression_policy']:raise ValueError('learning mismatch')
    counts={}
    for row in plan['operator_training_records']:
        verdict=row['verdict'];checked(verdict,'verdict_digest')
        if row['candidate']['candidate_digest']!=verdict['candidate_digest']:raise ValueError('training identity mismatch')
        ops=row['candidate']['provenance']['component_operators'] or [row['candidate']['origin']]
        for op in ops:counts.setdefault(op,Counter())[classify(verdict)]+=1
    policy=plan['initial_operator_policy'];checked(policy,'policy_digest')
    if policy['outcomes']!={k:dict(v) for k,v in sorted(counts.items())}:raise ValueError('operator counts mismatch')
    training=result['training']
    if [r['case'] for r in training]!=plan['teacher_cases']:raise ValueError('teacher case mismatch')
    for row in training:
        teacher=read(row['case']+'.TEACHER.json');checked(teacher,'teacher_digest')
        if {k:v for k,v in teacher.items() if k!='teacher_digest'}!=row:raise ValueError('teacher record mismatch')
        calls=row['result']['model_calls'];known=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None)
        if known>plan['teacher_api_budget_per_case'] or len(row['result']['verdicts'])>plan['teacher_validation_budget']:raise ValueError('teacher budget exceeded')
        if row['result']['known_cost_usd']!=known:raise ValueError('teacher cost mismatch')
        for verdict in row['result']['verdicts']:checked(verdict,'verdict_digest')
        if row['accepted']:
            identity=row['accepted']['candidate_digest'];checked(row['replay'],'verdict_digest')
            if not row['replay']['plausible'] or row['replay']['candidate_digest']!=identity:raise ValueError('teacher replay mismatch')
            if not any(e['kind']=='recipe' and e['data']['candidate_digest']==identity for e in row['new_events']):raise ValueError('teacher success not durable')
    outcomes=result['outcomes']
    if [r['case'] for r in outcomes]!=plan['cases']:raise ValueError('transfer cases mismatch')
    for row in outcomes:
        case=row['case'];analysis=read(case+'.ANALYSIS.json');checked(analysis,'analysis_digest')
        if analysis['analysis_digest']!=row['analysis_digest'] or len(analysis['analysis_runs'])>plan['max_analyzed_sources']:raise ValueError('analysis mismatch')
        for run in analysis['setup_runs']+analysis['analysis_runs']:checked(run,'run_digest')
        pool=read(case+'.POOL.json');checked(pool,'pool_digest');checked(pool['screen'],'screen_digest')
        for name,arm in row['arms'].items():
            checked(arm,'arm_digest')
            if arm!=read(case+'.'+name+'.ARM.json') or arm['external_model_calls']!=0 or arm['api_cost_usd']!=0:raise ValueError('arm mismatch')
            if arm['candidate_compilations']!=arm['validated'] or arm['validated']!=len(arm['steps']) or arm['validated']>plan['candidate_compile_budget_per_arm']:raise ValueError('compilation budget mismatch')
            candidates={c['candidate_digest']:c for c in pool[name]};seen=set();prior=[];passed=[]
            for index,step in enumerate(arm['steps'],1):
                verdict=step['verdict'];checked(verdict,'verdict_digest');choice=step['choice'];checked(choice,'choice_digest')
                identity=step['candidate']['candidate_digest']
                if identity not in candidates or identity in seen or identity!=verdict['candidate_digest'] or identity!=choice['candidate_digest']:raise ValueError('candidate identity mismatch')
                if choice['index']!=index or choice['prior_verdict_digests']!=prior or step['diagnosis']!=classify(verdict):raise ValueError('feedback linkage mismatch')
                if choice!=read(case+'.'+name+f'.CHOICE{index}.json'):raise ValueError('choice mismatch')
                attempt=read(case+'.'+name+f'.ATTEMPT{index}.json');checked(attempt,'attempt_digest')
                if {k:v for k,v in attempt.items() if k!='attempt_digest'}!=step:raise ValueError('attempt mismatch')
                seen.add(identity);prior.append(verdict['verdict_digest'])
                if verdict['plausible']:
                    if verdict['stopped_at']!='passed':raise ValueError('invalid success')
                    passed.append(identity)
            if arm['solved']!=bool(passed):raise ValueError('arm success mismatch')
        if row['success_recorded']:
            checked(row['replay'],'verdict_digest')
            if not row['replay_verified'] or not row['replay']['plausible']:raise ValueError('transfer replay mismatch')
    gains=[r['case'] for r in outcomes if r['arms']['child']['solved'] and not r['arms']['parent']['solved']]
    regressions=[r['case'] for r in outcomes if r['arms']['parent']['solved'] and not r['arms']['child']['solved']]
    pv=sum(r['arms']['parent']['validated'] for r in outcomes);cv=sum(r['arms']['child']['validated'] for r in outcomes)
    decision=result['decision'];checked(decision,'decision_digest')
    if decision!=read('DECISION.json') or decision['gains']!=gains or decision['regressions']!=regressions or decision['promoted']!=(bool(gains) and not regressions and cv<=pv):raise ValueError('decision mismatch')
    calls=[e['data'] for e in final[len(initial):] if e['kind']=='call'];unknown=sum(c.get('cost_usd') is None for c in calls);cost=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None)
    expected_summary=dict(cases=3,parent_solved=sum(r['arms']['parent']['solved'] for r in outcomes),child_solved=sum(r['arms']['child']['solved'] for r in outcomes),
        parent_compilations=pv,child_compilations=cv,policy_promoted=decision['promoted'],teacher_solved=sum(r['result']['solved'] for r in training),
        teacher_success_replays=sum(bool(r['replay'] and r['replay']['plausible']) for r in training),transfer_successes_recorded=sum(r['success_recorded'] for r in outcomes),
        transfer_replays=sum(r['replay_verified'] for r in outcomes),new_api_requests=sum(c.get('request_sent',True) for c in calls),known_api_cost_usd=cost,
        total_api_cost_usd=None if unknown else cost,new_unknown_costs=unknown,transfer_model_calls=0,acquired_rules=len(learning['source_policy']['rules']),
        refined_rules=len(learning['expression_policy']['rules'])-len(learning['source_policy']['rules']),final_memory_events=len(final),general_rsi_demonstrated=False)
    if result['summary']!=expected_summary:raise ValueError('summary mismatch')
    verification=sealed(dict(plan_digest=plan['plan_digest'],result_digest=result['result_digest'],summary=expected_summary,
        stored_evidence_verified=True,history_preserved=True,independent_execution_replication=False),'verification_digest')
    if (output/'VERIFICATION.json').exists():
        if read('VERIFICATION.json')!=verification:raise ValueError('prior verification changed')
    else:_write_new(output/'VERIFICATION.json',verification)
    return verification


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('experiment',type=Path);print(json.dumps(audit(p.parse_args().experiment.resolve()),indent=2))
