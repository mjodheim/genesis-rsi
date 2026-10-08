#!/usr/bin/env python3
"""Recompute authored development grades from raw container outputs.

This checks integrity and recorded-output arithmetic, not independent execution
replication or authenticity of the evaluator.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of

KEYS=['result_digest','decision_digest','evaluation_digest','receipt_digest',
      'search_digest','candidate_set_digest','policy_digest','search_policy_digest','plan_digest']


def audit(directory):
    plan=json.loads((directory/'PLAN.json').read_text());checked(plan,'plan_digest')
    result=json.loads((directory/'RESULT.json').read_text());checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest']:raise ValueError('result/plan mismatch')
    for name,expected in plan['machinery'].items():
        archived=Path(plan['workspace'])/'machinery-snapshot'/name
        path=archived if archived.exists() else ROOT/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise ValueError('frozen source mismatch: '+name)
    tasks={t['task_id']:t for t in plan['tasks']}
    for task in tasks.values():checked(task,'task_digest')
    artifacts=0;evaluations=0;attempts=0
    for path in sorted(directory.glob('*.json')):
        if path.name=='VERIFICATION.json':continue
        document=json.loads(path.read_text())
        if path.name=='STARTED.json':
            if document['plan_digest']!=plan['plan_digest']:raise ValueError('started provenance mismatch')
            continue
        key=next((k for k in KEYS if k in document),None)
        if key is None:raise ValueError('unknown artifact: '+path.name)
        checked(document,key);artifacts+=1
        if not path.name.endswith('.EVALUATION.json'):continue
        evaluations+=1;task=tasks[document['task_id']];expected=task['expected']
        baseline=document['baseline_run'];checked(baseline,'run_digest')
        if baseline['returncode']!=0 or baseline['timed_out'] or json.loads(baseline['stdout'])==expected:
            raise ValueError('original must execute and fail host grading')
        passed=False
        for attempt in document['attempts']:
            checked(attempt,'receipt_digest');run=attempt['run'];checked(run,'run_digest');attempts+=1
            try:observed=json.loads(run['stdout'])
            except (TypeError,ValueError):observed=None
            good=(run['returncode']==0 and not run['timed_out'] and type(observed)is list
                  and all(type(value)is int for value in observed) and observed==expected)
            if attempt['passed']!=good:raise ValueError('host grade differs from raw output')
            passed=passed or good
        if document['passed']!=passed or document['attempt_count']!=len(document['attempts']):
            raise ValueError('evaluation summary mismatch')
    pools=0
    if 'diagnosis' in result:
        # Search-order changes must not benefit from different candidate pools.
        for row in result['decision']['comparisons']+result['final']:
            candidate_sets=[]
            for label in ['parent','child']:
                outcome=row[label]
                file=directory/(row['task_id']+'-'+outcome['search_policy_digest'][:12]+'.SEARCH.json')
                search=json.loads(file.read_text());checked(search,'candidate_set_digest')
                if search['candidate_set_digest']!=outcome['candidate_set_digest']:
                    raise ValueError('candidate set provenance mismatch')
                candidate_sets.append({digest_of(c['mutations']) for c in search['candidates']})
            if candidate_sets[0]!=candidate_sets[1]:raise ValueError('candidate pools differ')
            pools+=1
        summary=result['summary'];rows=result['final']
        for label in ['parent','child']:
            if summary[label+'_final_passes']!=sum(r[label]['passed'] for r in rows):
                raise ValueError('final pass total mismatch')
            if summary[label+'_final_validations']!=sum(r[label]['attempt_count'] for r in rows):
                raise ValueError('final validation total mismatch')
    else:
        if result['summary']['baseline_passes']!=sum(r['baseline']['passed'] for r in result['final']):
            raise ValueError('baseline total mismatch')
        if result['summary']['descendant_passes']!=sum(r['descendant']['passed'] for r in result['final']):
            raise ValueError('descendant total mismatch')
    verification=sealed(dict(plan_digest=plan['plan_digest'],result_digest=result['result_digest'],
        checked_artifacts=artifacts,recomputed_evaluations=evaluations,recomputed_candidate_attempts=attempts,
        identical_candidate_pool_pairs=pools,all_recorded_originals_executed_and_failed=True,
        recorded_output_grades_verified=True,frozen_machinery_hashes_verified=True,
        scope='posthoc recorded-output integrity check; not independent replication'), 'verification_digest')
    _write_new(directory/'VERIFICATION.json',verification)
    return verification


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    print(json.dumps(audit(parser.parse_args().directory),indent=2))
