#!/usr/bin/env python3
"""Prospective lexical-learning development gates and three real transfer trials."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from genesis.adaptive_repair import RepairExperience
from genesis.g12_operator_lab import _write_new
from genesis.repair_bench import collect_evidence, validate
from genesis.repair_proposers import strategist_proposer
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_transformation_learning import acquire,generate,search
from genesis.trust_root import digest_of
from scripts.run_real_repair_transfer import RecordingSandbox,candidate_record
from genesis.defects4j_sandbox import SandboxLimits


def machinery():
    files=sorted((ROOT/'genesis').rglob('*.py'))+[Path(__file__).resolve()]
    files += [ROOT/'scripts/run_real_repair_transfer.py',ROOT/'scripts/audit_repair_transformation_trial.py']
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def exposures(split):
    """Conservative census of already public DEVELOPMENT results, not held-out data."""
    exposed=set(split['exposed_cases']);evidence={}
    for path in sorted((ROOT/'experiment/bench').rglob('*RESULT.json')):
        if 'DEV' not in str(path.relative_to(ROOT/'experiment/bench')):continue
        cases=sorted(set(re.findall(r'\b(Jsoup-\d+|Math-\d+|Compress-\d+)\b',path.read_text())))
        if cases: exposed.update(cases);evidence[str(path.relative_to(ROOT))]=cases
    return exposed,evidence


def prepare(output,workspace):
    if output.exists() or workspace.exists():raise ValueError('fresh output and workspace required')
    split=json.loads((ROOT/'experiment/bench/REPAIR_BENCH_SPLIT_V1.json').read_text());checked(split,'split_digest')
    exposed,census=exposures(split)
    cases=[next(c for c in split['development'] if c.startswith(p+'-') and c not in exposed)
           for p in ['Jsoup','Math','Compress']]
    pointer=json.loads((ROOT/'experiment/bench/ADAPTIVE_REPAIR_ACTIVE_MEMORY.json').read_text());checked(pointer,'pointer_digest')
    events=RepairExperience(Path(pointer['path'])).events()
    if digest_of(events)!=pointer['memory_digest']:raise ValueError('canonical memory mismatch')
    generations=[];parent=None
    # Genesis's extractor chooses which recorded successes add an executable rule.
    # Every acquisition remains attributed; selection gates are externally owned.
    for index,event in enumerate(events):
        if event['kind']!='recipe':continue
        child=acquire(events[:index+1],parent)
        if parent is None and not child['rules']:continue
        if parent is not None and len(child['rules'])==len(parent['rules']):continue
        generations.append(child);parent=child
    if parent is None:raise ValueError('no reusable transformation extracted')
    image=subprocess.check_output(['docker','image','inspect','genesis-defects4j:8c16da8','--format','{{.Id}}'],text=True).strip()
    workspace.mkdir(parents=True);output.mkdir(parents=True)
    memory=workspace/'experience.sqlite'
    with sqlite3.connect(pointer['path']) as db,sqlite3.connect(memory) as copy:db.backup(copy)
    plan=sealed(dict(schema='genesis-repair-transformation-trial-development-v1',cases=cases,
        selection='first remaining public development case per Jsoup/Math/Compress in frozen split order',
        exposure_census=census,excluded_cases=sorted(exposed),split_digest=split['split_digest'],
        initial_memory=events,initial_memory_digest=digest_of(events),memory=str(memory),
        source_pointer_digest=pointer['pointer_digest'],generations=generations,child_policy=parent,
        image=image,workspace=str(workspace.resolve()),machinery=machinery(),
        validation_budget=8,local_pool_budget=32,command_timeout_seconds=180,
        parent='exact experience plus existing strategist; fixed order',
        child='same exact experience and strategist plus extracted lexical transformations and own-outcome feedback',
        selection_gate='authored renamed/layout Java positives and behavioural counterexamples; not independent transfer',
        real_gate='strict solved-case gain at equal validation ceilings; no solved-case regression; nonincreasing aggregate validations',
        no_llm_during_transfer=True,assisted_training_after_transfer=False,
        scope='public real Java DEVELOPMENT; no independent/blind generality or general RSI claim',
        fixed_revision_consulted=False,plausible_is_not_correct=True),'plan_digest')
    _write_new(output/'PLAN.json',plan)
    snapshot=workspace/'machinery-snapshot'
    for name in plan['machinery']:
        dest=snapshot/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((ROOT/name).read_bytes())
    print('Prepared',cases,'generations',len(generations),'rules',len(parent['rules']),flush=True)


def exercise_source(family,control,variant):
    """Authored fixtures test this substrate, never count as real RSI evidence."""
    name='bytes' if variant==1 else 'payload';size='minimum' if variant==1 else 'threshold'
    if family=='relational_change':
        check='!check(new byte[5],3)' if control else 'check(new byte[5],3)'
        return 'Example',f'''class Example {{
 static boolean check(byte[] {name}, int {size}) {{
  if ({name}.length != {size}) {{ return false; }} return true;
 }}
 public static void main(String[] args) {{
  if (!({check} && !check(new byte[2],3) && check(new byte[3],3))) throw new AssertionError("length contract");
 }}
}}'''
    if family=='call_structure_change':
        expected='a  b' if control else 'a b';variable='node' if variant==1 else 'element'
        return 'Example',f'''class Example {{
 static class Element {{ String text() {{ return " a  b "; }} }}
 static class TextNode {{ static String normaliseWhitespace(String s) {{ return s.replaceAll("\\\\s+", " "); }} }}
 static String check(Element {variable}) {{
  return {variable} != null ? {variable}.text().trim() : "";
 }}
 public static void main(String[] args) {{
  if (!check(new Element()).equals("{expected}") || !check(null).equals("")) throw new AssertionError("whitespace contract");
 }}
}}'''
    if family=='expression_change':
        variable='record' if variant==1 else 'nextRecord'
        expected='value.value == 99 && parser.current != null' if control else 'value.value == 7 && parser.current == null'
        return 'CSVParser',f'''class CSVParser {{
 static class CSVRecord {{ final int value; CSVRecord(int value) {{ this.value=value; }} }}
 CSVRecord current=new CSVRecord(7);
 class Iter {{
  CSVRecord current=new CSVRecord(99);
  CSVRecord next() {{
   CSVRecord {variable} = this.current;
   this.current = null;
   return {variable};
  }}
 }}
 public static void main(String[] args) {{
  CSVParser parser=new CSVParser(); CSVRecord value=parser.new Iter().next();
  if (!({expected})) throw new AssertionError("owner contract");
 }}
}}'''
    raise ValueError('unsupported authored gate family')


def java_verdict(sandbox,directory,candidate,main):
    target=sandbox.workspace/directory/candidate.path;original=target.read_bytes()
    try:
        target.write_text(candidate.content)
        compiled=sandbox.execute(['javac','-d','/work/'+directory+'/classes','/work/'+directory+'/'+candidate.path])
        run=sandbox.execute(['java','-cp','/work/'+directory+'/classes',main]) if compiled.ok else None
        stage='passed' if run and run.ok else ('compile' if not compiled.ok else 'failing_tests')
        return sealed(dict(candidate_digest=candidate.digest,plausible=stage=='passed',stopped_at=stage,
            feedback=(run.output if run else compiled.output)[:1500],compile_run=compiled.record(),
            test_run=run.record() if run else None),'verdict_digest')
    finally:target.write_bytes(original)


def selection_gate(plan,output,sandbox):
    rows=[]
    families=sorted({r['family'] for r in plan['child_policy']['rules']})
    for generation,policy in enumerate(plan['generations'],1):
        tests=[]
        for family in families:
            active=any(r['family']==family for r in policy['rules'])
            for control in (False,True):
                for variant in (1,2):
                    main,text=exercise_source(family,control,variant)
                    # Formatting varies without introducing oracle-derived edits.
                    if variant==2:text=text.replace('.length', ' . length').replace(' != ', '\n != ')
                    directory=f'gate-g{generation}-{family}-c{int(control)}-v{variant}'
                    root=sandbox.workspace/directory;(root/'src').mkdir(parents=True);(root/'classes').mkdir()
                    path='src/'+main+'.java';(root/path).write_text(text)
                    evidence=dict(source_directory='src',suspect_locations=[(path,n+1) for n,line in enumerate(text.splitlines()) if '!=' in line or 'this.current' in line])
                    from genesis.repair_bench import Candidate
                    baseline=java_verdict(sandbox,directory,Candidate(path,text,'baseline'),main)
                    if baseline['stopped_at']=='compile':raise ValueError('authored baseline failed compilation')
                    candidates=generate(root,evidence,policy)
                    attempts=[dict(candidate=candidate_record(c),verdict=java_verdict(sandbox,directory,c,main)) for c in candidates[:4]]
                    passed=any(a['verdict']['plausible'] for a in attempts)
                    expected=(not control and active)
                    if baseline['plausible']!=control or passed!=expected:raise ValueError('authored transfer/control gate failed')
                    tests.append(dict(family=family,control=control,variant=variant,baseline=baseline,
                        source_digest=digest_of(text),attempts=attempts,expected_candidate_success=expected,
                        solved=passed,source_restored=(root/path).read_text()==text))
        row=sealed(dict(generation=generation,policy_digest=policy['policy_digest'],tests=tests,
            positives_solved=sum(t['solved'] for t in tests if not t['control']),
            negative_controls_accepted=sum(t['solved'] for t in tests if t['control']),
            scope='authored substrate gate; semantic counterexamples reject plausible-looking edits'),'gate_digest')
        rows.append(row);_write_new(output/f'GENERATION{generation}.GATE.json',row)
        print('Generation',generation,'positive transfers',row['positives_solved'],'negative controls accepted',row['negative_controls_accepted'],flush=True)
    return rows


def execute(output):
    plan=json.loads((output/'PLAN.json').read_text());checked(plan,'plan_digest')
    if plan['machinery']!=machinery():raise ValueError('frozen machinery changed')
    if (output/'STARTED.json').exists():raise ValueError('one-shot run already started; preserve prior record')
    store=RepairExperience(Path(plan['memory']))
    if digest_of(store.events())!=plan['initial_memory_digest']:raise ValueError('initial memory mismatch')
    _write_new(output/'STARTED.json',dict(plan_digest=plan['plan_digest']))
    sandbox=RecordingSandbox(Path(plan['workspace']),image=plan['image'],limits=SandboxLimits(timeout_seconds=plan['command_timeout_seconds']))
    outcomes=[];gates=[]
    try:
        probe=sandbox.probe();_write_new(output/'SANDBOX_PROBE.json',probe)
        if not probe['isolated']:raise ValueError('isolation failure')
        gates=selection_gate(plan,output,sandbox)
        _write_new(output/'SELECTION.json',sealed(dict(gates=[g['gate_digest'] for g in gates],
            selected_policy_digest=plan['child_policy']['policy_digest'],passed=True,
            scope='authored development selection only; real-world gate still required'),'selection_digest'))
        for case in plan['cases']:
            directory=case+'-b';project,bug=case.rsplit('-',1)
            if (sandbox.workspace/directory).exists():raise ValueError('fresh buggy checkout required')
            if not sandbox.checkout(project,int(bug),'b',directory).ok:raise ValueError('checkout failure '+case)
            root=sandbox.workspace/directory;evidence=collect_evidence(sandbox,directory)
            _write_new(output/(case+'.EVIDENCE.json'),evidence)
            local=list(strategist_proposer(plan['local_pool_budget'])(root,evidence,(),plan['local_pool_budget']))
            exact=list(store.candidates(root,evidence,2));learned=generate(root,evidence,plan['child_policy'])
            _write_new(output/(case+'.POOL.json'),sealed(dict(case=case,evidence_digest=evidence['evidence_digest'],
                exact=[candidate_record(c) for c in exact],learned=[candidate_record(c) for c in learned],
                local=[candidate_record(c) for c in local]),'pool_digest'))
            arms={};accepted={}
            for arm in ('parent','child'):
                counts={'choice':0,'attempt':0};started=time.monotonic()
                def record(kind,data):
                    counts[kind]+=1
                    _write_new(output/(case+'.'+arm+f'.{kind.upper()}{counts[kind]}.json'),data)
                result=search(root,evidence,plan['child_policy'] if arm=='child' else None,store,local,
                    lambda c:validate(sandbox,directory,c,evidence['failing_tests']),
                    budget=plan['validation_budget'],reactive=arm=='child',record=record)
                accepted[arm]=result.pop('accepted');result['seconds']=time.monotonic()-started
                arms[arm]=sealed(dict(case=case,arm=arm,**result),'arm_digest')
                _write_new(output/(case+'.'+arm+'.ARM.json'),arms[arm])
                print(case,arm,'solved',result['solved'],'validations',result['validated'],'learned candidates',result['learned_candidates'],flush=True)
            outcomes.append(dict(case=case,evidence_digest=evidence['evidence_digest'],arms=arms,
                accepted_candidate_digest={a:c.digest if c else None for a,c in accepted.items()}))
            _write_new(output/(case+'.COMPARISON.json'),sealed(outcomes[-1],'comparison_digest'))
        gains=[r['case'] for r in outcomes if r['arms']['child']['solved'] and not r['arms']['parent']['solved']]
        regressions=[r['case'] for r in outcomes if r['arms']['parent']['solved'] and not r['arms']['child']['solved']]
        parent_validations=sum(r['arms']['parent']['validated'] for r in outcomes)
        child_validations=sum(r['arms']['child']['validated'] for r in outcomes)
        decision=sealed(dict(gains=gains,regressions=regressions,
            parent_validations=parent_validations,child_validations=child_validations,
            promoted=bool(gains) and not regressions and child_validations<=parent_validations,
            rule=plan['real_gate'],policy_digest=plan['child_policy']['policy_digest']),'decision_digest')
        _write_new(output/'DECISION.json',decision)
        # Only after all comparisons may successful repairs teach future invocations.
        for row in outcomes:
            case=row['case'];directory=case+'-b';root=sandbox.workspace/directory
            evidence=json.loads((output/(case+'.EVIDENCE.json')).read_text())
            local=list(strategist_proposer(plan['local_pool_budget'])(root,evidence,(),plan['local_pool_budget']))
            all_candidates=list(store.candidates(root,evidence,2))+generate(root,evidence,plan['child_policy'])+local
            by_digest={c.digest:c for c in all_candidates}
            identity=row['accepted_candidate_digest']['child'] or row['accepted_candidate_digest']['parent']
            row['success_recorded']=False;row['replay_verified']=False
            if identity:
                candidate=by_digest[identity]
                verdict=next(s['verdict'] for arm in row['arms'].values() for s in arm['steps'] if s['verdict']['candidate_digest']==identity and s['verdict']['plausible'])
                store.retain(root,evidence,candidate,verdict,role='released_development')
                proposal=acquire(store.events(),plan['child_policy'])
                store.append('transformation_proposal',dict(policy=proposal,source_case=case,promoted=False))
                fresh=RepairExperience(store.path)
                repeats=fresh.candidates(root,evidence,2)
                repeated=next(c for c in repeats if c.digest==identity)
                replay=validate(sandbox,directory,repeated,evidence['failing_tests'])
                row['success_recorded']=True;row['replay_verified']=replay['plausible'];row['replay']=replay
                if not row['replay_verified']:raise ValueError('durable full-suite replay failed')
            _write_new(output/(case+'.RETENTION.json'),sealed(row,'retention_digest'))
        # No-success runs still retain search failures and proposed capabilities in the clone.
        for row in outcomes:
            for arm in row['arms'].values():
                for step in arm['steps']:store.append('transformation_validation',dict(case=row['case'],arm=arm['arm'],**step))
        store.append('transformation_trial',dict(policy=plan['child_policy'],decision=decision,
            selection_gate_digests=[g['gate_digest'] for g in gates],source_trial=output.name))
        final=store.events()
        summary=dict(cases=len(outcomes),parent_solved=sum(r['arms']['parent']['solved'] for r in outcomes),
            child_solved=sum(r['arms']['child']['solved'] for r in outcomes),
            parent_validations=parent_validations,child_validations=child_validations,
            successes_recorded=sum(r['success_recorded'] for r in outcomes),verified_replays=sum(r['replay_verified'] for r in outcomes),
            acquired_rules=len(plan['child_policy']['rules']),acquisition_generations=len(plan['generations']),
            policy_promoted=decision['promoted'],external_model_calls=0,api_cost_usd=0,
            general_rsi_demonstrated=False,final_memory_events=len(final))
        _write_new(output/'RESULT.json',sealed(dict(plan_digest=plan['plan_digest'],outcomes=outcomes,gates=gates,
            decision=decision,summary=summary,final_memory_events=final,final_memory_digest=digest_of(final),
            scope=plan['scope']),'result_digest'))
        print(json.dumps(summary,indent=2),flush=True)
    except Exception as error:
        _write_new(output/'ABORTED.json',sealed(dict(plan_digest=plan['plan_digest'],error_type=type(error).__name__,
            error=str(error)[:500],outcomes=outcomes,gates=gates,final_memory_events=store.events()),'abort_digest'))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--workspace',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        if not args.workspace:parser.error('--workspace required')
        prepare(args.output.resolve(),args.workspace.resolve())
    else:execute(args.output.resolve())
