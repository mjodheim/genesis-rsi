"""Pre-register fresh Defects4J case IDs without opening any case checkout."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from genesis import external_repair_campaign as campaign
from genesis.learning import self_extension
from genesis.trust_root import digest_of
from scripts.run_autonomous_defects4j_lang import _active_bug_ids


def preregister(state_path: Path, count: int = 8) -> dict:
    state = campaign.CampaignStore(state_path).load()
    excluded = set(map(int, state['attempted_case_ids']))
    if state.get('current_case'):
        excluded.add(int(state['current_case']['case_id']))
    eligible = [i for i in _active_bug_ids() if i not in excluded]
    if not 1 <= count <= len(eligible):
        raise ValueError('invalid holdout count')
    seed = hashlib.sha256(('er4-ablation-v1|' + state['state_digest']).encode()).hexdigest()
    ranked = sorted(eligible, key=lambda i: hashlib.sha256((seed + '|' + str(i)).encode()).hexdigest())
    holdout = ranked[:count]
    machinery = state['machinery']
    payload = {
        'schema': 'genesis-er4-ablation-preregistration-v1',
        'parent_state_digest': state['state_digest'],
        'training_generation': state['generation'],
        'training_memory_digest': machinery['retained_memory']['memory_digest'],
        'baseline_memory_digest': self_extension.empty_memory()['memory_digest'],
        'candidate_budget_per_arm': machinery['candidate_budget'],
        'planner_front_budget_per_arm': machinery['planner_front_budget'],
        'selection_seed_sha256': seed,
        'eligible_count': len(eligible),
        'holdout_ids': [str(x) for x in holdout],
        'other_unseen_ids': [str(x) for x in ranked[count:]],
        'arms': ['baseline_no_memory', 'trained_memory'],
        'both_arms_must_freeze_before_reveal': True,
        'full_suite_validation_required': True,
        'holdout_training_prohibited': True,
    }
    return {**payload, 'preregistration_digest': digest_of(payload)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('state', type=Path)
    parser.add_argument('--count', type=int, default=8)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest = preregister(args.state, args.count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
