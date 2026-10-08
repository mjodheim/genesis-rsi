#!/usr/bin/env python3
"""Audit evidence gates without equating patch plausibility with general RSI.

This is an intentionally conservative readiness contract. Passing finite
benchmarks alone does not establish general recursive self-improvement, so
human-authored capabilities never satisfy autonomous operator discovery.
No user's server credential or hidden tests are used.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis.trust_root import digest_of

BASE=ROOT/'experiment/g11'
BATCHES=[
    ('first_independent_three','G11_3REPO_RESULTS_20261008.json',
     'G11_3REPO_PREREG_20261008.json'),
    ('second_independent_three','G11_SECOND_BATCH_RESULTS_20261008.json',
     'G11_SECOND_BATCH_PREREG_20261008.json'),
    ('third_independent_three','G11_THIRD_BATCH_RESULTS_20261008.json',
     'G11_THIRD_BATCH_PREREG_20261008.json'),
]


def _read_checked(file:Path,key:str):
    if not file.is_file():return None
    item=json.loads(file.read_text())
    if item[key]!=digest_of({k:v for k,v in item.items() if k!=key}):
        raise ValueError(f'integrity failure: {file}')
    return item


def audit() -> dict:
    cases=[]
    records=[]
    missing=[]
    for title,name,prereg in BATCHES:
        manifest=_read_checked(BASE/prereg,'preregistration_digest')
        result=_read_checked(BASE/name,'result_digest')
        if not manifest:
            missing.append(prereg)
            continue
        if result is None:
            missing.append(name)
            continue
        if result['preregistration_digest']!=manifest['preregistration_digest']:
            raise ValueError('mismatched independent preregistration')
        if not result.get('no_fixed_revision_or_human_solution',False):
            raise ValueError('human solution source accidentally accessible')
        runs=[]
        for row in result['cases']:
            candidate_arms=list(row['arms'].items())
            runs.append({
                'project':row['project'],
                'case_id':row['bug_id'],
                'arm_successes':{
                    arm:bool(v['first_passing_rank'] is not None)
                    for arm,v in candidate_arms
                },
                'full_suite_valid_distinct_candidates':row['full_suite_valid_unique_candidates'],
            })
            cases.append((row['project'],row['bug_id']))
        records.append({'name':title,'case_count':len(runs),'case_results':runs,
            'evaluation_digest':result['result_digest'],
            'freeze_digest':result['freeze_digest']})
    independent_case_count=len(cases)
    if len(set(cases))!=independent_case_count:
        raise ValueError('duplicate case counted multiple times as independent')
    if any(b['case_count']<1 for b in records):
        raise ValueError('empty batch')
    validated=sum(
        max(int(value) for value in row['arm_successes'].values())
        for batch in records for row in batch['case_results']
    )
    projects_with_success=set(
        row['project']
        for batch in records for row in batch['case_results']
        if any(row['arm_successes'].values())
    )
    # Hard gates, not heuristic guesses from product labels.
    thresholds={
        'independent_full_suite_repairs_at_least_five':validated>=5,
        'success_across_at_least_three_projects':len(projects_with_success)>=3,
        'minimum_ten_pre_registered_untouched_cases':independent_case_count>=10,
        'independent_batched_evaluations_at_least_three':len(records)>=3,
        # No operator authored by a human, copied from a published fix, or
        # inferred from an already exposed case can count here.
        'genesis_self_generated_and_independently_validated_new_operator':False,
        'multiple_recursive_improvement_generations_proven':False,
        'independent_equal_budget_baseline_improvement_proven':False,
        'sandboxed_unattended_campaign_verified':False,
    }
    summary={
        'schema':'genesis-rsi-scientific-readiness-gates-v1',
        'candidate_counted_independent_cases':independent_case_count,
        'full_suite_successful_distinct_independent_cases':validated,
        'successful_distinct_projects':len(projects_with_success),
        'batches_evaluated':len(records),
        'batches':records,
        'missing_studies':missing,
        'gates':thresholds,
        'fully_operational_rsi_scientifically_demonstrated':all(thresholds.values()),
        'status':'not_proven' if not all(thresholds.values()) else 'requires_external_replication',
        'posthoc_development_repairs_do_not_count':True,
        'human_operator_inventions_do_not_count':True,
        'patch_overfitting_not_ruled_out_by_visible_test_suites':True,
    }
    return {**summary,'audit_digest':digest_of(summary)}

if __name__=='__main__':
    output=ROOT/'experiment/g11/RSI_READINESS_20261008.json'
    state=audit()
    output.write_text(json.dumps(state,indent=2,sort_keys=True)+'\n')
    print('RSI_READINESS',state['fully_operational_rsi_scientifically_demonstrated'],
          'cases',state['candidate_counted_independent_cases'],
          'full_suite_successes',state['full_suite_successful_distinct_independent_cases'],
          'independently_tested_batches',state['batches_evaluated'],
          'pending',state['missing_studies'])
