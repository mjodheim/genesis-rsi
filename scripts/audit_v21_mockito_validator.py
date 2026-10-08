#!/usr/bin/env python3
"""Explicit post-freeze infrastructure-only correction for Mockito-22.

NEVER rewrites the original negative result nor any frozen candidate list.
The original evaluation's shared build-directory ignore rule accidentally
removed Mockito/lib/build. The one general correction retains build dirs,
while still omitting compiled *.class, Gradle cache, logs and git metadata.
"""
from __future__ import annotations
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from genesis.trust_root import digest_of
from scripts.run_autonomous_defects4j_lang import D4J, _run, _failing_count
from scripts.run_v21_fresh_repair_trial import (
    BENCH,FROZEN,OUTCOME,PUBLIC_INDEX,
    _open_verified,_verify_validator_inputs,read_locked_manifest,
)

AMENDMENT=ROOT/'experiment/v2/V21_FRESH_3PROJECT_VALIDATOR_AMENDMENT_20261008.json'
RESULT=ROOT/'experiment/v2/V21_FRESH_3PROJECT_MOCKITO_CORRECTED_20261008.json'


def isolation(root: Path, path: Path) -> None:
    shutil.copytree(root,path,ignore=shutil.ignore_patterns(
        '.git','target','*.class','*.log','.gradle'
    ))


def evaluate_candidate(original_root: Path,item: dict,triggers: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix='v21-audited-validator-',dir=BENCH) as temp:
        clone=Path(temp)/'buggy'
        isolation(original_root,clone)
        source,_=_verify_validator_inputs(clone,item)
        source.write_text(item['content_utf8'])
        try:
            compile_run=_run([str(D4J),'compile'],cwd=clone,check=False,timeout=180)
        except subprocess.TimeoutExpired:
            return {'compiled':False,'full_suite_pass':False,'error':'compile_timeout'}
        if compile_run.returncode:
            return {
                'compiled':False,'full_suite_pass':False,'error':'compile_failed',
                'compile_output_sha256':sha256(compile_run.stdout.encode()).hexdigest(),
            }
        feedback=[]
        for trigger in triggers:
            try:
                run=_run([str(D4J),'test','-t',trigger],cwd=clone,check=False,timeout=120)
                feedback.append({
                    'test':trigger,'exit':run.returncode,'failures':_failing_count(run.stdout),
                    'output_sha256':sha256(run.stdout.encode()).hexdigest(),
                })
            except subprocess.TimeoutExpired:
                feedback.append({'test':trigger,'exit':None,'failures':None,'error':'trigger_timeout'})
        if any(r['failures'] is not None and r['failures']>0 for r in feedback):
            return {'compiled':True,'full_suite_ran':False,'full_suite_pass':False,
                    'error':'original_public_trigger_fails','triggers':feedback}
        try:
            whole=_run([str(D4J),'test'],cwd=clone,check=False,timeout=300)
        except subprocess.TimeoutExpired:
            return {'compiled':True,'full_suite_ran':False,'full_suite_pass':False,
                    'error':'full_suite_timeout','triggers':feedback}
        failures=_failing_count(whole.stdout)
        return {
            'compiled':True,'full_suite_ran':True,
            'full_suite_pass':failures==0 and whole.returncode==0,
            'full_suite_failures':failures,'test_exit':whole.returncode,
            'test_output_sha256':sha256(whole.stdout.encode()).hexdigest(),
            'triggers':feedback,
        }


def audited_baseline(root: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix='v21-audited-control-',dir=BENCH) as tmp:
        dest=Path(tmp)/'buggy'
        isolation(root,dest)
        run=_run([str(D4J),'compile'],cwd=dest,check=False,timeout=180)
        if run.returncode:
            raise RuntimeError('fixed isolated validator still does not compile untouched control')
        return {
            'compiled':True,
            'compile_exit':run.returncode,
            'compile_output_sha256':sha256(run.stdout.encode()).hexdigest(),
        }


def main():
    locked=read_locked_manifest()
    amend=_open_verified(AMENDMENT,'amendment_digest')
    candidates=_open_verified(FROZEN,'freeze_digest')
    original=_open_verified(OUTCOME,'result_digest')
    public=_open_verified(PUBLIC_INDEX,'index_digest')
    if RESULT.exists():
        raise RuntimeError('refusing to overwrite corrected independent validation')
    if (amend['original_result_digest']!=original['result_digest']
            or amend['unchanged_candidate_freeze_digest']!=candidates['freeze_digest']
            or public['all_candidates_freeze_digest']!=candidates['freeze_digest']
            or amend['original_preregistration_digest']!=locked['preregistration_digest']):
        raise RuntimeError('scientific lineage mismatch')
    case=next(c for c in candidates['cases'] if (c['project'],c['bug_id'])==('Mockito',22))
    root=Path(case['buggy_root'])
    control=audited_baseline(root)
    print('VALIDATOR_UNMODIFIED_SOURCE_CONTROL_PASSED',flush=True)
    unique={}
    for arm in locked['arms']:
        for record in case['arms'][arm]['candidates']:
            key=(record['path'],record['candidate_sha256'])
            if key in unique and record!=unique[key]:
                raise RuntimeError('candidate identity collision')
            unique[key]=record
    results={}
    for index,(key,record) in enumerate(sorted(unique.items()),1):
        _verify_validator_inputs(root,record)
        outcome=evaluate_candidate(root,record,case['triggers'])
        _verify_validator_inputs(root,record)
        results[key]=outcome
        print('REVALIDATED_MOCKITO',index,'of',len(unique),
              'compiled',outcome.get('compiled'),
              'full_suite_pass',outcome.get('full_suite_pass'),
              'error',outcome.get('error'),flush=True)
    arms={}
    for arm in locked['arms']:
        entries=case['arms'][arm]['candidates']
        observed=[results[(c['path'],c['candidate_sha256'])] for c in entries]
        successes=[rank for rank,res in enumerate(observed,1) if res.get('full_suite_pass')]
        arms[arm]={
            'tested_count':len(entries),
            'compiled_count':sum(x.get('compiled') is True for x in observed),
            'full_suite_pass_count':len(successes),
            'first_full_suite_pass_rank':min(successes) if successes else None,
            'candidate_index_digest':case['arms'][arm]['candidate_index_digest'],
        }
    body={
        'schema':'genesis-v21-corrected-verified-mockito-retest-v1',
        'amendment_digest':amend['amendment_digest'],
        'unchanged_candidate_freeze_digest':candidates['freeze_digest'],
        'original_invalid_result_digest':original['result_digest'],
        'positive_control':control,
        'project':'Mockito','bug_id':22,
        'distinct_frozen_candidates_retested':len(unique),
        'arms':arms,
        'candidate_outcomes':[{
            'path':key[0],'sha256':key[1],'result':value
        } for key,value in sorted(results.items())],
        'policy_and_candidate_generation_unchanged':True,
        'postfreeze_evaluator_amendment':True,
        'independent_semantic_repair_success_not_assumed':True,
    }
    RESULT.parent.mkdir(parents=True,exist_ok=True)
    RESULT.write_text(json.dumps({**body,'audit_digest':digest_of(body)},indent=2,sort_keys=True)+'\n')
    print('MOCKITO_CORRECTED_RETEST_FINISHED',
          {a:v['full_suite_pass_count'] for a,v in arms.items()},flush=True)


if __name__=='__main__':
    main()
