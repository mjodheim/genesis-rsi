#!/usr/bin/env python3
"""Import ONLY explicitly released, already published experiments as training.

Frozen independent evaluations remain pristine; no holdout is opened by this
script. Logs neither source, candidate text, human patches nor issue content.
Idempotent on exact candidate hashes and per-project case identities.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from genesis.failure_feedback import analyze_public_failures
from genesis.operator_outcome_memory import OperatorOutcomeMemory
from genesis.trust_root import digest_of

EXPERIMENT = ROOT/'experiment/g11/G11_3REPO_RESULTS_20261008.json'
FREEZE = Path('/home/anthony/benchmarks/g11-fresh-three-20261008/FROZEN_3REPO_CANDIDATES.json')
STATE = Path('/home/anthony/benchmarks/g11-trained-operators-v1/operator_events.sqlite')


def _load(file: Path, checksum: str) -> dict:
    data=json.loads(file.read_text())
    if data[checksum] != digest_of({k:v for k,v in data.items() if k!=checksum}):
        raise ValueError(f'experiment integrity mismatch: {file}')
    return data


def import_released(*, results:Path, freeze:Path, ledger: Path) -> dict:
    verified=_load(results,'result_digest')
    frozen=_load(freeze,'freeze_digest')
    if verified['freeze_digest'] != frozen['freeze_digest']:
        raise ValueError('result does not match frozen candidate index')
    if verified['preregistration_digest'] != frozen['preregistration_digest']:
        raise ValueError('result and preregistration disagree')
    # Only frozen/negative earlier three-project batch may enter by this
    # path. New future holdouts require an independent release decision.
    acceptable={('Math',53),('Csv',16),('Collections',24)}
    given={(x['project'],x['bug_id']) for x in verified['cases']}
    if given != acceptable:
        raise ValueError('cannot import an unreleased or unexpected holdout set')
    if verified.get('cases_solved_per_arm') != {
        'legacy_unchanged':0,
        'candidate_atomic_first_plus_source_balancing_plus_testname_hints':0,
    }:
        raise ValueError('released-results anchor mismatch')

    memory=OperatorOutcomeMemory(ledger)
    seen={(e['project'],e['case_digest'],e['candidate_sha256']) for e in memory.events()}
    case_frozen={(c['project'],c['bug_id']):c for c in frozen['all_cases']}
    imported=0
    skipped=0
    for case in verified['cases']:
        key=(case['project'],case['bug_id'])
        raw=case_frozen[key]
        if int(raw['failure_count_original']) < 1:
            raise ValueError('buggy baseline did not have a failing test')
        if not raw['buggy_root'].startswith('/home/anthony/benchmarks/g11-fresh-three-20261008/'):
            raise ValueError('unexpected experiment workspace')
        failures=Path(raw['buggy_root'])/'failing_tests'
        # Test feedback is PUBLIC already-exposed TRAINING data.
        summary=analyze_public_failures(failures.read_text())
        symptoms=sorted(set(x['symptom'] for x in summary['observations']))
        symptom=symptoms[0] if len(symptoms)==1 else 'multiple' if symptoms else 'unknown'
        case_digest=digest_of({'project':case['project'],
                               'bug_id':case['bug_id'],
                               'freeze_digest':frozen['freeze_digest']})
        candidate_index={}
        for arm in raw['arms'].values():
            for candidate in arm['top']:
                identifier=(candidate['path'],candidate['sha256'])
                if identifier in candidate_index:
                    if candidate_index[identifier]['operators'] != candidate['operators']:
                        raise ValueError('operators differ for duplicate candidate')
                candidate_index[identifier]=candidate
        for item in case['outcomes']:
            identifier=(item['path'],item['sha256'])
            if identifier not in candidate_index:
                raise ValueError('outcome not in frozen candidates')
            result=item['result']
            if result.get('full_suite_pass'):
                verdict='full_suite_passed'
            elif result.get('compiled') is False and result.get('error') == 'compile_failed':
                verdict='compile_failed'
            elif result.get('error')=='public_trigger_still_fails':
                verdict='public_trigger_failed'
            elif result.get('full_suite_ran') and result.get('full_suite_failures') is not None:
                verdict='full_suite_failed'
            else:
                skipped+=1
                continue
            row=(case['project'],case_digest,item['sha256'])
            if row in seen:
                skipped+=1
                continue
            operator_names=list(candidate_index[identifier]['operators'])
            memory.record(
                project=case['project'],
                case_digest=case_digest,
                candidate_sha256=item['sha256'],
                operators=operator_names,
                public_failure_symptom=symptom,
                outcome=verdict,
                freeze_digest=frozen['freeze_digest'],
                independent_evaluator_digest=verified['result_digest'],
                role='released_training',
            )
            seen.add(row)
            imported+=1
    evidence=memory.evidence_summary()
    report={
        'schema':'genesis-g11-training-release-import-v1',
        'source_evaluation_digest':verified['result_digest'],
        'source_freeze_digest':frozen['freeze_digest'],
        'released_projects':[list(x) for x in sorted(acceptable)],
        'event_imported_count':imported,
        'event_skipped_count':skipped,
        'operator_evidence':evidence['operator_evidence'],
        'operator_evidence_digest':evidence['summary_digest'],
        'independently_verified_automated_repairs':0,
        'future_holdouts_opened':False,
        'policy_automatically_changed':False,
    }
    return {**report,'report_digest':digest_of(report)}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release-training',action='store_true',required=True)
    parser.add_argument('--out',type=Path,default=ROOT/'experiment/g11/G11_RELEASED_TRAINING_SUMMARY_20261008.json')
    args=parser.parse_args()
    report=import_released(results=EXPERIMENT,freeze=FREEZE,ledger=STATE)
    args.out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print('TRAINING_IMPORT',report['event_imported_count'],
          'skipped',report['event_skipped_count'],
          'operator_families',len(report['operator_evidence']),
          'summary_digest',report['operator_evidence_digest'])


if __name__=='__main__':
    main()
