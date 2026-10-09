from pathlib import Path
import json
import urllib.error

import pytest

from genesis.openrouter_repair import inspect_tool, openrouter_proposer
from run_repair_bench_trial import CallJournal


def setup(root):
    (root / 'src').mkdir()
    (root / 'test').mkdir()
    (root / 'src/A.java').write_text('class A { int value() { return 1; } }')
    return {'source_directory': 'src', 'test_directory': 'test', 'evidence_digest': 'e',
            'traces': [], 'test_source': [], 'production_source': []}


def response(name, args, cost=0.001):
    return {'id': 'r1', 'model': 'qwen/qwen3-coder', 'provider': 'test', 'usage': {'cost': cost},
            'choices': [{'finish_reason': 'tool_calls', 'message': {'role': 'assistant', 'content': None,
                'tool_calls': [{'id': 't1', 'type': 'function', 'function': {
                    'name': name, 'arguments': json.dumps(args)}}]}}]}


def fix(path='src/A.java'):
    return {'candidates': [{'hypothesis': 'wrong value', 'path': path,
                          'edits': [{'search': 'return 1;', 'replace': 'return 0;'}]}]}


def test_agent_inspects_then_submits_without_modifying_checkout(tmp_path):
    evidence = setup(tmp_path)
    answers = iter([response('read_file', {'path': 'src/A.java'}), response('submit_repairs', fix())])
    requests, calls = [], []
    def send(payload, timeout):
        requests.append(json.loads(json.dumps(payload)))
        return next(answers)
    proposer = openrouter_proposer('qwen/qwen3-coder', 4, calls, explore=True, transport=send)
    candidates = proposer(tmp_path, evidence, (), 4)
    assert len(candidates) == 1 and 'return 0;' in candidates[0].content
    assert 'return 1;' in (tmp_path / 'src/A.java').read_text()
    assert len(calls) == 2 and sum(call['cost_usd'] for call in calls) == 0.002
    assert any(message['role'] == 'tool' for message in requests[1]['messages'])
    assert requests[0]['provider']['allow_fallbacks'] is True
    assert requests[0]['model'] == requests[1]['model'] == 'qwen/qwen3-coder'


@pytest.mark.parametrize('path', ['../secret', '/etc/passwd', 'src/../../secret', '.git/config', 'src/.git/config'])
def test_inspection_refuses_paths_outside_roots_and_history(tmp_path, path):
    evidence = setup(tmp_path)
    with pytest.raises(ValueError):
        inspect_tool(tmp_path, evidence, 'read_file', {'path': path})


