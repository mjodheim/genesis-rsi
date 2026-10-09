import json

import pytest

from genesis.repair_branch_strategy import strategy_genome
from genesis.repair_lineage import SEED_GENOME, genome_digest
from genesis.repair_local_revision import changed_leaves, paired_summary
from genesis.repair_self_improvement import sealed
from scripts.run_repair_branch_strategy_trial import verify


def test_strategy_changes_only_playbook_without_mutating_parent():
    before = json.dumps(SEED_GENOME, sort_keys=True)
    child = strategy_genome(SEED_GENOME)
    assert changed_leaves(SEED_GENOME, child) == ['playbook']
    assert json.dumps(SEED_GENOME, sort_keys=True) == before


def test_strategy_receipts_bind_each_arm_to_its_genome(tmp_path):
    child = strategy_genome(SEED_GENOME)
    plan = sealed(dict(cases=['Case-1'], replicates=1, seed_genome=SEED_GENOME,
                       child_genome=child, spending_ceiling_usd=.2,
                       envelope=dict(validations_per_case=6, model_requests_per_case=8)), 'plan_digest')
    arm = sealed(dict(solved=False, validated=1,
        verdicts=[dict(candidate_digest='first')], calls=[dict(round=1, cost_usd=.001,
        submission_results=[dict(parent='', applicable=True, candidate_digest='first',
        complete_paths=['src/A.java'], files=[dict(path='src/A.java')])])]), 'arm_digest')
    rows = [dict(case='Case-1', replicate=1, order=['parent', 'child'], parent=arm, child=arm)]
    result = sealed(dict(plan_digest=plan['plan_digest'], rows=rows,
                         summary=paired_summary(rows)), 'result_digest')
    calls = [dict(case='Case-1', label=f'branch-strategy-r1-{name}',
             genome=genome_digest(genome), call=arm['calls'][0])
             for name, genome in [('parent', SEED_GENOME), ('child', child)]]
    for name, body in [('PLAN.json', plan), ('RESULT.json', result),
                       ('JOURNAL.json', sealed(dict(calls=calls), 'journal_digest'))]:
        (tmp_path/name).write_text(json.dumps(body))
    assert verify(tmp_path)['verified']
    calls[1]['genome'] = genome_digest(SEED_GENOME)
    (tmp_path/'JOURNAL.json').write_text(json.dumps(sealed(dict(calls=calls), 'journal_digest')))
    with pytest.raises(ValueError, match='genome differs'):
        verify(tmp_path)
