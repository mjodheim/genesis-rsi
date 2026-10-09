import json

import pytest

from genesis.repair_lineage import SEED_GENOME, genome_digest
from genesis.repair_local_revision import paired_summary
from genesis.repair_self_improvement import sealed
from scripts.run_repair_causal_evidence_trial import verify
from scripts.run_repair_causal_evidence_normalized_trial import verify as verify_normalized


def fixture(folder, incorrect=False):
    plan = sealed(dict(cases=['Case-1'], replicates=1, seed_genome=SEED_GENOME,
        child_genome=SEED_GENOME, spending_ceiling_usd=.2,
        envelope=dict(validations_per_case=6, model_requests_per_case=8)), 'plan_digest')
    base = dict(parent='', applicable=True, candidate_digest='first', complete_paths=['src/A.java'], files=[dict(path='src/A.java')])
    parent = sealed(dict(solved=False, validated=1, verdicts=[dict(candidate_digest='first')],
        calls=[dict(round=1, cost_usd=.001, submission_results=[base])]), 'arm_digest')
    assessment = 'signal_changed' if incorrect else 'signal_unchanged'
    calls = []
    for round_number, identity, previous, status in [(1, 'first', None, 'none'), (2, 'second', 'first', assessment)]:
        observed = dict(observed_signal='same error', previous_assessment=status,
                        candidate_digest=previous, stage='baseline' if previous is None else 'failing_tests')
        proposal = dict(base, candidate_digest=identity, causal_checks_passed=True, causal_rejection=None,
                        causal_evidence=dict(observed_signal='same error', previous_assessment=status))
        calls.append(dict(round=round_number, cost_usd=.001, causal_observation=observed, submission_results=[proposal]))
    child = sealed(dict(solved=False, validated=2, causal_baseline_signal='same error', calls=calls,
        verdicts=[dict(candidate_digest=name, feedback='same error', stopped_at='failing_tests') for name in ['first', 'second']]), 'arm_digest')
    rows = [dict(case='Case-1', replicate=1, order=['parent','child'], parent=parent, child=child)]
    result = sealed(dict(plan_digest=plan['plan_digest'], rows=rows, summary=paired_summary(rows)), 'result_digest')
    journal = [dict(case='Case-1', label=f'causal-evidence-r1-{arm}', genome=genome_digest(SEED_GENOME), call=c)
               for arm, body in [('parent',parent),('child',child)] for c in body['calls']]
    for name, body in [('PLAN.json',plan),('RESULT.json',result),('JOURNAL.json',sealed(dict(calls=journal),'journal_digest'))]:
        (folder/name).write_text(json.dumps(body))


@pytest.mark.parametrize('verify', [verify, verify_normalized])
def test_evidence_receipts_match_previous_external_verdict(tmp_path, verify):
    fixture(tmp_path)
    assert verify(tmp_path)['calls'] == 3


@pytest.mark.parametrize('verify', [verify, verify_normalized])
def test_false_prediction_assessment_is_rejected_even_if_receipts_agree(tmp_path, verify):
    fixture(tmp_path, incorrect=True)
    with pytest.raises(ValueError, match='previous prediction assessment'):
        verify(tmp_path)
