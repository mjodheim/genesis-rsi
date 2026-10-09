#!/usr/bin/env python3
"""Prospective development test of outcome-driven repair-search adaptation."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))

from genesis.g12_operator_lab import _write_new
from genesis.multilingual_repair_sandbox import run_task
from genesis.repair_search_adaptation import (derive_search_descendant, ordered_candidates,
    search_promotion, seed_search)
from genesis.repair_self_improvement import checked,sealed,validate_policy
from genesis.trust_root import digest_of
from run_repair_self_improvement import BAGS, SLOTS, MACHINERY, authored_task, grade, write_task

SOURCES=MACHINERY+['genesis/repair_search_adaptation.py','scripts/run_repair_search_adaptation.py']


def hashes():
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES}


def valid_task(task_id, language, delta, role, **kwargs):
    if any(not 0 <= slot+delta < len(bag) for bag in BAGS for slot in SLOTS):
        raise ValueError('exercise offset must stay in bounds in every language')
    return authored_task(task_id,language,delta,role,**kwargs)


def prepare(output:Path,source:Path,workspace:Path):
    result=json.loads((source/'RESULT.json').read_text());checked(result,'result_digest')
    original=json.loads((source/'PLAN.json').read_text());checked(original,'plan_digest')
    if result['plan_digest']!=original['plan_digest']:raise ValueError('source provenance mismatch')
    searches={}
    for file in source.glob('train-*.SEARCH.json'):
        search=json.loads(file.read_text());checked(search,'search_digest')
        searches[search['search_digest']]=search
    policy=validate_policy(result['final_policy']);parent=seed_search(policy)
    proposal=derive_search_descendant(parent,result,searches)
    # Task selection is explicit and frozen before the new policy sees outcomes.
    tasks=[valid_task('search-gate-python','python',2,'promotion',exemplar=True,renamed=True),
           valid_task('search-gate-javascript','javascript',3,'promotion',exemplar=True,renamed=True),
           valid_task('search-gate-regression-java','java',-1,'promotion',renamed=True),
           valid_task('search-final-python','python',3,'final_evaluation',exemplar=True,renamed=True),
           valid_task('search-final-javascript','javascript',2,'final_evaluation',exemplar=True,renamed=True),
           valid_task('search-final-java','java',3,'final_evaluation',exemplar=True,renamed=True)]
    output.mkdir(parents=True,exist_ok=True);workspace.mkdir(parents=True,exist_ok=True)
    body=dict(schema='genesis-repair-search-adaptation-development-plan-v1',source_result=result,
        source_plan_digest=original['plan_digest'],source_training_searches=searches,
        capability_policy=policy,parent_search=parent,proposal=proposal,
        tasks=tasks,candidate_budget=4,image=original['image'],workspace=str(workspace.resolve()),
        machinery=hashes(),external_model_calls=0,api_budget_usd=0,
        scope='authored development exercises; bounded search-order modification',
        final_evaluation_learning=False)
    plan=sealed(body,'plan_digest');_write_new(output/'PLAN.json',plan)
    dest=workspace/'machinery-snapshot'
    for name in plan['machinery']:
        target=dest/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    print('Prepared',output/'PLAN.json',flush=True)


def evaluate(task,capabilities,search_policy,plan,output):
    with tempfile.TemporaryDirectory(prefix='source-',dir=plan['workspace']) as temporary:
        directory=Path(temporary);write_task(directory,task)
        candidates=ordered_candidates(directory/'src',capabilities,search_policy,budget=plan['candidate_budget'])
        frozen=sealed(dict(task_digest=task['task_digest'],search_policy_digest=search_policy['search_policy_digest'],
                           candidates=candidates),'candidate_set_digest')
        key=task['task_id']+'-'+search_policy['search_policy_digest'][:12]
        _write_new(output/(key+'.SEARCH.json'),frozen)
        baseline=run_task(directory,task['language'],plan['image']);baseline_grade=grade(baseline,task)
        if (baseline['returncode']!=0 or baseline['timed_out'] or baseline_grade['observed'] is None
            or baseline_grade['passed']):
            raise ValueError('original must execute successfully and return incorrect answers')
        attempts=[];winner=None
        for candidate in candidates:
            mutation=candidate['mutations']
            if (len(mutation)!=1 or mutation[0]['path']!=Path(task['source_path']).name
                or mutation[0]['expected_sha256']!=hashlib.sha256(task['source'].encode()).hexdigest()):
                raise ValueError('candidate source mismatch')
            with tempfile.TemporaryDirectory(prefix='attempt-',dir=plan['workspace']) as temp:
                attempt_dir=Path(temp);write_task(attempt_dir,task,mutation[0]['content_utf8'])
                run=run_task(attempt_dir,task['language'],plan['image']);grading=grade(run,task)
            receipt=sealed(dict(task_id=task['task_id'],role=task['role'],candidate_digest=candidate['candidate_digest'],
                passed=grading['passed'],run=run,grading=grading),'receipt_digest')
            attempts.append(receipt);_write_new(output/(key+f'.ATTEMPT{len(attempts)}.json'),receipt)
            if grading['infrastructure_error']:raise RuntimeError('executor infrastructure error')
            if grading['passed']:winner=candidate;break
        result=sealed(dict(task_id=task['task_id'],task_digest=task['task_digest'],role=task['role'],
            search_policy_digest=search_policy['search_policy_digest'],candidate_budget=plan['candidate_budget'],
            passed=winner is not None,attempt_count=len(attempts),attempts=attempts,
            baseline_run=baseline,baseline_grade=baseline_grade,candidate_set_digest=frozen['candidate_set_digest'],
            external_model_calls=0,known_api_cost_usd=0),'evaluation_digest')
        _write_new(output/(key+'.EVALUATION.json'),result)
        return result


def execute(output:Path):
    plan=json.loads((output/'PLAN.json').read_text());checked(plan,'plan_digest')
    if hashes()!=plan['machinery']:raise ValueError('machinery changed after freeze')
    if (output/'STARTED.json').exists():
        raise ValueError('preserve previous run; no automatic retries')
    _write_new(output/'STARTED.json',{'plan_digest':plan['plan_digest']})
    policy=plan['capability_policy'];parent=plan['parent_search'];child=plan['proposal']['child']
    capability_digest=policy['policy_digest'];comparisons=[];final=[]
    try:
        for task in plan['tasks']:
            checked(task,'task_digest')
            if task['role']!='promotion':continue
            before=evaluate(task,policy,parent,plan,output)
            after=evaluate(task,policy,child,plan,output)
            comparisons.append(dict(task_id=task['task_id'],parent=before,child=after))
            print(task['task_id'],before['attempt_count'],'->',after['attempt_count'],flush=True)
        decision=search_promotion(parent,child,comparisons,budget=plan['candidate_budget'])
        _write_new(output/'DECISION.json',decision)
        active=child if decision['promoted'] else parent
        _write_new(output/'ACTIVE_SEARCH_POLICY.json',active)
        active_digest=active['search_policy_digest']
        for task in plan['tasks']:
            if task['role']!='final_evaluation':continue
            before=evaluate(task,policy,parent,plan,output)
            after=evaluate(task,policy,active,plan,output)
            final.append(dict(task_id=task['task_id'],language=task['language'],parent=before,child=after))
            print(task['task_id'],before['attempt_count'],'->',after['attempt_count'],flush=True)
        if policy['policy_digest']!=capability_digest or active['search_policy_digest']!=active_digest:
            raise ValueError('final evaluation changed policy')
        summary=dict(search_policy_promoted=decision['promoted'],promotion_tasks=len(comparisons),
            final_tasks=len(final),parent_final_passes=sum(r['parent']['passed'] for r in final),
            child_final_passes=sum(r['child']['passed'] for r in final),
            parent_final_validations=sum(r['parent']['attempt_count'] for r in final),
            child_final_validations=sum(r['child']['attempt_count'] for r in final),
            external_model_calls=0,api_cost_usd=0,general_rsi_demonstrated=False)
        _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],diagnosis=plan['proposal']['diagnosis'],
            decision=decision,final=final,active_search_policy=active,summary=summary,scope=plan['scope'],
            limitations=['two authored search orderings and an authored diagnosis',
                         'single authored bug family with observation-derived offsets',
                         'development tasks do not establish independent real-world RSI']), 'result_digest'))
        print(json.dumps(summary,indent=2),flush=True)
    except Exception as error:
        _write_new(output/'ABORTED.json',sealed(dict(plan_digest=plan['plan_digest'],error_type=type(error).__name__,
            error=str(error)[:500],comparisons=comparisons,final=final),'abort_digest'))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--source',type=Path)
    parser.add_argument('--workspace',type=Path);args=parser.parse_args()
    if args.action=='prepare':
        if not args.source or not args.workspace:parser.error('--source and --workspace required')
        prepare(args.output,args.source,args.workspace)
    else:execute(args.output)


if __name__=='__main__':main()
