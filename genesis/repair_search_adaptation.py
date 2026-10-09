"""Outcome-driven modification of a bounded repair search policy.

The two orderings and diagnosis are authored. Genesis chooses a descendant from
released training evidence; the external controller owns its promotion tests.
"""
from pathlib import Path

from genesis import exemplar_strategy
from genesis.repair_self_improvement import checked, sealed, validate_policy

SCHEMA = 'genesis-repair-search-order-policy-v1'


def seed_search(capability_policy: dict) -> dict:
    validate_policy(capability_policy)
    return sealed(dict(schema=SCHEMA, generation=0, ordering='retained_first',
        capability_policy_digest=capability_policy['policy_digest'],
        parent_search_digest='', evidence_digest=''), 'search_policy_digest')


def validate_search(policy: dict) -> dict:
    body=checked(policy,'search_policy_digest')
    if (body.get('schema') != SCHEMA or body.get('ordering') not in {'retained_first','observed_first'}
        or type(body.get('generation')) is not int or body['generation'] < 0
        or not body.get('capability_policy_digest')):
        raise ValueError('invalid search policy')
    if body['generation'] == 0:
        if body['ordering'] != 'retained_first' or body['parent_search_digest'] or body['evidence_digest']:
            raise ValueError('invalid seed search policy')
    elif not body.get('parent_search_digest') or not body.get('evidence_digest'):
        raise ValueError('search adaptation provenance required')
    return policy


def derive_search_descendant(parent: dict, result: dict, searches: dict[str,dict]) -> dict:
    """Diagnose wasted retained-rule attempts using training outcomes only."""
    validate_search(parent); checked(result,'result_digest')
    if parent['capability_policy_digest'] != result['final_policy']['policy_digest']:
        raise ValueError('diagnosis and capability policy differ')
    examples=[]
    for round_record in result['rounds']:
        training=round_record['training'];checked(training,'evaluation_digest')
        if training.get('role') != 'released_training':
            raise ValueError('adaptation cannot consume evaluation outcomes')
        search=searches[training['search_digest']];checked(search,'search_digest')
        if (search['search_digest'] != training['search_digest'] or search['task_digest'] != training['task_digest']
            or search['policy_digest'] != training['policy_digest'] or search.get('discover') is not True):
            raise ValueError('training search provenance mismatch')
        candidates={c['candidate_digest']:c for c in search['candidates']}
        wasted=[]; found=False
        for attempt in training['attempts']:
            checked(attempt,'receipt_digest')
            if attempt.get('role') != 'released_training' or attempt.get('host_graded') is not True:
                raise ValueError('ungraded or nontraining diagnosis input')
            candidate=candidates[attempt['candidate_digest']]
            generator=candidate['provenance']['generator']
            if attempt['passed'] is False and generator == 'retained_acquired_strategy':
                wasted.append(attempt['receipt_digest'])
            if attempt['passed'] is True and generator == 'repository_exemplar_mutations':
                found=True;break
        if found and wasted:
            examples.append(dict(task_id=training['task_id'], failed_retained_receipts=wasted,
                                 training_evaluation_digest=training['evaluation_digest']))
    if len(examples)<2 or parent['ordering'] != 'retained_first':
        raise ValueError('insufficient repeated training evidence for ordering change')
    diagnosis=sealed(dict(examples=examples,source_result_digest=result['result_digest'],
        hypothesis='previously acquired rules waste validations before a useful repository observation',
        proposed_change='observed_first',only_training_outcomes_used=True), 'diagnosis_digest')
    child=sealed(dict(schema=SCHEMA,generation=parent['generation']+1,ordering='observed_first',
        capability_policy_digest=parent['capability_policy_digest'],parent_search_digest=parent['search_policy_digest'],
        evidence_digest=diagnosis['diagnosis_digest']), 'search_policy_digest')
    return dict(diagnosis=diagnosis,child=validate_search(child))


def ordered_candidates(root: Path, capability_policy: dict, search_policy: dict, *, budget: int):
    validate_policy(capability_policy);validate_search(search_policy)
    if (search_policy['capability_policy_digest'] != capability_policy['policy_digest']
        or type(budget) is not int or not 1<=budget<=32):
        raise ValueError('bounded matching policy required')
    retained=exemplar_strategy.generate_from_acquired(root,capability_policy['strategies'],max_candidates=32)['candidates']
    observed=exemplar_strategy.generate(root,max_candidates=32)['candidates']
    groups=[retained,observed] if search_policy['ordering']=='retained_first' else [observed,retained]
    ordered=[];seen=set()
    for group in groups:
        for candidate in group:
            mutation=candidate['mutations'][0]
            identity=(mutation['path'],mutation['content_utf8'])
            if identity not in seen:
                seen.add(identity);ordered.append(candidate)
    return ordered[:budget]


def search_promotion(parent: dict, child: dict, comparisons: list[dict], *, budget: int) -> dict:
    validate_search(parent);validate_search(child)
    if (child['parent_search_digest'] != parent['search_policy_digest']
        or child['generation'] != parent['generation']+1
        or child['capability_policy_digest'] != parent['capability_policy_digest'] or not comparisons):
        raise ValueError('direct child and promotion evidence required')
    gains=[];regressions=[];seen=set()
    for row in comparisons:
        task=row['task_id']
        if task in seen:raise ValueError('duplicate promotion task')
        seen.add(task)
        for key,policy in [('parent',parent),('child',child)]:
            outcome=row[key];checked(outcome,'evaluation_digest')
            if (outcome.get('task_id') != task or outcome.get('role') != 'promotion'
                or outcome.get('search_policy_digest') != policy['search_policy_digest']
                or outcome.get('candidate_budget') != budget or type(outcome.get('passed')) is not bool
                or type(outcome.get('attempt_count')) is not int or not 0<=outcome['attempt_count']<=budget
                or outcome.get('external_model_calls') != 0):
                raise ValueError('incomparable search evaluation')
        before=row['parent'];after=row['child']
        if before['passed'] and (not after['passed'] or after['attempt_count']>before['attempt_count']):
            regressions.append(task)
        if after['passed'] and (not before['passed'] or after['attempt_count']<before['attempt_count']):
            gains.append(task)
    return sealed(dict(parent_search_digest=parent['search_policy_digest'],child_search_digest=child['search_policy_digest'],
        comparisons=comparisons,gains=gains,regressions=regressions,promoted=bool(gains) and not regressions,
        rule='at least one success/validation-efficiency gain; no success/efficiency regression',
        authority='host-graded development selection; no general RSI claim'), 'decision_digest')
