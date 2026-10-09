#!/usr/bin/env python3
"""Freeze and execute a model-free, authored multilingual development experiment.

Candidates never receive expected answers. The host grades container outputs.
No reserved benchmarks or real-project generality claims are involved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from genesis import exemplar_strategy
from genesis.g12_operator_lab import _write_new
from genesis.multilingual_repair_sandbox import run_task
from genesis.repair_self_improvement import (checked, decide_promotion, propose,
                                            propose_descendant, sealed, seed_policy, validate_policy)
from genesis.trust_root import digest_of

LANGUAGES = ('python', 'javascript', 'java')
BAGS = [[11, 23, 41, 59, 71, 89, 101, 127], [8, 7, 6, 5, 4, 3, 2, 1],
        [-13, 2, -47, 31, 0, 19, -8, 63]]
SLOTS = [2, 3, 4]
MACHINERY = ['scripts/run_repair_self_improvement.py', 'genesis/repair_self_improvement.py',
             'genesis/multilingual_repair_sandbox.py', 'genesis/exemplar_strategy.py',
             'genesis/g12_operator_lab.py', 'genesis/trust_root.py']


def snapshot():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in MACHINERY}


def authored_task(task_id, language, delta, role, *, exemplar=False, renamed=False):
    identifier = 'position' if renamed else 'slot'
    expression = f'{identifier} {"+" if delta > 0 else "-"} {abs(delta)}'
    if language == 'python':
        name = 'src/subject.py'
        source = f'def pick(values, {identifier}):\n    return values[{identifier}]\n'
        if exemplar:
            source += f'\ndef neighboring(values, {identifier}):\n    return values[{expression}]\n'
        runner_name = 'runner.py'
        runner = ('import json, sys\nsys.path.insert(0, "/task/src")\nfrom subject import pick\n'
                  f'bags = {BAGS!r}\nslots = {SLOTS!r}\n'
                  'print(json.dumps([pick(values, position) for values in bags for position in slots]))\n')
    elif language == 'javascript':
        name = 'src/subject.js'
        source = f'function pick(values, {identifier}) {{ return values[{identifier}]; }}\n'
        if exemplar:
            source += f'function neighboring(values, {identifier}) {{ return values[{expression}]; }}\n'
        source += 'module.exports = {pick};\n'
        runner_name = 'runner.js'
        runner = ('const {pick} = require("/task/src/subject.js");\n'
                  f'const bags = {json.dumps(BAGS)}, slots = {json.dumps(SLOTS)};\n'
                  'console.log(JSON.stringify(bags.flatMap(values => slots.map(position => pick(values, position)))));\n')
    else:
        name = 'src/Subject.java'
        source = f'public class Subject {{\n public static int pick(int[] values, int {identifier}) {{ return values[{identifier}]; }}\n'
        if exemplar:
            source += f' public static int neighboring(int[] values, int {identifier}) {{ return values[{expression}]; }}\n'
        source += '}\n'
        runner_name = 'Runner.java'
        java_bags = '{' + ','.join('{' + ','.join(map(str, bag)) + '}' for bag in BAGS) + '}'
        runner = ('public class Runner { public static void main(String[] args) {\n'
                  f'int[][] bags = {java_bags}; int[] slots = {{2,3,4}};\n'
                  'System.out.print("["); boolean first=true;\n'
                  'for(int[] values: bags) for(int position: slots) {\n'
                  'if(!first) System.out.print(","); first=false; System.out.print(Subject.pick(values,position)); }\n'
                  'System.out.println("]"); }}\n')
    return sealed(dict(task_id=task_id, language=language, role=role,
        source_path=name, source=source, runner_path=runner_name, runner=runner,
        expected=[values[position+delta] for values in BAGS for position in SLOTS],
        provenance='project-authored exercise; not a real-world or independent benchmark',
        family='subscript offset; authored primitive with discovered parameter'), 'task_digest')


def prepare(output: Path, workspace: Path, image_tag: str):
    output.mkdir(parents=True, exist_ok=True); workspace.mkdir(parents=True, exist_ok=True)
    image = subprocess.check_output(['docker', 'image', 'inspect', image_tag, '--format', '{{.Id}}'], text=True).strip()
    tasks = []; cycles = []
    # The entire task set, including final transfer probes, is fixed before any run.
    for index, (language, delta) in enumerate(zip(LANGUAGES, [-1, 1, -2]), 1):
        training = authored_task(f'train-{index}', language, delta, 'released_training', exemplar=True)
        tasks.append(training)
        gates = []
        for previous in range(1, index+1):
            for target in LANGUAGES:
                task = authored_task(f'gate-{index}-{previous}-{target}', target,
                    [-1, 1, -2][previous-1], 'promotion', renamed=True)
                tasks.append(task); gates.append(task['task_id'])
        cycles.append(dict(training_task=training['task_id'], promotion_tasks=gates))
    finals = []
    for index, delta in enumerate([-1, 1, -2], 1):
        for language in LANGUAGES:
            task = authored_task(f'final-{index}-{language}', language, delta, 'final_evaluation', renamed=True)
            # Source differs from the promotion task, beyond its task identity.
            prefix = '# transfer probe\n' if language == 'python' else '// transfer probe\n'
            task['source'] = prefix + task['source']
            task = sealed({k:v for k,v in task.items() if k != 'task_digest'}, 'task_digest')
            tasks.append(task); finals.append(task['task_id'])
    protocol = sealed(dict(schema='genesis-repair-self-improvement-development-plan-v1',
        image=image, workspace=str(workspace.resolve()), machinery=snapshot(), tasks=tasks,
        cycles=cycles, final_tasks=finals, candidate_budget=4, external_model_calls=0,
        api_budget_usd=0, scope='authored development exercises; not independent general RSI evidence',
        promotion='strict gain, no regression; training and promotion task IDs disjoint',
        final_evaluation_learning=False, initial_policy=seed_policy()), 'plan_digest')
    _write_new(output/'PLAN.json', protocol)
    print('Prepared', output/'PLAN.json', flush=True)


def write_task(directory: Path, task: dict, content=None):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'src').mkdir()
    (directory/task['source_path']).write_text(task['source'] if content is None else content)
    (directory/task['runner_path']).write_text(task['runner'])


def evaluate(task, policy, plan, output, *, discover=False):
    validate_policy(policy); checked(task, 'task_digest')
    work = Path(plan['workspace'])
    with tempfile.TemporaryDirectory(prefix='source-', dir=work) as temporary:
        directory = Path(temporary); write_task(directory, task)
        # The generator sees only src/, never runner, test vectors or expected output.
        candidates = propose(directory/'src', policy, discover=discover, budget=plan['candidate_budget'])
        frozen = sealed(dict(task_digest=task['task_digest'], policy_digest=policy['policy_digest'],
            discover=discover, candidates=candidates, source_digest=digest_of(task['source'])), 'search_digest')
        key = task['task_id']+'-'+policy['policy_digest'][:12]+('-training' if discover else '')
        _write_new(output/(key+'.SEARCH.json'), frozen)
        attempts = []; winner = None; receipt = None
        # Establish that the original really fails the host's tests; infrastructure errors abort.
        baseline = run_task(directory, task['language'], plan['image'])
        original = grade(baseline, task)
        if original['passed']:
            raise ValueError('task is not initially buggy')
        if original['infrastructure_error']:
            raise RuntimeError('original task executor failed: '+baseline['stderr'][:300])
        for candidate in candidates:
            mutation = candidate['mutations']
            if (len(mutation) != 1 or mutation[0]['path'] != Path(task['source_path']).name
                or mutation[0]['expected_sha256'] != hashlib.sha256(task['source'].encode()).hexdigest()):
                raise ValueError('candidate must change only the frozen production source')
            with tempfile.TemporaryDirectory(prefix='attempt-', dir=work) as temporary_attempt:
                attempt_dir = Path(temporary_attempt)
                write_task(attempt_dir, task, mutation[0]['content_utf8'])
                run = run_task(attempt_dir, task['language'], plan['image'])
                grading = grade(run, task)
                receipt = sealed(dict(task_id=task['task_id'], role=task['role'],
                    task_digest=task['task_digest'], candidate_digest=candidate['candidate_digest'],
                    passed=grading['passed'], host_graded=True, returncode=run['returncode'],
                    timed_out=run['timed_out'], run=run, grading=grading), 'receipt_digest')
                attempts.append(receipt)
                # Persist each attempt before trying another candidate.
                _write_new(output/(key+f'.ATTEMPT{len(attempts)}.json'), receipt)
                if grading['infrastructure_error']:
                    raise RuntimeError('candidate executor infrastructure error')
                if grading['passed']:
                    winner=candidate; break
        result = sealed(dict(task_id=task['task_id'], task_digest=task['task_digest'], role=task['role'],
            policy_digest=policy['policy_digest'], candidate_budget=plan['candidate_budget'],
            passed=winner is not None, attempt_count=len(attempts), attempts=attempts,
            baseline_run=baseline, baseline_grade=original, search_digest=frozen['search_digest'],
            external_model_calls=0, known_api_cost_usd=0), 'evaluation_digest')
        _write_new(output/(key+'.EVALUATION.json'), result)
        return result, winner, receipt


def grade(run, task):
    try:
        observed = json.loads(run['stdout'])
    except (ValueError, TypeError):
        observed = None
    # Compare outputs on the host, not a success flag printed by candidate code.
    valid = (isinstance(observed, list) and len(observed) == len(task['expected'])
             and all(type(value) is int for value in observed))
    return dict(passed=run['returncode'] == 0 and not run['timed_out'] and valid
                and observed == task['expected'], host_graded=True, observed=observed,
                infrastructure_error=run['returncode'] in {125, 126, 127},
                examples=len(task['expected']), expected_digest=digest_of(task['expected']))


def execute(output: Path):
    plan=json.loads((output/'PLAN.json').read_text()); checked(plan, 'plan_digest')
    if plan['machinery'] != snapshot():
        raise ValueError('machinery changed after protocol freeze')
    if (output/'STARTED.json').exists():
        raise ValueError('preserve started/aborted run; prepare a new protocol to retry')
    _write_new(output/'STARTED.json', {'plan_digest':plan['plan_digest']})
    tasks={task['task_id']:task for task in plan['tasks']}
    if len(tasks) != len(plan['tasks']):
        raise ValueError('duplicate task identity')
    training_ids={cycle['training_task'] for cycle in plan['cycles']}
    final_ids=set(plan['final_tasks'])
    gate_ids={task for cycle in plan['cycles'] for task in cycle['promotion_tasks']}
    if training_ids & (final_ids | gate_ids) or final_ids & gate_ids:
        raise ValueError('task roles overlap')
    policy=validate_policy(plan['initial_policy']); rounds=[]
    _write_new(output/'POLICY0.json', policy)
    try:
        for index, cycle in enumerate(plan['cycles'],1):
            task=tasks[cycle['training_task']]
            if task['role'] != 'released_training': raise ValueError('wrong training role')
            training, winner, receipt=evaluate(task, policy, plan, output, discover=True)
            parent=policy; child=None; decision=None
            if winner and winner['provenance']['generator'] == 'repository_exemplar_mutations':
                child=propose_descendant(parent,winner,receipt,role='released_training')
                _write_new(output/f'CHILD{index}.json',child)
                comparisons=[]
                for task_id in cycle['promotion_tasks']:
                    target=tasks[task_id]
                    if target['role'] != 'promotion': raise ValueError('wrong promotion role')
                    before,_,_=evaluate(target,parent,plan,output)
                    after,_,_=evaluate(target,child,plan,output)
                    comparisons.append(dict(task_id=task_id,parent=before,child=after))
                decision=decide_promotion(parent,child,comparisons,training_ids=training_ids,
                                          candidate_budget=plan['candidate_budget'])
                _write_new(output/f'DECISION{index}.json',decision)
                if decision['promoted']:policy=child
            _write_new(output/f'POLICY{index}.json',policy)
            rounds.append(dict(cycle=index,training=training,parent_policy_digest=parent['policy_digest'],
                child_policy_digest=child['policy_digest'] if child else None,
                decision=decision,active_policy_digest=policy['policy_digest']))
            print('Cycle',index,'generation',policy['generation'],flush=True)
        # Final results cannot affect any training, selection, or admission decision.
        frozen_digest=policy['policy_digest']; final=[]
        for task_id in plan['final_tasks']:
            task=tasks[task_id]
            if task['role'] != 'final_evaluation':raise ValueError('wrong final role')
            before,_,_=evaluate(task,plan['initial_policy'],plan,output)
            after,_,_=evaluate(task,policy,plan,output)
            final.append(dict(task_id=task_id,language=task['language'],baseline=before,descendant=after))
        if policy['policy_digest'] != frozen_digest:raise ValueError('final evaluation changed policy')
        summary=dict(cycles=len(rounds),promotions=sum(bool(r['decision'] and r['decision']['promoted']) for r in rounds),
            generation=policy['generation'],acquired_strategies=len(policy['strategies']),
            final_tasks=len(final),baseline_passes=sum(r['baseline']['passed'] for r in final),
            descendant_passes=sum(r['descendant']['passed'] for r in final),
            external_model_calls=0,api_cost_usd=0,new_semantic_primitives_invented=0,
            general_rsi_demonstrated=False)
        result=sealed(dict(plan_digest=plan['plan_digest'],rounds=rounds,final=final,
            final_policy=policy,summary=summary,scope=plan['scope'],
            limitations=['authored tasks and fixed subscript-offset substrate',
                         'selection sets are development data, not independent evaluation',
                         'final tasks share the same family and near-identical source structure',
                         'parameter acquisition is not semantic primitive invention']), 'result_digest')
        _write_new(output/'RESULT.json',result)
        print(json.dumps(summary,indent=2),flush=True)
    except Exception as error:
        _write_new(output/'ABORTED.json',sealed(dict(plan_digest=plan['plan_digest'],
            error_type=type(error).__name__,error=str(error)[:500],completed_rounds=rounds,
            last_policy_digest=policy['policy_digest']), 'abort_digest'))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','run'])
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workspace',type=Path)
    parser.add_argument('--image',default='mira-mira-backend:latest')
    args=parser.parse_args()
    if args.action=='prepare':
        if args.workspace is None:parser.error('--workspace required for prepare')
        prepare(args.output,args.workspace,args.image)
    else:execute(args.output)


if __name__=='__main__':main()
