#!/usr/bin/env python3
"""Run bounded adaptive repairs on explicitly released Defects4J development cases.

Example: python scripts/run_adaptive_repair.py --case Csv-16 --workspace /tmp/repair-demo
         --memory /tmp/repair-memory.sqlite --catalog experiment/bench/ADAPTIVE_REPAIR_CATALOG_20261008.json
         --comparison experiment/bench/DEV_MODEL_COST_COMPARISON1_RESULT.json
         --learn-trial DEV_COST_COMPARE2_HAIKU_CSV --output /tmp/repair-demo-result.json

Learning a prior trial revalidates its accepted patch before memory admission.
Each invocation revalidates retained proposals and keeps the buggy source intact.
"""
import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from genesis.adaptive_repair import EconomicRouter, ModelOption, RepairExperience, solve_development, task_features
from genesis.defects4j_sandbox import Defects4JSandbox
from genesis.repair_bench import Candidate, collect_evidence, validate
from genesis.openrouter_repair import _allowed
from genesis.trust_root import digest_of
from genesis.repair_stall_recovery import recover
from genesis.repair_quality_learning import operator_policy
from genesis.repair_proposers import strategist_proposer
from genesis.repair_contract_learning import generate as contract_candidates, validate_policy as validate_contract_policy


def sealed(path, field):
    data = json.loads(path.read_text())
    if data.get(field) != digest_of({k:v for k,v in data.items() if k!=field}):
        raise ValueError(f'invalid record: {path}')
    return data


def apply_archived_patch(original, patch):
    old=original.splitlines(keepends=True); out=[]; cursor=0; active=False
    for line in patch.splitlines(keepends=True):
        if line.startswith('@@'):
            match=re.match(r'@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@',line)
            if not match: raise ValueError('invalid patch hunk')
            pos=int(match[1])-1
            if pos < cursor or pos > len(old): raise ValueError('overlapping/out-of-range hunk')
            out.extend(old[cursor:pos]);cursor=pos;active=True
        elif active and line[:1] in (' ', '-', '+'):
            if line[0] in (' ', '-'):
                if cursor >= len(old) or old[cursor]!=line[1:]: raise ValueError('patch context mismatch')
                cursor+=1
            if line[0] in (' ', '+'):out.append(line[1:])
        elif active: raise ValueError('unsupported patch line')
    if not active: raise ValueError('no patch hunks')
    out.extend(old[cursor:]);return ''.join(out)


