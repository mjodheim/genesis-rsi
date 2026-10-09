#!/usr/bin/env python3
"""Read-only stored evidence audit; not independent execution replication."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.repair_contract_learning import acquire,validate_policy
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of


def audit(directory):
    plan=json.loads((directory/'PLAN.json').read_text());checked(plan,'plan_digest')
    result=json.loads((directory/'RESULT.json').read_text());checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest']:raise ValueError('plan mismatch')
    policy=validate_policy(plan['policy'])
    events=json.loads((ROOT/'experiment/bench/DEV_REPAIR_STALL_RECOVERY1/ADMITTED_MEMORY.json').read_text())['events']
    if digest_of(events)!=plan['initial_memory_digest'] or acquire(events)!=policy:raise ValueError('acquisition mismatch')
    if len(result['rows'])!=len(plan['fixtures']):raise ValueError('fixture count mismatch')
    positives=negatives=compiles=0
    for fixture,row in zip(plan['fixtures'],result['rows']):
        checked(row,'case_digest')
        if row['main']!=fixture['main'] or row['nullable']!=fixture['nullable'] or not row['source_restored']:raise ValueError('fixture identity or restoration mismatch')
        baseline=row['baseline'];checked(baseline,'verdict_digest');compiles+=1
        for verdict in row['verdicts']:
            checked(verdict,'verdict_digest');compiles+=1
        wrong=row['wrong_contract_verdict']
        if wrong:
            checked(wrong,'verdict_digest');compiles+=1
        if fixture['nullable']:
            passed=baseline['plausible'] and row['generated']==0 and not row['verdicts'] and wrong and not wrong['plausible'] and wrong['stopped_at']=='failing_tests'
            negatives+=bool(passed)
        else:
            passed=not baseline['plausible'] and baseline['stopped_at']=='failing_tests' and row['generated']==1 and len(row['verdicts'])==1 and row['verdicts'][0]['plausible'] and row['verdicts'][0]['stopped_at']=='passed'
            positives+=bool(passed)
        if bool(passed)!=row['passed']:raise ValueError('gate receipt mismatch')
    if positives!=result['positive_transfer_cases'] or negatives!=result['negative_controls_passed'] or result['all_gates_passed']!=(positives+negatives==len(result['rows'])):raise ValueError('summary mismatch')
    if result['external_model_calls'] or result['api_cost_usd'] or result['policy_promoted'] or result['canonical_memory_changed']:raise ValueError('scope exceeded')
    return sealed(dict(result_digest=result['result_digest'],positive_cases=positives,negative_cases=negatives,
        candidate_compilations=compiles,stored_evidence_consistent=True,independent_execution_replication=False),'verification_digest')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);print(json.dumps(audit(p.parse_args().directory),indent=2))