def test_inspection_refuses_symlinks_and_shell_tools(tmp_path):
    evidence = setup(tmp_path)
    (tmp_path / 'src/link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError):
        inspect_tool(tmp_path, evidence, 'read_file', {'path': 'src/link'})
    with pytest.raises(ValueError):
        inspect_tool(tmp_path, evidence, 'shell', {'command': 'echo bad'})
    assert 'src/link' not in inspect_tool(tmp_path, evidence, 'search_files', {'text': ''})


def test_provider_error_is_journaled_without_retry_or_secret(tmp_path):
    evidence = setup(tmp_path)
    journal = CallJournal(tmp_path / 'calls.jsonl', 'development', 'model', 'frozen')
    def send(payload, timeout):
        raise urllib.error.HTTPError('https://openrouter.ai', 429, 'limited', {}, None)
    assert openrouter_proposer('qwen/qwen3-coder', 1, journal, transport=send)(tmp_path, evidence, (), 1) == []
    assert len(journal) == 1 and journal[0]['http_status'] == 429
    event = json.loads((tmp_path / 'calls.jsonl').read_text())
    assert event['call']['call_failed'] and event['preregistration_digest'] == 'frozen'
    assert event['call']['cost_usd'] is None


def test_agent_stops_at_request_budget(tmp_path):
    evidence = setup(tmp_path)
    calls = []
    proposer = openrouter_proposer('qwen/qwen3-coder', 1, calls, explore=True, max_requests=2,
                                  transport=lambda *_: response('read_file', {'path': 'src/A.java'}))
    assert proposer(tmp_path, evidence, (), 1) == []
    assert len(calls) == 2 and calls[-1]['call_failed']


def test_test_edits_are_dropped(tmp_path):
    evidence = setup(tmp_path)
    (tmp_path / 'test/A.java').write_text('return 1;')
    calls = []
    proposer = openrouter_proposer('qwen/qwen3-coder', 1, calls,
                                  transport=lambda *_: response('submit_repairs', fix('test/A.java')))
    assert proposer(tmp_path, evidence, (), 1) == []
    assert not calls[0].get('call_failed')


@pytest.mark.parametrize("model", ["openai/gpt-6-luna", "anthropic/claude-sonnet-5.5", "anthropic/claude-haiku-5.5", "xiaomi/mimo-v2.6-pro"])
def test_routes_omit_unsupported_temperature(tmp_path, model):
    evidence = setup(tmp_path)
    payloads = []
    def send(payload, timeout):
        payloads.append(payload)
        return response('submit_repairs', fix())
    calls = []
    proposer = openrouter_proposer(model, 1, calls, transport=send)
    assert len(proposer(tmp_path, evidence, (), 1)) == 1
    assert 'temperature' not in payloads[0]
    assert payloads[0]['provider']['require_parameters']


def test_expensive_request_is_refused_before_network(tmp_path):
    evidence = setup(tmp_path)
    calls, requests = [], []
    def send(payload, timeout):
        requests.append(payload)
        return response('submit_repairs', fix())
    proposer = openrouter_proposer('qwen/qwen3-coder-next', 1, calls,
                                  max_call_usd=0.000001, transport=send)
    assert proposer(tmp_path, evidence, (), 1) == []
    assert requests == [] and calls[0]['budget_refused']
    assert calls[0]['request_sent'] is False and calls[0]['cost_usd'] == 0.0
    assert not calls[0].get('call_failed')


def test_price_and_round_reservation_limits(tmp_path):
    evidence = setup(tmp_path)
    calls, requests = [], []
    def send(payload, timeout):
        requests.append(payload)
        return response('read_file', {'path': 'src/A.java'})
    proposer = openrouter_proposer('qwen/qwen3-coder-next', 1, calls, explore=True,
                                  max_round_usd=0.005, transport=send)
    assert proposer(tmp_path, evidence, (), 1) == []
    assert len(requests) == 1 and calls[-1]['budget_refused']
    assert requests[0]['provider']['max_price'] == {'prompt': 0.2, 'completion': 1.0, 'request': 0.0}
    assert requests[0]['max_tokens'] == 2048


def test_trial_specific_prices_and_budget_are_forwarded(tmp_path):
    evidence = setup(tmp_path)
    calls, requests = [], []
    caps = {'prompt': 0.35, 'completion': 1.3, 'request': 0.0}
    def send(payload, timeout):
        requests.append(payload)
        return response('submit_repairs', fix())
    proposer = openrouter_proposer('deepseek/deepseek-v4.1-flash', 1, calls,
        max_tokens=4096, max_price=caps, max_call_usd=0.03, max_round_usd=0.06, transport=send)
    assert len(proposer(tmp_path, evidence, (), 1)) == 1
    assert requests[0]['provider']['max_price'] == caps
    assert requests[0]['max_tokens'] == 4096


def test_reasoning_effort_is_explicit_and_truncation_is_recorded(tmp_path):
    evidence = setup(tmp_path)
    calls, requests = [], []
    def send(payload, timeout):
        requests.append(payload)
        result = response('submit_repairs', fix())
        result['choices'][0]['finish_reason'] = 'length'
        return result
    proposer = openrouter_proposer('z-ai/glm-5.3-flash', 1, calls,
                                  reasoning_effort='low', transport=send)
    assert proposer(tmp_path, evidence, (), 1) == []
    assert requests[0]['reasoning'] == {'effort': 'low'}
    assert calls[0]['call_failed'] and calls[0]['finish_reason'] == 'length'


def test_haiku_fourth_request_uses_auto_submission_only(tmp_path):
    evidence=setup(tmp_path);requests=[];calls=[]
    answers=iter([response('read_file',{'path':'src/A.java'}) for _ in range(3)]+[response('submit_repairs',fix())])
    def send(payload,timeout):
        requests.append(json.loads(json.dumps(payload)))
        if payload['tool_choice']!='auto':
            raise urllib.error.HTTPError('https://openrouter.ai',404,'unsupported tool choice',{},None)
        return next(answers)
    candidates=openrouter_proposer('anthropic/claude-haiku-5.5',1,calls,explore=True,
        reasoning_effort='low',transport=send)(tmp_path,evidence,(),1)
    assert len(candidates)==1 and len(requests)==4
    assert [t['function']['name'] for t in requests[-1]['tools']]==['submit_repairs']
    assert all(r['tool_choice']=='auto' for r in requests)
    assert calls[-1]['submission_only'] and not any(c.get('call_failed') for c in calls)


def test_http_diagnostic_redacts_secret_before_truncating(tmp_path,monkeypatch):
    import io
    evidence=setup(tmp_path);calls=[];secret='unit-test-secret-that-must-not-leak'
    monkeypatch.setenv('OPENROUTER_API_KEY',secret)
    def send(*args):
        body=json.dumps({'error':{'code':404,'message':'x'*590+secret+' unsupported tool_choice'}}).encode()
        raise urllib.error.HTTPError('https://openrouter.ai',404,'unsupported',{},io.BytesIO(body))
    assert openrouter_proposer('anthropic/claude-haiku-5.5',1,calls,transport=send)(tmp_path,evidence,(),1)==[]
    assert calls[0]['http_status']==404 and calls[0]['api_error_code']==404
    assert secret not in json.dumps(calls) and secret[:8] not in calls[0]['api_error_message']
    assert calls[0]['cost_usd'] is None
