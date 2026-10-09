#!/usr/bin/env python3
"""Execute a sealed three-case development plan, verify durable learning and replay."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/"scripts"))
from genesis.adaptive_repair import EconomicRouter, ModelOption, RepairExperience, solve_development
from genesis.defects4j_sandbox import Defects4JSandbox
from genesis.repair_bench import collect_evidence, validate
from genesis.repair_proposers import strategist_proposer
from genesis.trust_root import digest_of
from run_adaptive_repair import sealed

MACHINERY=('genesis/adaptive_repair.py','genesis/openrouter_repair.py',
    'genesis/repair_proposers.py','genesis/repair_strategist.py','genesis/repair_bench.py',
    'genesis/defects4j_sandbox.py','scripts/run_adaptive_repair.py',
    'scripts/run_adaptive_repair_trial.py')


def machinery():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in MACHINERY}


def write_sealed(path,body,key):
    if path.exists():raise ValueError(f'refusing to overwrite {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({**body,key:digest_of(body)},indent=2,sort_keys=True)+'\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    args=p.parse_args();plan=sealed(args.plan,'plan_digest')
    if plan['machinery_sha256']!=machinery():raise ValueError('machinery differs from plan')
    split=sealed(ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json','split_digest')
    if any(c not in split['development'] for c in plan['cases']):raise ValueError('development cases only')
    workspace=Path(plan['workspace']);store=RepairExperience(Path(plan['memory']))
    if digest_of(store.events())!=plan['initial_memory_digest']:raise ValueError('initial memory differs')
    if plan['catalog_digest']!=digest_of(plan['catalog']):raise ValueError('catalog differs')
    options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,
                         float(m['pricing']['completion'])*1e6*1.01) for m in plan['catalog']]
    if {o.model for o in options}!={'anthropic/claude-haiku-5.5','openai/gpt-6-luna'}:
        raise ValueError('only approved Haiku/Luna models')
    router=EconomicRouter(options,store)
    fallback=EconomicRouter(options,store,minimum_observed_success_rate=0)
    sandbox=Defects4JSandbox(workspace);probe=sandbox.probe()
    if not probe['isolated']:raise ValueError('sandbox boundary failed')
    outcomes=[]
    for case in plan['cases']:
        print('START',case,flush=True)
        case_path=ROOT/'experiment/bench'/f"{plan['name']}_{case}_RESULT.json"
        if case_path.exists():raise ValueError('case already observed; no automatic retry')
        before=store.events();directory=case+'-b';project,bug=case.rsplit('-',1)
        result=None;candidate=None;recorded=False;replay=None;evidence=None;patch=None
        try:
            if not (workspace/directory).is_dir() and not sandbox.checkout(project,int(bug),'b',directory).ok:
                raise ValueError('checkout failed')
            evidence=collect_evidence(sandbox,directory);root=workspace/directory
            result=solve_development(root,evidence,router,
                lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                role='released_development',budget_usd=plan['budget_usd_per_case'],
                validation_budget=plan['validation_budget'],local_validation_budget=plan['local_candidates'],
                local_proposer=strategist_proposer(plan['local_candidates']),max_models=2,
                max_rounds_per_model=plan['max_rounds_per_model'],fallback_router=fallback)
            candidate=result.pop('candidate');after=RepairExperience(store.path).events()
            recipes=[e['data'] for e in after[len(before):] if e['kind']=='recipe']
            recorded=bool(candidate and any(r['candidate_digest']==candidate.digest for r in recipes))
            replay=None;patch=None
            if result['solved']:
                if not recorded:raise ValueError('successful candidate absent from durable recipe memory')
                patch=''.join(difflib.unified_diff((root/candidate.path).read_text().splitlines(keepends=True),
                    candidate.content.splitlines(keepends=True),fromfile='a/'+candidate.path,tofile='b/'+candidate.path))
                # A fresh database reader verifies persistence; no local operators or LLM allowed.
                replay_store=RepairExperience(store.path)
                replay_router=EconomicRouter(options,replay_store)
                replay=solve_development(root,evidence,replay_router,
                    lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                    role='released_development',allow_llm=False,validation_budget=2)
                replay_candidate=replay.pop('candidate')
                if not replay['reuse_without_llm'] or replay['model_calls'] or replay_candidate.digest!=candidate.digest:
                    raise ValueError('durable memory replay failed')
            body=dict(case=case,usable=True,evidence=evidence,result=result,
                success_recorded=recorded,accepted_candidate_digest=candidate.digest if candidate else None,
                accepted_origin=candidate.origin if candidate else None,patch=patch,replay=replay,
                memory_before_digest=digest_of(before),memory_after_digest=digest_of(RepairExperience(store.path).events()),
                new_memory_events=RepairExperience(store.path).events()[len(before):],plan_digest=plan['plan_digest'])
        except Exception as error:
            body=dict(case=case,aborted=True,error_type=type(error).__name__,
                result=result,evidence=evidence,success_recorded=recorded,replay=replay,
                accepted_origin=candidate.origin if candidate else None,
                plan_digest=plan['plan_digest'],new_memory_events=RepairExperience(store.path).events()[len(before):])
        write_sealed(case_path,body,'result_digest');outcomes.append(body)
        print(case,json.dumps({k:body.get(k) for k in ('aborted','success_recorded','accepted_origin')}),flush=True)
    final_events=RepairExperience(store.path).events()
    calls=[e['data'] for e in final_events if e['kind']=='call'][
        sum(e['kind']=='call' for e in json.loads(Path(plan['initial_memory_snapshot']).read_text())):]
    unknown=sum(c.get('cost_usd') is None for c in calls)
    total=sum(c['cost_usd'] for c in calls if c.get('cost_usd') is not None)
    summary=dict(cases=len(outcomes),aborted_cases=sum(bool(o.get('aborted')) for o in outcomes),
        solved=sum(bool((o.get('result') or {}).get('solved')) for o in outcomes),
        solved_without_llm=sum(bool((o.get('result') or {}).get('solved_without_llm')) for o in outcomes),
        successes_recorded=sum(bool(o.get('success_recorded')) for o in outcomes),
        successful_memory_replays=sum(bool((o.get('replay') or {}).get('reuse_without_llm')) for o in outcomes),
        actual_requests=sum(c.get('request_sent',True) for c in calls),known_cost_usd=total,
        total_cost_usd=None if unknown else total,calls_with_unknown_cost=unknown)
    write_sealed(ROOT/'experiment/bench'/f"{plan['name']}_RESULT.json",
        dict(schema='genesis-three-case-adaptive-development-v1',plan_digest=plan['plan_digest'],
            outcomes=outcomes,summary=summary,sandbox_probe=probe,final_memory_events=final_events,
            final_memory_digest=digest_of(final_events),scope='exposed development; no fresh/general-RSI claim',
            plausible_is_not_correct=True,fixed_revision_consulted=False),'result_digest')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
