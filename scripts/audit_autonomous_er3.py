import argparse
import collections
import hashlib
import json
from pathlib import Path

from genesis import external_repair_campaign as campaign
from genesis.learning import self_extension
from genesis.trust_root import digest_of


def audit(path: Path):
    raw = path.read_bytes()
    state = campaign.validate_state(json.loads(raw))
    memory = self_extension.validate_memory(state['machinery']['retained_memory'])
    events = state['events']
    previous = ''
    for index, event in enumerate(events):
        unsigned = {k: v for k, v in event.items() if k != 'event_digest'}
        if event['index'] != index or event['previous_event_digest'] != previous:
            raise ValueError('event chain order mismatch')
        if digest_of(unsigned) != event['event_digest']:
            raise ValueError('event digest mismatch')
        previous = event['event_digest']
    counts = collections.Counter(e['kind'] for e in events)
    cases = [e['payload']['case_id'] for e in events if e['kind'] == 'case_closed']
    overfit = sum(
        e['kind'] == 'trigger_positive_rejected'
        or (e['kind'] == 'positive_validated' and not e['payload'].get('passed'))
        for e in events
    )
    freeze = state.get('blind_freeze') or {}
    activation = (freeze.get('planner_summary') or {}).get('family_activation', {})
    retained = activation.get('retained_structural') or {}
    return {
        'schema': 'genesis-er3-audit-v1',
        'state_sha256': hashlib.sha256(raw).hexdigest(),
        'state_digest': state['state_digest'],
        'last_event_digest': previous,
        'phase': state['phase'],
        'current_case': (state.get('current_case') or {}).get('case_id'),
        'completed_cases': state['generation'],
        'completed_case_ids': cases,
        'selected_cases': counts['case_selected'],
        'seeded_exclusions': len(state['attempted_case_ids']) - state['generation'],
        'full_repairs_validated': state['success_count'],
        'trigger_only_rejections': overfit,
        'blind_evaluation_rounds': counts['blind_result_frozen'],
        'negative_diagnoses': counts['negative_diagnosed_pre_reveal'],
        'human_solution_reveals_after_negative': counts['solution_revealed_after_negative'],
        'machinery_validations': counts['machinery_validation'],
        'machinery_validation_passes': sum(
            e['payload'].get('passed') is True for e in events if e['kind'] == 'machinery_validation'
        ),
        'memory_generation': memory['generation'],
        'retained_operators': len(memory['operators']),
        'current_case_retained_variants_generated': retained.get('generated'),
        'current_case_retained_variants_accepted': retained.get('accepted'),
        'current_case_retained_variants_activated': retained.get('activated'),
        'scientific_caveat': 'Retained candidates generated is not proof of causal transfer. Machinery validation is not a full repair.',
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('state', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = audit(args.state)
    encoded = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(encoded, end='')


if __name__ == '__main__':
    main()
