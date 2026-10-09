from copy import deepcopy

import pytest

from genesis.repair_bench import Candidate
from genesis.repair_causal_evidence import check, observation
from genesis.repair_lineage import Envelope, GenomeError, Ledger, lineage_proposer
from test_repair_lineage import answer, genome, scripted, setup


def record(evidence, history, quote, term='Serializable', relation='present'):
    observed = observation(evidence, history)
    return dict(observed_signal=observed['observed_signal'], previous_assessment=observed['previous_assessment'],
                facts=[dict(path='src/A.java', line=1, quote=quote, term=term, relation=relation)],
                explanation='Check the declared interface before changing the configuration.',
                prediction='The observed exception should disappear.')


def test_literal_contradiction_and_fabricated_observation_are_rejected(tmp_path):
    evidence = setup(tmp_path)
    source = 'class A implements Serializable { int n = 1; }'
    (tmp_path/'src/A.java').write_text(source)
    evidence['traces'] = [dict(trace='java.io.NotSerializableException: B\n at f()')]
    valid = record(evidence, [], source)
    assert check(tmp_path, evidence, [], '', valid) is None
    bad = deepcopy(valid); bad['facts'][0]['relation'] = 'absent'
    assert 'contradicts quoted line' in check(tmp_path, evidence, [], '', bad)
    bad = deepcopy(valid); bad['observed_signal'] = 'java.io.NotSerializableException: C'
    assert 'contradicts host record' in check(tmp_path, evidence, [], '', bad)


def test_quote_uses_selected_parent_and_tracks_refuted_prediction(tmp_path):
    evidence = setup(tmp_path)
    old = (tmp_path/'src/A.java').read_text().splitlines()[0]
    parent = Candidate('src/A.java', 'class A implements Serializable {}', 't',
                       provenance={'causal_evidence': {'observed_signal': 'same error'}})
    h = [(parent, dict(candidate_digest=parent.digest, stopped_at='failing_tests', feedback='--- Test\nsame error\n at f()'))]
    assert observation(evidence, h)['previous_assessment'] == 'signal_unchanged'
    valid = record(evidence, h, parent.content)
    assert check(tmp_path, evidence, h, parent.digest, valid) is None
    bad = deepcopy(valid); bad['facts'][0]['quote'] = old
    assert 'does not match' in check(tmp_path, evidence, h, parent.digest, bad)
    bad = deepcopy(valid); bad['previous_assessment'] = 'signal_changed'
    assert 'contradicts host record' in check(tmp_path, evidence, h, parent.digest, bad)
    h[0][1]['feedback'] = 'new error'
    assert observation(evidence, h)['previous_assessment'] == 'signal_changed'


@pytest.mark.parametrize('mutation', ['test_path', 'unknown_parent', 'bad_line', 'bad_fact', 'missing_prediction'])
def test_invalid_evidence_is_refused_without_writes(tmp_path, mutation):
    evidence = setup(tmp_path); source = (tmp_path/'src/A.java').read_text()
    r = record(evidence, [], source.splitlines()[0], term='class')
    parent = ''
    if mutation == 'test_path': r['facts'][0]['path'] = 'test/A.java'
    if mutation == 'unknown_parent': parent = 'unknown'
    if mutation == 'bad_line': r['facts'][0]['line'] = True
    if mutation == 'bad_fact': r['facts'][0] = 'not an object'
    if mutation == 'missing_prediction': r.pop('prediction')
    assert check(tmp_path, evidence, [], parent, r)
    assert (tmp_path/'src/A.java').read_text() == source


def test_rejected_premise_can_be_corrected_within_existing_request_budget(tmp_path):
    evidence = setup(tmp_path); source = (tmp_path/'src/A.java').read_text()
    good = record(evidence, [], source.splitlines()[0], term='class')
    bad = deepcopy(good); bad['facts'][0]['relation'] = 'absent'
    item = dict(parent='', hypothesis='fix', files=[dict(path='src/A.java', edits=[dict(search='return 1;', replace='return 2;')])])
    send, seen = scripted(answer('submit_repairs', dict(candidates=[dict(item, causal_evidence=bad)])),
                          answer('submit_repairs', dict(candidates=[dict(item, causal_evidence=good)])))
    calls = []
    proposer = lineage_proposer(genome(inspection_requests=1, rounds=1), Envelope(model='test/model'), Ledger(1),
        calls, transport=send, application_feedback=True, multi_file=True, branching=True, causal_checks=True)
    result = proposer(tmp_path, evidence, [], 6)
    assert len(result) == 1 and len(calls) == 2
    assert calls[0]['submission_results'][0]['causal_rejection']
    assert result[0].provenance['causal_evidence'] == good
    assert 'contradicts quoted line' in seen[1]['messages'][-2]['content']
    assert (tmp_path/'src/A.java').read_text() == source


def test_causal_gate_requires_feedback_and_branches():
    with pytest.raises(GenomeError, match='require'):
        lineage_proposer(genome(), Envelope(model='test/model'), Ledger(1), [], causal_checks=True)
