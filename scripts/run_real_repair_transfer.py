#!/usr/bin/env python3
"""Frozen real-development comparison, followed by separately labelled training."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import EconomicRouter, ModelOption, RepairExperience, solve_development
from genesis.defects4j_sandbox import Defects4JSandbox, SandboxLimits
from genesis.g12_operator_lab import _write_new
from genesis.real_repair_transfer import candidate_pool, order_pool
from genesis.repair_bench import collect_evidence, validate
from genesis.repair_proposers import strategist_proposer
from genesis.repair_self_improvement import checked, sealed
from genesis.trust_root import digest_of


def machinery():
    files=sorted((ROOT/'genesis').rglob('*.py'))+[Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def prepare(output,workspace,catalog):
    split=json.loads((ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json').read_text());checked(split,'split_digest')
    cases=[next(c for c in split['development'] if c.startswith(p+'-') and c not in split['exposed_cases'])
           for p in ['Jsoup','Math','Compress']]
    learned=json.loads((ROOT/'experiment/bench/DEV_REPAIR_SELF_IMPROVEMENT1/RESULT.json').read_text());checked(learned,'result_digest')
    search=json.loads((ROOT/'experiment/bench/DEV_REPAIR_SEARCH_ADAPTATION1/PLAN.json').read_text());checked(search,'plan_digest')
    image=subprocess.check_output(['docker','image','inspect','genesis-defects4j:8c16da8','--format','{{.Id}}'],text=True).strip()
    pointer=json.loads((ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text());checked(pointer,'pointer_digest')
    initial=RepairExperience(Path(pointer['path'])).events()
    if digest_of(initial)!=pointer['memory_digest']:raise ValueError('canonical memory differs')
    models=json.loads(catalog.read_text())
    if {m['id'] for m in models}!={'anthropic/claude-haiku-5.5','openai/gpt-6-luna'}:
        raise ValueError('only approved economical models allowed')
    for m in models:
        if any(float(m['pricing'][p])>0.000001 for p in ['prompt','completion']):
            raise ValueError('model tariff exceeds experiment ceiling')
    output.mkdir(parents=True,exist_ok=True);workspace.mkdir(parents=True,exist_ok=True)
    memory=workspace/'training-memory.sqlite'
    if memory.exists():raise ValueError('new experiment memory required')
    with sqlite3.connect(pointer['path']) as original,sqlite3.connect(memory) as copy:original.backup(copy)
    plan=sealed(dict(schema='genesis-real-repair-transfer-development-v1',cases=cases,
        selection='first nonpreviously-exposed development case per project in frozen split order',
        split_digest=split['split_digest'],image=image,workspace=str(workspace.resolve()),
        initial_memory=initial,initial_memory_digest=digest_of(initial),memory=str(memory),
        capability_policy=learned['final_policy'],parent_search=search['parent_search'],
        child_search=search['proposal']['child'],catalog=models,machinery=machinery(),
        validation_budget=4,pool_budget=32,command_timeout_seconds=180,
        assisted_training_after_comparison=True,api_budget_usd_per_case=.05,
        max_models=2,max_rounds_per_model=2,assisted_validation_budget=8,
        scope='released real-project DEVELOPMENT; public bugs; not independent/blind generality evidence',
        fixed_revision_consulted=False,plausible_is_not_correct=True), 'plan_digest')
    _write_new(output/'PLAN.json',plan)
    dest=workspace/'machinery-snapshot'
    for name in plan['machinery']:
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    print('Prepared',cases,flush=True)


class RecordingSandbox(Defects4JSandbox):
    def execute(self,arguments,*,timeout_seconds=None):
        run=super().execute(arguments,timeout_seconds=timeout_seconds)
        path=self.workspace/'sandbox-runs.jsonl'
        with path.open('a') as handle:
            handle.write(json.dumps(run.record(),sort_keys=True)+'\n');handle.flush();os.fsync(handle.fileno())
        return run


def candidate_record(candidate):
    return dict(path=candidate.path,origin=candidate.origin,description=candidate.description,
                candidate_digest=candidate.digest,content_sha256=hashlib.sha256(candidate.content.encode()).hexdigest())


def evaluate_arm(case,arm,candidates,sandbox,directory,evidence,output,plan):
    order=[candidate_record(c) for c in candidates]
    freeze=sealed(dict(case=case,arm=arm,evidence_digest=evidence['evidence_digest'],
        ordered_candidates=order,validation_budget=plan['validation_budget']), 'search_digest')
    _write_new(output/(case+'.'+arm+'.SEARCH.json'),freeze)
    results=[];accepted=None
    for index,candidate in enumerate(candidates,1):
        verdict=validate(sandbox,directory,candidate,evidence['failing_tests'])
        row=dict(candidate=candidate_record(candidate),verdict=verdict)
        results.append(row)
        _write_new(output/(case+'.'+arm+f'.ATTEMPT{index}.json'),sealed(row,'attempt_digest'))
        if verdict['plausible']:
            accepted=candidate;break
    body=dict(case=case,arm=arm,search_digest=freeze['search_digest'],attempts=results,
        solved=accepted is not None,validated=len(results),external_model_calls=0,api_cost_usd=0,
        accepted_candidate_digest=accepted.digest if accepted else None)
    result=sealed(body,'arm_digest');_write_new(output/(case+'.'+arm+'.ARM.json'),result)
    return result,accepted


def load_api_key():
    if os.environ.get('OPENROUTER_API_KEY'):return
    for line in Path('/opt/mira/.env').read_text().splitlines():
        if line.startswith('OPENROUTER_API_KEY='):
            os.environ['OPENROUTER_API_KEY']=line.split('=',1)[1].strip().strip('\"\'');return
    raise ValueError('OpenRouter credential unavailable')


def execute(output):
    plan=json.loads((output/'PLAN.json').read_text());checked(plan,'plan_digest')
    if plan['machinery']!=machinery():raise ValueError('machinery differs from frozen plan')
    if (output/'STARTED.json').exists():raise ValueError('preserve prior run; no automatic retries')
    store=RepairExperience(Path(plan['memory']))
    if digest_of(store.events())!=plan['initial_memory_digest']:raise ValueError('initial memory differs')
    _write_new(output/'STARTED.json',{'plan_digest':plan['plan_digest']})
    sandbox=RecordingSandbox(Path(plan['workspace']),image=plan['image'],
        limits=SandboxLimits(timeout_seconds=plan['command_timeout_seconds']))
    probe=sandbox.probe();_write_new(output/'SANDBOX_PROBE.json',probe)
    if not probe['isolated']:raise ValueError('sandbox boundary not enforced')
    outcomes=[];runtime={}
    try:
        # The complete autonomous comparison precedes all assisted learning.
        for case in plan['cases']:
            directory=case+'-b';project,bug=case.rsplit('-',1)
            if (sandbox.workspace/directory).exists():raise ValueError('fresh buggy checkout required')
            checkout=sandbox.checkout(project,int(bug),'b',directory)
            if not checkout.ok:raise ValueError('checkout failed: '+case)
            evidence=collect_evidence(sandbox,directory);root=sandbox.workspace/directory
            groups=candidate_pool(root,evidence,plan['capability_policy'],pool_budget=plan['pool_budget'])
            pool=sealed(dict(case=case,evidence_digest=evidence['evidence_digest'],
                groups={key:[candidate_record(c) for c in value] for key,value in groups.items()}), 'pool_digest')
            _write_new(output/(case+'.POOL.json'),pool)
            arms={};accepted={}
            for arm in ['parent','child']:
                candidates=order_pool(groups,plan['capability_policy'],plan[arm+'_search'],budget=plan['validation_budget'])
                arms[arm],accepted[arm]=evaluate_arm(case,arm,candidates,sandbox,directory,evidence,output,plan)
                print(case,arm,'solved',arms[arm]['solved'],'validations',arms[arm]['validated'],flush=True)
            row=dict(case=case,evidence=evidence,pool_digest=pool['pool_digest'],arms=arms,
                     training=None,replay=None,success_recorded=False)
            outcomes.append(row);runtime[case]=(root,directory,evidence,accepted)
            _write_new(output/(case+'.COMPARISON.json'),sealed(row,'comparison_digest'))
        gains=[];regressions=[]
        for row in outcomes:
            before=row['arms']['parent'];after=row['arms']['child']
            if after['solved'] and (not before['solved'] or after['validated']<before['validated']):gains.append(row['case'])
            if before['solved'] and (not after['solved'] or after['validated']>before['validated']):regressions.append(row['case'])
        decision=sealed(dict(gains=gains,regressions=regressions,promoted=bool(gains) and not regressions,
            parent_search_digest=plan['parent_search']['search_policy_digest'],child_search_digest=plan['child_search']['search_policy_digest'],
            rule='strict success/efficiency gain; no success/efficiency regression',
            scope='real development comparison; no independent/general RSI claim'), 'decision_digest')
        _write_new(output/'DECISION.json',decision)
        options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,
                             float(m['pricing']['completion'])*1e6*1.01) for m in plan['catalog']]
        for row in outcomes:
            case=row['case'];root,directory,evidence,accepted=runtime[case]
            before=len(store.events());candidate=accepted['child'] or accepted['parent']
            if candidate:
                arm='child' if accepted['child'] else 'parent'
                verdict=next(r['verdict'] for r in row['arms'][arm]['attempts'] if r['verdict']['plausible'])
                store.retain(root,evidence,candidate,verdict,role='released_development')
                training=dict(solved=True,accepted_origin=candidate.origin,assisted=False,
                    known_cost_usd=0,total_cost_usd=0,model_calls=[],verdicts=[verdict])
            else:
                load_api_key();router=EconomicRouter(options,store);fallback=EconomicRouter(options,store,0)
                training=solve_development(root,evidence,router,
                    lambda c:validate(sandbox,directory,c,evidence['failing_tests']),role='released_development',
                    budget_usd=plan['api_budget_usd_per_case'],validation_budget=plan['assisted_validation_budget'],
                    local_proposer=strategist_proposer(4),local_validation_budget=4,
                    max_models=plan['max_models'],max_rounds_per_model=plan['max_rounds_per_model'],fallback_router=fallback)
                candidate=training.pop('candidate')
                training['assisted']=bool(training['model_calls'])
                training['accepted_origin']=candidate.origin if candidate else None
                if candidate and not any(e['kind']=='recipe' and e['data']['candidate_digest']==candidate.digest
                                         for e in store.events()[before:]):
                    verdict=next(v for v in training['verdicts'] if v['plausible'] and v['candidate_digest']==candidate.digest)
                    store.retain(root,evidence,candidate,verdict,role='released_development')
            row['training']=training
            if candidate:
                row['success_recorded']=any(e['kind']=='recipe' and e['data']['candidate_digest']==candidate.digest
                                           for e in RepairExperience(store.path).events()[before:])
                row['accepted_candidate_digest']=candidate.digest
                row['patch']=''.join(difflib.unified_diff((root/candidate.path).read_text().splitlines(keepends=True),
                    candidate.content.splitlines(keepends=True),fromfile='a/'+candidate.path,tofile='b/'+candidate.path))
                fresh=RepairExperience(store.path);router=EconomicRouter(options,fresh)
                replay=solve_development(root,evidence,router,
                    lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                    role='released_development',allow_llm=False,validation_budget=2)
                repeated=replay.pop('candidate');row['replay']=replay
                row['replay_verified']=bool(repeated and repeated.digest==candidate.digest and replay['reuse_without_llm'] and not replay['model_calls'])
                if not row['success_recorded'] or not row['replay_verified']:
                    _write_new(output/(case+'.TRAINING.json'),sealed(row,'training_digest'))
                    raise ValueError('durable success or replay verification failed: '+case)
            row['new_memory_events']=RepairExperience(store.path).events()[before:]
            _write_new(output/(case+'.TRAINING.json'),sealed(row,'training_digest'))
            print(case,'training solved',training['solved'],'replay',row.get('replay_verified',False),
                  'known API cost',training['known_cost_usd'],flush=True)
        events=RepairExperience(store.path).events();calls=[e['data'] for e in events[len(plan['initial_memory']):] if e['kind']=='call']
        known=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None);unknown=sum(c.get('cost_usd') is None for c in calls)
        summary=dict(cases=len(outcomes),parent_solved=sum(r['arms']['parent']['solved'] for r in outcomes),
            child_solved=sum(r['arms']['child']['solved'] for r in outcomes),search_policy_promoted=decision['promoted'],
            training_solved=sum(r['training']['solved'] for r in outcomes),
            successes_recorded=sum(r['success_recorded'] for r in outcomes),
            verified_memory_replays=sum(r.get('replay_verified',False) for r in outcomes),
            new_api_requests=sum(c.get('request_sent',True) for c in calls),known_api_cost_usd=known,
            total_api_cost_usd=None if unknown else known,new_unknown_costs=unknown,general_rsi_demonstrated=False)
        _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],outcomes=outcomes,decision=decision,
            summary=summary,final_memory_events=events,final_memory_digest=digest_of(events),sandbox_probe=probe,
            scope=plan['scope'],fixed_revision_consulted=False,plausible_is_not_correct=True), 'result_digest'))
        print(json.dumps(summary,indent=2),flush=True)
    except Exception as error:
        events=RepairExperience(store.path).events()
        _write_new(output/'ABORTED.json',sealed(dict(plan_digest=plan['plan_digest'],error_type=type(error).__name__,
            error=str(error)[:500],outcomes=outcomes,final_memory_events=events,final_memory_digest=digest_of(events)), 'abort_digest'))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workspace',type=Path)
    parser.add_argument('--catalog',type=Path);args=parser.parse_args()
    if args.action=='prepare':
        if not args.workspace or not args.catalog:parser.error('--workspace and --catalog required')
        prepare(args.output,args.workspace,args.catalog)
    else:execute(args.output)


if __name__=='__main__':main()
