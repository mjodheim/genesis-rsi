#!/usr/bin/env python3
"""Summarize actual journal charges, including unsuccessful/aborted attempts.

A passing developer suite is a plausible repair, not proven correctness.
Reasoning tokens are a subset of completion tokens and are never added twice.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from genesis.trust_root import digest_of


def sealed(path, field):
    record = json.loads(path.read_text())
    body = {key: value for key, value in record.items() if key != field}
    if record.get(field) != digest_of(body):
        raise ValueError(f'Invalid digest: {path}')
    return record


def summarize(repo, workspace, name):
    pre = sealed(repo / 'experiment/bench' / f'TRIAL_{name}_PREREG.json', 'preregistration_digest')
    result_path = repo / 'experiment/bench' / f'TRIAL_{name}_RESULT.json'
    result = sealed(result_path, 'result_digest') if result_path.exists() else None
    if result and result['preregistration_digest'] != pre['preregistration_digest']:
        raise ValueError('Result/protocol mismatch')
    calls = []
    for path in sorted(workspace.glob(f'{name}.*.calls.jsonl')):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            body = {key: value for key, value in event.items() if key != 'event_digest'}
            if event.get('event_digest') != digest_of(body) or event['preregistration_digest'] != pre['preregistration_digest']:
                raise ValueError(f'Invalid journal event: {path}')
            calls.append(event['call'])
    sent = [call for call in calls if call.get('request_sent', True)]
    ids = [call['response_id'] for call in sent if call.get('response_id')]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate response IDs; accounting requires inspection')
    unknown = sum(call.get('cost_usd') is None for call in sent)
    known = sum(call['cost_usd'] for call in sent if call.get('cost_usd') is not None)
    outcomes = {case['case']: case for case in result['cases']} if result and 'cases' in result else {}
    partial = workspace / f'{name}.partial.jsonl'
    if not result and partial.exists():
        for line in partial.read_text().splitlines():
            case = json.loads(line)
            if case['case'] not in pre['cases']:
                raise ValueError('Partial outcome outside protocol')
            outcomes[case['case']] = case
    for path in sorted(workspace.glob(f'{name}.*.aborted.jsonl')):
        for line in path.read_text().splitlines():
            event = json.loads(line)
            body = {key: value for key, value in event.items() if key != 'event_digest'}
            if event.get('event_digest') != digest_of(body) or event['preregistration_digest'] != pre['preregistration_digest']:
                raise ValueError(f'Invalid aborted outcome: {path}')
            case = event['outcome']
            outcomes.setdefault(case['case'], case)
    solved = sum(result['summary']['solved_per_arm'].values()) if result else sum(
        bool(arm['solved']) for case in outcomes.values() for arm in case.get('arms', {}).values())
    usages = [call.get('usage', {}) for call in sent]
    return dict(name=name, model=pre['model'], sealed=result is not None,
                planned_cases=len(pre['cases']), usable_cases=result['summary']['usable_cases'] if result else None,
                observed_cases=[dict(case=case['case'], usable=case.get('usable'),
                    solved=any(arm['solved'] for arm in case.get('arms', {}).values()),
                    validated=sum(arm['validated'] for arm in case.get('arms', {}).values()))
                    for case in outcomes.values()],
                suite_passing_repairs=solved, actual_requests=len(sent),
                failed_calls=sum(bool(call.get('call_failed')) for call in sent),
                budget_refusals=sum(bool(call.get('budget_refused')) for call in calls),
                known_cost_usd=known, calls_with_unknown_cost=unknown,
                total_cost_usd=None if unknown else known,
                cost_per_suite_passing_repair_usd=known / solved if solved and not unknown else None,
                prompt_tokens=sum(u.get('prompt_tokens', 0) for u in usages),
                completion_tokens=sum(u.get('completion_tokens', 0) for u in usages),
                reasoning_tokens=sum((u.get('completion_tokens_details') or {}).get('reasoning_tokens', 0) for u in usages),
                calls_with_usage=sum(bool(u) for u in usages),
                cost_scope='all journaled attempts, including unsuccessful and aborted calls; excludes unjournaled in-flight requests and infrastructure')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(summarize(Path(__file__).resolve().parents[1], args.workspace, args.name), indent=2))
