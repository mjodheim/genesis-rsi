"""Cost accounting includes unsuccessful calls and never hides missing charges."""
import json
from pathlib import Path
import pytest
from genesis.trust_root import digest_of
from scripts.audit_repair_model_costs import summarize


def setup_records(tmp_path, calls):
    name = 'ACCOUNTING'
    bench = tmp_path / 'experiment/bench'
    bench.mkdir(parents=True)
    pre = {'model': 'test/model', 'cases': ['A-1', 'B-2']}
    binding = digest_of(pre)
    (bench / f'TRIAL_{name}_PREREG.json').write_text(json.dumps({**pre, 'preregistration_digest': binding}))
    result = {'preregistration_digest': binding, 'summary': {'usable_cases': 2, 'solved_per_arm': {'model_explore': 1}}}
    (bench / f'TRIAL_{name}_RESULT.json').write_text(json.dumps({**result, 'result_digest': digest_of(result)}))
    events = []
    for call in calls:
        body = {'case': 'A-1', 'arm': 'model_explore', 'preregistration_digest': binding, 'call': call}
        events.append(json.dumps({**body, 'event_digest': digest_of(body)}))
    (tmp_path / f'{name}.A-1.model_explore.calls.jsonl').write_text('\n'.join(events))
    return summarize(tmp_path, tmp_path, name)


def test_failed_attempts_included_and_reasoning_not_double_counted(tmp_path):
    result = setup_records(tmp_path, [
        {'request_sent': True, 'response_id': 'a', 'cost_usd': .02, 'call_failed': True,
         'usage': {'prompt_tokens': 100, 'completion_tokens': 80, 'completion_tokens_details': {'reasoning_tokens': 60}}},
        {'request_sent': True, 'response_id': 'b', 'cost_usd': .03},
        {'request_sent': False, 'budget_refused': True, 'cost_usd': 0}])
    assert result['total_cost_usd'] == pytest.approx(.05)
    assert result['cost_per_suite_passing_repair_usd'] == pytest.approx(.05)
    assert result['actual_requests'] == 2
    assert result['completion_tokens'] == 80
    assert result['reasoning_tokens'] == 60


def test_unknown_cost_prevents_claiming_total_or_cost_per_success(tmp_path):
    result = setup_records(tmp_path, [{'request_sent': True, 'cost_usd': None, 'call_failed': True}])
    assert result['calls_with_unknown_cost'] == 1
    assert result['total_cost_usd'] is None
    assert result['cost_per_suite_passing_repair_usd'] is None


def test_duplicate_billed_response_requires_inspection(tmp_path):
    with pytest.raises(ValueError, match='Duplicate response'):
        setup_records(tmp_path, [{'response_id': 'same', 'cost_usd': .01}] * 2)
