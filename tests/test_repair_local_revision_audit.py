import copy,json
import pytest
from genesis.repair_lineage import SEED_GENOME,Envelope,genome_digest
from genesis.repair_local_revision import paired_summary
from genesis.repair_self_improvement import sealed
from scripts.audit_repair_local_revision_trial import audit


def build(root,extra_calls=False,false_success=False):
    parent=copy.deepcopy(SEED_GENOME);child=copy.deepcopy(parent);child['playbook']='Check evidence.'
    plan=sealed(dict(seed_genome=parent,cases=['A'],replicates=2,envelope=Envelope(model='test').record(),spending_ceiling_usd=.35),'plan_digest')
    proposal=sealed(dict(parent_digest=genome_digest(parent),proposed_genome=child,genome=child,
        changed_leaves=['playbook'],accepted_for_measurement=True,promoted=False,calls=[dict(cost_usd=.001)]),'proposal_digest')
    def arm(passed):
        verdict=sealed(dict(candidate_digest='c',plausible=passed,stopped_at='passed' if passed else 'compile'),'verdict_digest')
        return sealed(dict(case='A',solved=passed or false_success,validated=1,verdicts=[verdict],calls=[dict(cost_usd=.001)]*(9 if extra_calls else 1)),'arm_digest')
    rows=[dict(case='A',replicate=1,order=['parent','child'],parent=arm(False),child=arm(True)),
          dict(case='A',replicate=2,order=['child','parent'],parent=arm(True),child=arm(True))]
    summary=paired_summary(rows)
    result=sealed(dict(plan_digest=plan['plan_digest'],proposal_digest=proposal['proposal_digest'],rows=rows,summary=summary,
        proposal_known_cost_usd=.001,proposal_unknown_calls=0,policy_promoted=False,held_out_consumed=False,
        decision='candidate_for_larger_test' if summary['warrants_larger_test'] else 'no_demonstrated_local_gain'),'result_digest')
    for name,data in [('PLAN',plan),('PROPOSAL',proposal),('RESULT',result)]:
        (root/(name+'.json')).write_text(json.dumps(data))


def test_consistent_small_pilot_is_audit_only(tmp_path):
    build(tmp_path);assert not audit(tmp_path)['independent_execution_replication']


def test_resealed_over_budget_record_is_refused(tmp_path):
    build(tmp_path,extra_calls=True)
    with pytest.raises(ValueError,match='budget'):audit(tmp_path)


def test_resealed_claimed_success_requires_passing_receipt(tmp_path):
    build(tmp_path,false_success=True)
    with pytest.raises(ValueError,match='false success'):audit(tmp_path)
