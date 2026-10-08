#!/usr/bin/env python3
"""Verify durable repair replay without model calls under a separately sealed plan."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from genesis.adaptive_repair import EconomicRouter, ModelOption, RepairExperience, solve_development
from genesis.defects4j_sandbox import Defects4JSandbox
from genesis.repair_bench import validate
from genesis.trust_root import digest_of
from run_adaptive_repair import sealed
from run_adaptive_repair_trial import machinery, write_sealed


def hashes():
    return {**machinery(),'scripts/run_adaptive_repair_replays.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=Path,required=True)
    args=parser.parse_args();plan=sealed(args.plan,'plan_digest')
    if hashes()!=plan['machinery_sha256']:raise ValueError('machinery differs')
    original=sealed(Path(plan['source_result']),'result_digest')
    if original['result_digest']!=plan['source_result_digest']:raise ValueError('source result differs')
    store=RepairExperience(Path(plan['memory']))
    if digest_of(store.events())!=plan['initial_memory_digest']:raise ValueError('memory differs')
    sandbox=Defects4JSandbox(Path(plan['workspace']));probe=sandbox.probe()
    if not probe['isolated']:raise ValueError('sandbox boundary failed')
    options=[ModelOption(m['id'],float(m['pricing']['prompt'])*1e6*1.01,
                        float(m['pricing']['completion'])*1e6*1.01) for m in plan['catalog']]
    outcomes=[]
    for case in plan['cases']:
        source=next(o for o in original['outcomes'] if o['case']==case)
        if not source['result']['solved']:raise ValueError('source case has no suite-passing repair')
        expected=next(v['candidate_digest'] for v in source['result']['verdicts'] if v['plausible'] and v['stopped_at']=='passed')
        reopened=RepairExperience(store.path);router=EconomicRouter(options,reopened)
        directory=case+'-b';evidence=source['evidence']
        result=solve_development(sandbox.workspace/directory,evidence,router,
            lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
            role='released_development',allow_llm=False,validation_budget=2)
        candidate=result.pop('candidate')
        success=bool(candidate and candidate.digest==expected and result['reuse_without_llm'] and not result['model_calls'])
        outcomes.append(dict(case=case,result=result,expected_candidate_digest=expected,
                             observed_candidate_digest=candidate.digest if candidate else None,verified=success))
        print(case,'memory replay verified:',success,flush=True)
    events=RepairExperience(store.path).events()
    body=dict(schema='genesis-memory-only-replay-followup-v1',plan_digest=plan['plan_digest'],
        source_result_digest=original['result_digest'],outcomes=outcomes,
        all_verified=all(o['verified'] for o in outcomes),model_calls=0,known_cost_usd=0,
        final_memory_events=events,final_memory_digest=digest_of(events),sandbox_probe=probe,
        scope='released development same-case replay; not fresh transfer or general RSI')
    write_sealed(Path(plan['output']),body,'result_digest')


if __name__=='__main__':main()
