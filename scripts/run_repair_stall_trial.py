#!/usr/bin/env python3
"""Exposed-case engineering recovery; never a fresh transfer experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import urllib.request
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import EconomicRouter,ModelOption,RepairExperience,solve_development
from genesis.defects4j_sandbox import SandboxLimits
from genesis.g12_operator_lab import _write_new
from genesis.repair_bench import validate
from genesis.repair_proposers import strategist_proposer
from genesis.repair_quality_learning import operator_policy
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_source_localization import enrich
from genesis.repair_stall_recovery import recover
from genesis.trust_root import digest_of
from scripts.run_real_repair_transfer import RecordingSandbox,load_api_key


def run(output):
    if output.exists():raise ValueError('fresh output required; preserve interrupted attempts')
    prior=ROOT/'experiment/bench/DEV_REPAIR_QUALITY_TRANSFER1'
    old=json.loads((prior/'PLAN.json').read_text());checked(old,'plan_digest')
    pointer=json.loads((ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text());checked(pointer,'pointer_digest')
    events=RepairExperience(Path(pointer['path'])).events()
    if digest_of(events)!=pointer['memory_digest']:raise ValueError('memory mismatch')
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models',timeout=30) as response:
        catalog=json.load(response)['data']
    ids={'anthropic/claude-haiku-5.5','openai/gpt-6-luna'}
    models=[m for m in catalog if m['id'] in ids]
    if {m['id'] for m in models}!=ids:raise ValueError('approved models unavailable')
    if any(float(m['pricing'][k])>1e-6 for m in models for k in ('prompt','completion')):raise ValueError('tariff ceiling exceeded')
    output.mkdir(parents=True)
    memory=output/'experience.sqlite'
    with sqlite3.connect(pointer['path']) as source,sqlite3.connect(memory) as target:source.backup(target)
    plan=sealed(dict(cases=old['cases'],scope='previously exposed development engineering; no fresh transfer',
        generation_sizes=[2,8,32],local_validation_budget=12,teacher_budget_usd=.05,
        teacher_validation_budget=8,max_models=2,max_rounds_per_model=2,
        initial_memory_digest=digest_of(events),image=old['image'],workspace=old['workspace'],
        catalog=[dict(id=m['id'],pricing=m['pricing']) for m in models],
        machinery={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'genesis').rglob('*.py'))+[Path(__file__).resolve()]},
        success_endpoint='full suite and fresh-reader replay on all three exposed cases; does not establish general RSI'), 'plan_digest')
    _write_new(output/'PLAN.json',plan)
    for name in plan['machinery']:
        dest=output/'snapshot'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    store=RepairExperience(memory);sandbox=RecordingSandbox(Path(old['workspace']),image=old['image'],limits=SandboxLimits(timeout_seconds=180))
    options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,float(m['pricing']['completion'])*1e6*1.01) for m in models]
    outcomes=[]
    try:
        for case in plan['cases']:
            directory=case+'-b';root=sandbox.workspace/directory
            evidence=json.loads((prior/(case+'.EVIDENCE.json')).read_text());checked(evidence,'evidence_digest')
            localized=enrich(root,evidence);_write_new(output/(case+'.EVIDENCE.json'),localized)
            counts={}
            def record(kind,data):
                counts[kind]=counts.get(kind,0)+1
                _write_new(output/(case+'.'+kind+str(counts[kind])+'.json'),data)
            local=recover(lambda size,history:strategist_proposer(size,preserve_provenance=True)(root,localized,(),size),
                operator_policy([]),lambda c:validate(sandbox,directory,c,localized['failing_tests']),
                generation_sizes=plan['generation_sizes'],budget=plan['local_validation_budget'],record=record)
            candidate=local.pop('accepted');_write_new(output/(case+'.LOCAL.json'),sealed(local,'local_digest'))
            print(case,'local',local['solved'],local['stop_reason'],local['validated'],flush=True)
            teacher=None
            if not candidate:
                load_api_key();teacher=solve_development(root,localized,EconomicRouter(options,store),
                    lambda c:validate(sandbox,directory,c,localized['failing_tests']),role='released_development',
                    budget_usd=plan['teacher_budget_usd'],validation_budget=8,max_models=2,
                    max_rounds_per_model=2,fallback_router=EconomicRouter(options,store,0),learn_transformation_proposals=True)
                candidate=teacher.pop('candidate')
                _write_new(output/(case+'.TEACHER.json'),sealed(teacher,'teacher_digest'))
            else:
                receipt=local['generations'][-1]['attempts'][-1]['verdict']
                store.retain(root,localized,candidate,receipt,role='released_development')
            replay=None
            if candidate:
                fresh=RepairExperience(memory)
                repeated=next(c for c in fresh.candidates(root,localized,2) if c.digest==candidate.digest)
                replay=validate(sandbox,directory,repeated,localized['failing_tests'])
                if not replay['plausible']:raise ValueError('fresh-reader replay failed')
            row=dict(case=case,local=local,teacher=teacher,replay=replay,solved=bool(candidate))
            outcomes.append(row);_write_new(output/(case+'.RESULT.json'),sealed(row,'case_digest'))
            print(case,'final',bool(candidate),'replay',bool(replay),'cost',teacher['known_cost_usd'] if teacher else 0,flush=True)
        _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],outcomes=outcomes,
            all_solved=all(r['solved'] for r in outcomes),initial_events=events,events=store.events(),
            final_memory_digest=digest_of(store.events()),canonical_memory_updated=False,
            external_cost_usd=sum(r['teacher']['known_cost_usd'] for r in outcomes if r['teacher']),
            scope=plan['scope']),'result_digest'))
    except BaseException as exc:
        _write_new(output/'ABORTED.json',dict(error=str(exc),completed=outcomes));raise

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
