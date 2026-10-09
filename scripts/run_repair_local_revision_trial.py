#!/usr/bin/env python3
"""Frozen small paired development pilot; no held-out consumption or active promotion."""
import argparse,json,shutil,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_lineage import training_report
from genesis.repair_local_revision import changed_leaves,paired_summary,propose
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of
from scripts.run_real_repair_transfer import load_api_key
from scripts.run_repair_lineage import Journal,envelope_of,ledger_for,prepare,run_case,run_names


def plan(output,workspace):
    if output.exists() or workspace.exists():raise ValueError('fresh trial directories required')
    old=json.loads((ROOT/'experiment/bench/LINEAGE2/PLAN.json').read_text());checked(old,'plan_digest')
    lineage=json.loads((ROOT/'experiment/bench/LINEAGE2/LINEAGE.json').read_text())
    evaluation=json.loads((ROOT/'experiment/bench/LINEAGE2/GEN0_EVALUATION.json').read_text());checked(evaluation,'evaluation_digest')
    report=training_report(evaluation,run_names(old['training_cases'],old['replicates'],only_first=True))
    with urllib.request.urlopen('https://openrouter.ai/api/v1/models',timeout=30) as response:models=json.load(response)['data']
    model=next(m for m in models if m['id']==old['envelope']['model'])
    if float(model['pricing']['prompt'])*1e6>.2 or float(model['pricing']['completion'])*1e6>1:raise ValueError('approved tariff ceiling exceeded')
    diagnosis=[dict(generation=g['generation'],changed_leaves=changed_leaves(old['seed_genome'],g['genome']),outcome=g['child']) for g in lineage['generations']]
    files=sorted((ROOT/'genesis').glob('repair*.py'))+[ROOT/'genesis/openrouter_repair.py',ROOT/'genesis/defects4j_sandbox.py',ROOT/'scripts/run_repair_lineage.py',Path(__file__).resolve()]
    hashes={str(p.relative_to(ROOT)):digest_of(p.read_bytes().hex()) for p in files}
    output.mkdir(parents=True);workspace.mkdir(parents=True)
    for name in hashes:
        target=workspace/'snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    _write_new(output/'PLAN.json',sealed(dict(cases=old['selection_cases'][:3],selection='first three LINEAGE2 selection cases, previously exposed development',
        replicates=2,seed_genome=old['seed_genome'],training_report=report,training_case_runs=run_names(old['training_cases'],old['replicates'],only_first=True),
        envelope=old['envelope'],spending_ceiling_usd=.35,catalog=dict(id=model['id'],pricing=model['pricing']),
        workspace=str(workspace),machinery_digests=hashes,previous_revision_diagnosis=diagnosis,
        scope='small previously exposed development pilot; external-model configuration revision; no general RSI',
        order='alternate parent/child order across case index and replicate',separate_environment=True,
        proposal='exactly one allowed genome leaf; reject multi-leaf proposals with charges retained',
        promotion=False,held_out_consumed=False),'plan_digest'))
    print('Prepared',old['selection_cases'][:3],flush=True)


def execute(output):
    plan=json.loads((output/'PLAN.json').read_text());checked(plan,'plan_digest')
    for name,identity in plan['machinery_digests'].items():
        if digest_of((ROOT/name).read_bytes().hex())!=identity:raise ValueError('frozen machinery changed')
    workspace=Path(plan['workspace']);load_api_key();ledger=ledger_for(workspace,plan['spending_ceiling_usd']);envelope=envelope_of(plan)
    try:
        proposal_path=output/'PROPOSAL.json'
        if proposal_path.exists():proposal=json.loads(proposal_path.read_text());checked(proposal,'proposal_digest')
        else:
            proposal=propose(plan['seed_genome'],plan['training_report'],envelope,ledger)
            journal=Journal(workspace/'calls.jsonl',dict(label='local-successor'))
            for call in proposal['calls']:journal.append(call)
            _write_new(proposal_path,proposal)
        if not proposal['genome']:
            _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],proposal_digest=proposal['proposal_digest'],
                decision='no_valid_single_leaf_revision',rows=[],policy_promoted=False,held_out_consumed=False),'result_digest'));return
        rows=[]
        for case in plan['cases']:
            setup=prepare(workspace,case,True)
            if not setup['usable']:raise ValueError('unusable case: '+case+' '+setup['reason'])
        for replicate in range(1,plan['replicates']+1):
            for index,case in enumerate(plan['cases']):
                order=['parent','child'] if (replicate+index)%2 else ['child','parent'];arms={}
                for arm in order:
                    target=output/(case+f'.r{replicate}.{arm}.json')
                    if target.exists():arms[arm]=json.loads(target.read_text());checked(arms[arm],'arm_digest')
                    else:
                        genome=plan['seed_genome'] if arm=='parent' else proposal['genome']
                        result=run_case(workspace,case,genome,envelope,ledger,f'local-r{replicate}-{arm}')
                        arms[arm]=sealed(result,'arm_digest');_write_new(target,arms[arm])
                    print(case,replicate,arm,arms[arm]['solved'],'cost ledger',ledger.spent,flush=True)
                rows.append(dict(case=case,replicate=replicate,order=order,**arms))
        summary=paired_summary(rows)
        result=sealed(dict(plan_digest=plan['plan_digest'],proposal_digest=proposal['proposal_digest'],rows=rows,summary=summary,
            proposal_known_cost_usd=sum(c['cost_usd'] for c in proposal['calls'] if c.get('cost_usd') is not None),
            proposal_unknown_calls=sum(c.get('cost_usd') is None for c in proposal['calls']),
            decision='candidate_for_larger_test' if summary['warrants_larger_test'] else 'no_demonstrated_local_gain',
            policy_promoted=False,held_out_consumed=False),'result_digest')
        _write_new(output/'RESULT.json',result)
    except BaseException as error:
        if not (output/'ABORTED.json').exists():_write_new(output/'ABORTED.json',dict(error=type(error).__name__+': '+str(error),partial_arm_files=[p.name for p in output.glob('*.r*.json')]))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['plan','execute']);p.add_argument('--output',type=Path,required=True);p.add_argument('--workspace',type=Path)
    args=p.parse_args()
    if args.action=='plan':plan(args.output.resolve(),args.workspace.resolve())
    else:execute(args.output.resolve())