def import_comparison(store, path):
    record=sealed(path,'comparison_digest'); identity=record['comparison_digest']
    if any(e['kind']=='comparison_import' and e['data']['digest']==identity for e in store.events()):return
    if 'exposed' not in record.get('scope',''):
        raise ValueError('only exposed development comparisons may seed policy')
    for model in record['models']:
        legacy_ids = {'Qwen3 Coder':'qwen/qwen3-coder', 'GLM-5.3 Flash':'z-ai/glm-5.3-flash',
                      'DeepSeek V4.1 Flash':'deepseek/deepseek-v4.1-flash', 'DeepSeek V4 Pro':'deepseek/deepseek-v4-pro'}
        model_id = model.get('model') or legacy_ids.get(model['label'])
        if not model_id: raise ValueError('comparison model identity missing')
        trials=[r['name'] for r in record['trial_records'] if r['model']==model_id]
        for outcome in model['cases']:
            if not outcome.get('usable'): continue
            calls=[]
            for name in trials:
                for filename, events in record['evidence'][name].items():
                    if not filename.endswith('.calls.jsonl'):continue
                    for event in events:
                        if event['event_digest']!=digest_of({k:v for k,v in event.items() if k!='event_digest'}):
                            raise ValueError('invalid call evidence')
                        if event['case']==outcome['case']:calls.append(event['call'])
            cost=None if any(c.get('cost_usd') is None for c in calls) else sum(c['cost_usd'] for c in calls)
            store.record_attempt({'complexity':'any','family':'released_comparison'},model_id,cost,outcome['solved'],role='released_development')
    store.append('comparison_import',dict(digest=identity))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case',required=True);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--memory',type=Path,required=True);p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--comparison',type=Path,action='append',default=[])
    p.add_argument('--learn-trial');p.add_argument('--budget',type=float,default=.05)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--max-models',type=int,default=2)
    p.add_argument('--minimum-success-rate',type=float,default=.5)
    p.add_argument('--localize-assertions',action='store_true',help='Opt in to static production API localisation when stack frames are absent')
    p.add_argument('--recover-stalls',action='store_true',help='Try bounded failure-derived local generations before model assistance')
    p.add_argument('--contract-policy',type=Path,help='Explicit opt-in learned constructor insertion policy')
    p.add_argument('--nonnull-contracts',type=Path,help='Caller-supplied production path/constructor/parameter contracts')
    args=p.parse_args()
    if bool(args.contract_policy)!=bool(args.nonnull_contracts):raise ValueError('policy and explicit contracts required together')
    if args.output.exists():raise ValueError('refusing to overwrite result before execution')
    split=sealed(ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json','split_digest')
    if args.case not in split['development']:raise ValueError('only exposed development cases allowed')
    args.workspace.mkdir(parents=True,exist_ok=True)
    sandbox=Defects4JSandbox(args.workspace);probe=sandbox.probe()
    if not probe['isolated']:raise ValueError('sandbox boundary failed')
    project,bug=args.case.rsplit('-',1);directory=args.case+'-b'
    if not (args.workspace/directory).is_dir() and not sandbox.checkout(project,int(bug),'b',directory).ok:
        raise ValueError('checkout failed')
    evidence=collect_evidence(sandbox,directory,localize_assertions=args.localize_assertions); root=args.workspace/directory
    store=RepairExperience(args.memory)
    for path in args.comparison:import_comparison(store,path)
    catalog=json.loads(args.catalog.read_text())
    options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,
                         float(m['pricing']['completion'])*1e6*1.01,
                         None if m['id'].startswith('qwen/') else 'low') for m in catalog]
    learning=None
    if args.learn_trial:
        pre=sealed(ROOT/'experiment/bench'/f'TRIAL_{args.learn_trial}_PREREG.json','preregistration_digest')
        result=sealed(ROOT/'experiment/bench'/f'TRIAL_{args.learn_trial}_RESULT.json','result_digest')
        if pre['held_out'] or result['preregistration_digest']!=pre['preregistration_digest']:
            raise ValueError('held-out or mismatched trial cannot teach this service')
        case=next(c for c in result['cases'] if c['case']==args.case)
        arm=next(a for a in case['arms'].values() if a['solved'])
        path=arm['plausible_path'];target=_allowed(root,path,evidence)
        if not target.resolve().is_relative_to((root/evidence['source_directory']).resolve()):
            raise ValueError('archived patch is not production source')
        candidate=Candidate(path,apply_archived_patch(target.read_text(),arm['plausible_patch']),
                            'released-trial:'+args.learn_trial,'Previously suite-validated exact-text repair; explanation limited to archived patch.')
        learning=validate(sandbox,directory,candidate,evidence['failing_tests'])
        store.retain(root,evidence,candidate,learning,role='released_development')
    recovery=None
    if args.recover_stalls:
        recovery=recover(lambda size,history:strategist_proposer(size,preserve_provenance=True)(root,evidence,(),size),
            operator_policy([]),lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
            generation_sizes=(2,8,32),budget=12)
        local_candidate=recovery.pop('accepted')
        for generation in recovery['generations']:
            store.append('search_generation',generation['proposal'])
            for attempt in generation['attempts']:
                store.append('local_validation',attempt)
        if local_candidate:
            store.retain(root,evidence,local_candidate,recovery['generations'][-1]['attempts'][-1]['verdict'],role='released_development')
    router=EconomicRouter(options,store,minimum_observed_success_rate=args.minimum_success_rate)
    ranking=[{**{k:v for k,v in r.items() if k!='option'},'model':r['option'].model} for r in router.rank(evidence,args.budget)]
    contract_proposer=None
    if args.contract_policy:
        insertion_policy=json.loads(args.contract_policy.read_text());validate_contract_policy(insertion_policy)
        contracts=json.loads(args.nonnull_contracts.read_text())
        def contract_proposer(project_root,case_evidence,history,remaining):
            tried={c.digest for c,_ in history}
            return [c for c in contract_candidates(project_root,case_evidence,insertion_policy,contracts)
                    if c.digest not in tried][:remaining]
    result=solve_development(root,evidence,router,
        lambda c:validate(sandbox,directory,c,evidence['failing_tests']),role='released_development',
        budget_usd=args.budget,max_models=args.max_models,
        local_proposer=contract_proposer,local_feedback_rounds=4 if contract_proposer else 1)
    candidate=result.pop('candidate')
    body=dict(schema='genesis-adaptive-repair-development-v1',case=args.case,
        evidence=evidence,features=task_features(evidence),initial_ranking=ranking,
        learning_verdict=learning,stall_recovery=recovery,result=result,candidate_digest=candidate.digest if candidate else None,
        sandbox_probe=probe,plausible_is_not_correct=True,general_understanding_demonstrated=False,
        memory_source='explicit released-development trial(s) and online outcomes')
    if args.output.exists():raise ValueError('refusing to overwrite result')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({**body,'result_digest':digest_of(body)},indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('verdicts','model_calls')},indent=2))


if __name__=='__main__':main()
