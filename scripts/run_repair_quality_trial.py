#!/usr/bin/env python3
"""Frozen teacher development, quality learning and three fresh development trials."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import EconomicRouter,ModelOption,RepairExperience,solve_development
from genesis.defects4j_sandbox import SandboxLimits
from genesis.g12_operator_lab import _write_new
from genesis.repair_bench import collect_evidence,validate
from genesis.repair_proposers import strategist_proposer
from genesis.repair_quality_learning import analyze_sources,classify,operator_policy,rank,refine,search,structural_screen
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_transformation_learning import acquire,generate
from genesis.trust_root import digest_of
from scripts.run_real_repair_transfer import RecordingSandbox,load_api_key
from scripts.run_repair_transformation_trial import exposures,selection_gate


def descriptor(c):return dict(path=c.path,candidate_digest=c.digest,content_sha256=hashlib.sha256(c.content.encode()).hexdigest(),origin=c.origin,description=c.description,provenance=c.provenance)


def machinery():
    files=sorted((ROOT/'genesis').rglob('*.py'))+[ROOT/'genesis/java_analysis/GenesisJavaAnalyzer.java',Path(__file__).resolve(),ROOT/'scripts/audit_repair_quality_trial.py',ROOT/'scripts/run_real_repair_transfer.py',ROOT/'scripts/run_repair_transformation_trial.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def prior_outcomes():
    directory=ROOT/'experiment/bench/DEV_REPAIR_TRANSFORMATION_TRANSFER1'
    result=json.loads((directory/'RESULT.json').read_text());checked(result,'result_digest')
    plan=json.loads((directory/'PLAN.json').read_text());observations=[];records=[]
    for row in result['outcomes']:
        evidence=json.loads((directory/(row['case']+'.EVIDENCE.json')).read_text())
        root=Path(plan['workspace'])/(row['case']+'-b')
        pool=strategist_proposer(32,preserve_provenance=True)(root,evidence,(),32)
        by_digest={c.digest:c for c in pool}
        for arm in row['arms'].values():
            for step in arm['steps']:
                candidate=by_digest[step['candidate']['candidate_digest']]
                observations.append((candidate,step['verdict']))
                records.append(dict(case=row['case'],candidate=descriptor(candidate),verdict=step['verdict']))
    return operator_policy(observations),records


def prepare(output,workspace,catalog):
    if output.exists() or workspace.exists():raise ValueError('fresh trial directories required')
    split=json.loads((ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json').read_text());checked(split,'split_digest')
    exposed,census=exposures(split)
    cases=[next(c for c in split['development'] if c.startswith(project+'-') and c not in exposed) for project in ('Jsoup','Math','Compress')]
    pointer=json.loads((ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text());checked(pointer,'pointer_digest')
    initial=RepairExperience(Path(pointer['path'])).events()
    if digest_of(initial)!=pointer['memory_digest']:raise ValueError('canonical memory differs')
    models=json.loads(catalog.read_text())
    if {m['id'] for m in models}!={'anthropic/claude-haiku-5.5','openai/gpt-6-luna'}:raise ValueError('approved economical models required')
    for model in models:
        if any(float(model['pricing'][key])>0.000001 for key in ('prompt','completion')):raise ValueError('tariff ceiling exceeded')
    learned,observations=prior_outcomes()
    image=subprocess.check_output(['docker','image','inspect','genesis-defects4j:8c16da8','--format','{{.Id}}'],text=True).strip()
    output.mkdir(parents=True);workspace.mkdir(parents=True);memory=workspace/'experience.sqlite'
    with sqlite3.connect(pointer['path']) as source,sqlite3.connect(memory) as target:source.backup(target)
    plan=sealed(dict(schema='genesis-repair-quality-trial-development-v1',cases=cases,
        selection='first remaining development case per Jsoup/Math/Compress in frozen split order',
        excluded_cases=sorted(exposed),exposure_census=census,split_digest=split['split_digest'],
        teacher_cases=['Jsoup-59','Math-41','Compress-44'],teacher_before_transfer=True,
        teacher_api_budget_per_case=.05,teacher_validation_budget=8,max_models=2,max_rounds_per_model=2,catalog=models,
        teacher_policy='economical router; all failed calls/charges retained; unknown charge stops retries',
        no_llm_during_transfer=True,validation_budget=8,local_pool_budget=64,
        analysis_shared_by_arms=True,max_analyzed_sources=8,analysis_counts_recorded=True,
        candidate_compile_budget_per_arm=8,baseline_and_shared_analysis_separate=True,
        parent='same learned exact memory; existing fixed strategist order',
        child='same exact memory; compiler-node-guarded expression refinements; structural screen and outcome/operator ranking',
        gate='strict solved-case gain; no solved-case regression; nonincreasing candidate compilations',
        initial_memory=initial,initial_memory_digest=digest_of(initial),source_pointer_digest=pointer['pointer_digest'],
        initial_operator_policy=learned,operator_training_records=observations,
        expression_algorithm='acquire verified recipes then mechanically refine smaller expressions; no expected fixes',
        command_timeout_seconds=180,image=image,workspace=str(workspace),memory=str(memory),machinery=machinery(),
        scope='public Java DEVELOPMENT; teacher-assisted acquisition attributed; no general RSI or independent blind claim',
        fixed_revision_consulted=False,plausible_is_not_correct=True),'plan_digest')
    _write_new(output/'PLAN.json',plan)
    for name in plan['machinery']:
        target=workspace/'machinery-snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    print('Prepared',cases,'teacher cases',plan['teacher_cases'],flush=True)


def execute(output):
    plan=json.loads((output/'PLAN.json').read_text());checked(plan,'plan_digest')
    if plan['machinery']!=machinery():raise ValueError('frozen machinery changed')
    if (output/'STARTED.json').exists():raise ValueError('one-shot started; preserve prior attempt')
    store=RepairExperience(Path(plan['memory']))
    if digest_of(store.events())!=plan['initial_memory_digest']:raise ValueError('initial memory changed')
    _write_new(output/'STARTED.json',dict(plan_digest=plan['plan_digest']))
    sandbox=RecordingSandbox(Path(plan['workspace']),image=plan['image'],limits=SandboxLimits(timeout_seconds=plan['command_timeout_seconds']))
    training=[];outcomes=[];accepted_candidates={}
    try:
        probe=sandbox.probe();_write_new(output/'SANDBOX_PROBE.json',probe)
        if not probe['isolated']:raise ValueError('isolation failure')
        options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,float(m['pricing']['completion'])*1e6*1.01) for m in plan['catalog']]
        load_api_key()
        for case in plan['teacher_cases']:
            directory='training-'+case+'-b';project,bug=case.rsplit('-',1)
            if not sandbox.checkout(project,int(bug),'b',directory).ok:raise ValueError('teacher checkout failed')
            root=sandbox.workspace/directory;evidence=collect_evidence(sandbox,directory)
            before=len(store.events());router=EconomicRouter(options,store);fallback=EconomicRouter(options,store,0)
            result=solve_development(root,evidence,router,lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                role='released_development',budget_usd=plan['teacher_api_budget_per_case'],validation_budget=plan['teacher_validation_budget'],
                max_models=plan['max_models'],max_rounds_per_model=plan['max_rounds_per_model'],fallback_router=fallback,
                learn_transformation_proposals=True)
            candidate=result.pop('candidate');replay=None
            if candidate:
                fresh=RepairExperience(store.path);repeated=next(c for c in fresh.candidates(root,evidence,2) if c.digest==candidate.digest)
                replay=validate(sandbox,directory,repeated,evidence['failing_tests'])
                if not replay['plausible']:raise ValueError('teacher repair replay failed')
            row=dict(case=case,result=result,accepted=descriptor(candidate) if candidate else None,replay=replay,
                new_events=store.events()[before:],scope='exposed development training; no fresh-transfer score')
            training.append(row);_write_new(output/(case+'.TEACHER.json'),sealed(row,'teacher_digest'))
            print(case,'teacher solved',result['solved'],'API',result['known_cost_usd'],flush=True)
        source_policy=acquire(store.events());policy=refine(source_policy)
        _write_new(output/'LEARNING.json',sealed(dict(source_policy=source_policy,expression_policy=policy,
            operator_policy=plan['initial_operator_policy'],training_memory_digest=digest_of(store.events()),
            training_events=len(store.events()),teacher_origins_preserved=True),'learning_digest'))
        # Existing authored gates remain labelled substrate selection, not real evidence.
        gates=selection_gate(dict(child_policy=source_policy,generations=[source_policy]),output,sandbox)
        frozen_memory=store.events();_write_new(output/'TRANSFER_MEMORY.json',sealed(dict(events=frozen_memory,memory_digest=digest_of(frozen_memory)),'memory_record_digest'))
        for case in plan['cases']:
            project,bug=case.rsplit('-',1);directory=case+'-b'
            if not sandbox.checkout(project,int(bug),'b',directory).ok:raise ValueError('transfer checkout failed')
            root=sandbox.workspace/directory;evidence=collect_evidence(sandbox,directory)
            analysis=analyze_sources(sandbox,directory,evidence,max_sources=plan['max_analyzed_sources'])
            _write_new(output/(case+'.ANALYSIS.json'),analysis);_write_new(output/(case+'.EVIDENCE.json'),evidence)
            local=list(strategist_proposer(plan['local_pool_budget'],preserve_provenance=True)(root,evidence,(),plan['local_pool_budget']))
            exact=list(store.candidates(root,evidence,2));learned=generate(root,evidence,policy,limit=64)
            def unique(items):return list({c.digest:c for c in items}.values())
            parent=unique(exact+local);child_raw=unique(exact+learned+local)
            child,screen=structural_screen(root,child_raw,analysis)
            _write_new(output/(case+'.POOL.json'),sealed(dict(case=case,parent=[descriptor(c) for c in parent],
                child_raw=[descriptor(c) for c in child_raw],child=[descriptor(c) for c in child],
                exact_candidates=len(exact),learned_candidates=len(learned),screen=screen),'pool_digest'))
            arms={};accepted={}
            for name,candidates in (('parent',parent),('child',child)):
                counts={'choice':0,'attempt':0};started=time.monotonic()
                def record(kind,data):
                    counts[kind]+=1;_write_new(output/(case+'.'+name+f'.{kind.upper()}{counts[kind]}.json'),data)
                result=search(candidates,plan['initial_operator_policy'],lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                    budget=plan['validation_budget'],reactive=name=='child',record=record)
                accepted[name]=result.pop('accepted');result['seconds']=time.monotonic()-started
                arms[name]=sealed(dict(case=case,arm=name,**result),'arm_digest');_write_new(output/(case+'.'+name+'.ARM.json'),arms[name])
                print(case,name,'solved',result['solved'],'compilations',result['candidate_compilations'],flush=True)
            row=dict(case=case,arms=arms,analysis_digest=analysis['analysis_digest'],
                accepted={name:descriptor(c) if c else None for name,c in accepted.items()},
                success_recorded=False,replay_verified=False)
            outcomes.append(row);accepted_candidates[case]=accepted['child'] or accepted['parent']
            _write_new(output/(case+'.COMPARISON.json'),sealed(row,'comparison_digest'))
        gains=[r['case'] for r in outcomes if r['arms']['child']['solved'] and not r['arms']['parent']['solved']]
        regressions=[r['case'] for r in outcomes if r['arms']['parent']['solved'] and not r['arms']['child']['solved']]
        pv=sum(r['arms']['parent']['candidate_compilations'] for r in outcomes);cv=sum(r['arms']['child']['candidate_compilations'] for r in outcomes)
        decision=sealed(dict(gains=gains,regressions=regressions,parent_compilations=pv,child_compilations=cv,
            promoted=bool(gains) and not regressions and cv<=pv,rule=plan['gate'],policy_digest=policy['policy_digest']),'decision_digest')
        _write_new(output/'DECISION.json',decision)
        for row in outcomes:
            case=row['case'];candidate=accepted_candidates[case]
            if candidate:
                directory=case+'-b';root=sandbox.workspace/directory;evidence=json.loads((output/(case+'.EVIDENCE.json')).read_text())
                verdict=next(s['verdict'] for arm in row['arms'].values() for s in arm['steps'] if s['verdict']['candidate_digest']==candidate.digest and s['verdict']['plausible'])
                store.retain(root,evidence,candidate,verdict,role='released_development')
                repeated=next(c for c in RepairExperience(store.path).candidates(root,evidence,2) if c.digest==candidate.digest)
                replay=validate(sandbox,directory,repeated,evidence['failing_tests'])
                row.update(success_recorded=True,replay_verified=replay['plausible'],replay=replay)
                if not replay['plausible']:raise ValueError('transfer durable replay failed')
            for name,arm in row['arms'].items():
                for step in arm['steps']:store.append('quality_validation',dict(case=case,arm=name,**step))
            _write_new(output/(case+'.RETENTION.json'),sealed(row,'retention_digest'))
        store.append('quality_trial',dict(source_trial=output.name,expression_policy=policy,operator_policy=plan['initial_operator_policy'],decision=decision))
        final=store.events();calls=[e['data'] for e in final[len(plan['initial_memory']):] if e['kind']=='call']
        unknown=sum(c.get('cost_usd') is None for c in calls);cost=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None)
        summary=dict(cases=3,parent_solved=sum(r['arms']['parent']['solved'] for r in outcomes),child_solved=sum(r['arms']['child']['solved'] for r in outcomes),
            parent_compilations=pv,child_compilations=cv,policy_promoted=decision['promoted'],
            teacher_solved=sum(r['result']['solved'] for r in training),teacher_success_replays=sum(bool(r['replay'] and r['replay']['plausible']) for r in training),
            transfer_successes_recorded=sum(r['success_recorded'] for r in outcomes),transfer_replays=sum(r['replay_verified'] for r in outcomes),
            new_api_requests=sum(c.get('request_sent',True) for c in calls),known_api_cost_usd=cost,total_api_cost_usd=None if unknown else cost,
            new_unknown_costs=unknown,transfer_model_calls=0,acquired_rules=len(source_policy['rules']),refined_rules=len(policy['rules'])-len(source_policy['rules']),
            final_memory_events=len(final),general_rsi_demonstrated=False)
        _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],training=training,outcomes=outcomes,gates=gates,decision=decision,
            summary=summary,final_memory_events=final,final_memory_digest=digest_of(final),scope=plan['scope']),'result_digest'))
        print(json.dumps(summary,indent=2),flush=True)
    except Exception as error:
        _write_new(output/'ABORTED.json',sealed(dict(plan_digest=plan['plan_digest'],error=str(error)[:500],error_type=type(error).__name__,
            training=training,outcomes=outcomes,final_memory_events=store.events()),'abort_digest'));raise


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','run']);p.add_argument('--output',type=Path,required=True);p.add_argument('--workspace',type=Path);p.add_argument('--catalog',type=Path)
    a=p.parse_args()
    if a.action=='prepare':
        if not a.workspace or not a.catalog:p.error('workspace and catalog required')
        prepare(a.output.resolve(),a.workspace.resolve(),a.catalog.resolve())
    else:execute(a.output.resolve())
