#!/usr/bin/env python3
"""Authored executable transfer gates for contract-conditioned learned insertions."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import RepairExperience
from genesis.defects4j_sandbox import SandboxLimits
from genesis.g12_operator_lab import _write_new
from genesis.repair_bench import Candidate
from genesis.repair_contract_learning import acquire,generate
from genesis.repair_self_improvement import checked,sealed
from genesis.trust_root import digest_of
from scripts.run_real_repair_transfer import RecordingSandbox
from scripts.run_repair_transformation_trial import java_verdict


def source(index,nullable=False):
    classname=['Parcel','PairBox','MixedBox'][index]
    declaration=['Object payload','String label, Object value','int count, Object item'][index]
    required=[['payload'],['label','value'],['item']][index]
    normal=['new Object()','"hello", new Object()','7, new Object()'][index]
    nulls=[['null'],['null, new Object()','"hello", null'],['7, null']][index]
    fields='\n'.join('Object field'+str(n)+';' for n in range(len(required)))
    assignments=' '.join('this.field'+str(n)+' = '+name+';' for n,name in enumerate(required))
    checks=[]
    for args in nulls:
        if nullable:checks.append('new '+classname+'('+args+');')
        else:checks.append('try { new '+classname+'('+args+'); throw new AssertionError("missing rejection"); } catch (NullPointerException expected) {}')
    return classname,required,f'''class {classname} {{
 {fields}
 public {classname}({declaration}) {{ {assignments} }}
 public static void main(String[] args) {{
  {classname} good = new {classname}({normal});
  if (good.field0 == null) throw new AssertionError("nonnull regression");
  {' '.join(checks)}
 }}
}}'''


def run(output,workspace):
    if output.exists() or workspace.exists():raise ValueError('fresh trial directories required')
    pointer=json.loads((ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text());checked(pointer,'pointer_digest')
    events=RepairExperience(Path(pointer['path'])).events()
    if digest_of(events)!=pointer['memory_digest']:raise ValueError('memory mismatch')
    policy=acquire(events)
    image='sha256:f047b3d0af5908396077f6f1635891e396cf2e73b4625e1a9f4064c3739b656c'
    output.mkdir(parents=True);workspace.mkdir(parents=True)
    fixtures=[dict(index=i,nullable=control,main=source(i,control)[0],parameters=source(i,control)[1],source=source(i,control)[2]) for i in range(3) for control in (False,True)]
    plan=sealed(dict(scope='authored Java transfer gates; not fresh real bugs or independent RSI evidence',
        policy=policy,fixtures=fixtures,image=image,workspace=str(workspace),external_model_calls=0,api_cost_usd=0,
        validation_budget_per_fixture=1,negative_controls='nullable contract has no proposal; wrong supplied contract must fail execution',
        contract_source='explicit authored caller contract; no semantic inference',
        machinery={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [ROOT/'genesis/repair_contract_learning.py',Path(__file__).resolve()]},
        initial_memory_digest=digest_of(events),promotion=False), 'plan_digest')
    _write_new(output/'PLAN.json',plan)
    sandbox=RecordingSandbox(workspace,image=image,limits=SandboxLimits(timeout_seconds=30))
    if not sandbox.probe()['isolated']:raise ValueError('isolation failed')
    rows=[]
    for fixture in fixtures:
        main=fixture['main'];directory=main+('-nullable' if fixture['nullable'] else '-nonnull')
        root=workspace/directory;(root/'src').mkdir(parents=True);(root/'classes').mkdir()
        path='src/'+main+'.java';(root/path).write_text(fixture['source'])
        evidence=dict(source_directory='src')
        baseline=java_verdict(sandbox,directory,Candidate(path,fixture['source'],'baseline'),main)
        contract={} if fixture['nullable'] else {path:{main:fixture['parameters']}}
        candidates=generate(root,evidence,policy,contract)
        verdicts=[java_verdict(sandbox,directory,c,main) for c in candidates[:1]]
        wrong=None
        if fixture['nullable']:
            false_candidates=generate(root,evidence,policy,{path:{main:fixture['parameters']}})
            if false_candidates:wrong=java_verdict(sandbox,directory,false_candidates[0],main)
        passed=(baseline['plausible'] and not candidates and wrong and not wrong['plausible']) if fixture['nullable'] else (not baseline['plausible'] and baseline['stopped_at']!='compile' and len(candidates)==1 and verdicts[0]['plausible'])
        row=sealed(dict(main=main,nullable=fixture['nullable'],baseline=baseline,generated=len(candidates),
            verdicts=verdicts,wrong_contract_verdict=wrong,passed=bool(passed),source_restored=(root/path).read_text()==fixture['source']), 'case_digest')
        rows.append(row);_write_new(output/(directory+'.RESULT.json'),row)
        print(directory,'passed',bool(passed),flush=True)
    result=sealed(dict(plan_digest=plan['plan_digest'],rows=rows,all_gates_passed=all(r['passed'] and r['source_restored'] for r in rows),
        positive_transfer_cases=sum(not r['nullable'] and r['passed'] for r in rows),
        negative_controls_passed=sum(r['nullable'] and r['passed'] for r in rows),
        external_model_calls=0,api_cost_usd=0,policy_promoted=False,canonical_memory_changed=False,
        scope=plan['scope']), 'result_digest')
    _write_new(output/'RESULT.json',result)
    if not result['all_gates_passed']:raise ValueError('gate failed; preserve negative evidence')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--workspace',type=Path,required=True)
    args=p.parse_args();run(args.output.resolve(),args.workspace.resolve())
