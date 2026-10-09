#!/usr/bin/env python3
"""Audit recorded local revision measurements without rerunning repairs."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from genesis.repair_lineage import fits,genome_digest
from genesis.repair_local_revision import ALLOWED,changed_leaves,paired_summary
from genesis.repair_self_improvement import checked,sealed
from scripts.run_repair_lineage import envelope_of


def audit(directory):
    plan=json.loads((directory/'PLAN.json').read_text());checked(plan,'plan_digest')
    proposal=json.loads((directory/'PROPOSAL.json').read_text());checked(proposal,'proposal_digest')
    result=json.loads((directory/'RESULT.json').read_text());checked(result,'result_digest')
    if result['plan_digest']!=plan['plan_digest'] or result['proposal_digest']!=proposal['proposal_digest']:raise ValueError('ancestry mismatch')
    if proposal['parent_digest']!=genome_digest(plan['seed_genome']):raise ValueError('parent identity mismatch')
    child=proposal['proposed_genome'];changes=changed_leaves(plan['seed_genome'],child) if child else []
    valid=child is not None and len(changes)==1 and changes[0] in ALLOWED
    if proposal['changed_leaves']!=changes or proposal['accepted_for_measurement']!=valid or proposal['genome']!=(child if valid else None):raise ValueError('mutation constraint mismatch')
    if proposal['promoted'] or result['policy_promoted'] or result['held_out_consumed']:raise ValueError('scope exceeded')
    envelope=envelope_of(plan)
    if valid:
        if not fits(child,envelope):raise ValueError('envelope exceeded')
        expected=[(case,replicate) for replicate in range(1,plan['replicates']+1) for case in plan['cases']]
        if [(r['case'],r['replicate']) for r in result['rows']]!=expected:raise ValueError('missing or reordered pair')
        for row in result['rows']:
            index=plan['cases'].index(row['case']);order=['parent','child'] if (row['replicate']+index)%2 else ['child','parent']
            if row['order']!=order:raise ValueError('arm order mismatch')
            for name in ('parent','child'):
                arm=row[name];checked(arm,'arm_digest')
                if arm['case']!=row['case'] or len(arm['calls'])>envelope.requests or arm['validated']>envelope.validations:raise ValueError('case budget mismatch')
                if len(arm['verdicts'])!=arm['validated']:raise ValueError('validation count mismatch')
                for verdict in arm['verdicts']:checked(verdict,'verdict_digest')
                passed=any(v['plausible'] and v['stopped_at']=='passed' for v in arm['verdicts'])
                if bool(arm['solved'])!=passed:raise ValueError('false success claim')
        known=sum(c['cost_usd'] for c in proposal['calls'] if c.get('cost_usd') is not None)
        unknown=sum(c.get('cost_usd') is None for c in proposal['calls'])
        if result['proposal_known_cost_usd']!=known or result['proposal_unknown_calls']!=unknown:raise ValueError('proposal cost mismatch')
        summary=paired_summary(result['rows'])
        if known+summary['known_api_cost_usd']>plan['spending_ceiling_usd']:raise ValueError('spending ceiling exceeded')
        if result['summary']!=summary:raise ValueError('summary mismatch')
        if result['decision']!=('candidate_for_larger_test' if summary['warrants_larger_test'] else 'no_demonstrated_local_gain'):raise ValueError('decision mismatch')
    elif result['rows'] or result['decision']!='no_valid_single_leaf_revision':raise ValueError('invalid proposal measured')
    journal_checked=False
    journal_path=directory/'JOURNAL.json'
    if journal_path.exists():
        journal=json.loads(journal_path.read_text());checked(journal,'journal_digest')
        groups={}
        for entry in journal['records']:
            groups.setdefault((entry['label'],entry.get('case')),[]).append(entry)
        expected={('local-successor',None)}
        if [e['call'] for e in groups.get(('local-successor',None),[])]!=proposal['calls']:raise ValueError('proposal journal mismatch')
        for row in result['rows']:
            for name in ('parent','child'):
                key=(f"local-r{row['replicate']}-{name}",row['case']);expected.add(key)
                entries=groups.get(key,[])
                genome=plan['seed_genome'] if name=='parent' else proposal['genome']
                if any(e.get('genome')!=genome_digest(genome) for e in entries):raise ValueError('journal genome mismatch')
                if [e['call'] for e in entries]!=row[name]['calls']:raise ValueError('arm journal mismatch')
        if set(groups)!=expected:raise ValueError('unmatched journal requests')
        journal_checked=True
    return sealed(dict(result_digest=result['result_digest'],proposal_digest=proposal['proposal_digest'],
        stored_evidence_consistent=True,journal_checked=journal_checked,independent_execution_replication=False),'verification_digest')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);print(json.dumps(audit(p.parse_args().directory),indent=2))
