"""Bounded development lineage over existing exemplar-derived repair strategies.

This is capability acquisition inside an authored substrate, not new primitive
invention. Validators own grading; content digests do not authenticate them.
"""
from __future__ import annotations

from pathlib import Path

from genesis import exemplar_strategy
from genesis.trust_root import digest_of

SCHEMA = 'genesis-repair-strategy-lineage-v1'


def sealed(body: dict, key: str) -> dict:
    return {**body, key: digest_of(body)}


def checked(record: dict, key: str) -> dict:
    body = {k: v for k, v in record.items() if k != key}
    if record.get(key) != digest_of(body):
        raise ValueError('invalid ' + key)
    return body


def seed_policy() -> dict:
    return sealed(dict(schema=SCHEMA, generation=0, parent_policy_digest='',
                       training_receipt_digest='', strategies=[]), 'policy_digest')


def validate_policy(policy: dict) -> dict:
    body = checked(policy, 'policy_digest')
    generation = body.get('generation')
    if (body.get('schema') != SCHEMA or type(generation) is not int or generation < 0
        or set(body) != {'schema', 'generation', 'parent_policy_digest',
                         'training_receipt_digest', 'strategies'}):
        raise ValueError('invalid policy schema')
    if generation == 0:
        if body['parent_policy_digest'] or body['training_receipt_digest'] or body['strategies']:
            raise ValueError('seed must have no learned capabilities')
    elif not body['parent_policy_digest'] or not body['training_receipt_digest']:
        raise ValueError('descendant provenance required')
    if not isinstance(body['strategies'], list) or len(body['strategies']) > 32:
        raise ValueError('bounded strategy list required')
    seen = set()
    for strategy in body['strategies']:
        checked(strategy, 'strategy_digest')
        delta = strategy.get('delta')
        if (strategy.get('schema') != exemplar_strategy.ACQUIRED_STRATEGY_SCHEMA
            or strategy.get('kind') != 'subscript_identifier_delta'
            or strategy.get('host_issue_specific_recipe') is not False
            or strategy.get('external_model_calls') != 0
            or type(delta) is not int or abs(delta) > 100 or delta == 0
            or strategy['strategy_digest'] in seen):
            raise ValueError('invalid or duplicate acquired strategy')
        seen.add(strategy['strategy_digest'])
        sign = '+' if delta > 0 else '-'
        if (strategy.get('template_before') != '[$IDENT]'
            or strategy.get('template_after') != f'[$IDENT {sign} {abs(delta)}]'):
            raise ValueError('strategy template contradicts executable parameter')
    return policy


def propose(root: Path, policy: dict, *, discover: bool, budget: int = 4) -> list[dict]:
    """Generation sees production source only, not test inputs or expected answers."""
    validate_policy(policy)
    if type(budget) is not int or not 1 <= budget <= 32:
        raise ValueError('candidate budget must be in [1,32]')
    retained = exemplar_strategy.generate_from_acquired(
        root, policy['strategies'], max_candidates=budget)['candidates']
    observed = exemplar_strategy.generate(root, max_candidates=budget)['candidates'] if discover else []
    result = []; seen = set()
    for candidate in retained + observed:
        mutation = candidate['mutations']
        identity = digest_of(mutation)
        if identity not in seen:
            seen.add(identity); result.append(candidate)
        if len(result) == budget:
            break
    return result


def propose_descendant(parent: dict, candidate: dict, receipt: dict, *, role: str) -> dict:
    """A successful training repair proposes a child; it does not promote it."""
    validate_policy(parent); checked(receipt, 'receipt_digest')
    if role != 'released_training' or receipt.get('role') != role:
        raise ValueError('learning allowed only on released training')
    if (receipt.get('candidate_digest') != candidate.get('candidate_digest')
        or receipt.get('passed') is not True or receipt.get('host_graded') is not True
        or receipt.get('timed_out') is not False or receipt.get('returncode') != 0):
        raise ValueError('matching host-graded passing receipt required')
    # Existing substrate extracts the offset and removes the original identifier.
    strategy = exemplar_strategy.acquire_strategy(candidate, result_digest=receipt['receipt_digest'])
    if any(s['delta'] == strategy['delta'] for s in parent['strategies']):
        raise ValueError('candidate adds no new capability parameter')
    child = sealed(dict(schema=SCHEMA, generation=parent['generation'] + 1,
        parent_policy_digest=parent['policy_digest'], training_receipt_digest=receipt['receipt_digest'],
        strategies=parent['strategies'] + [strategy]), 'policy_digest')
    return validate_policy(child)


def decide_promotion(parent: dict, child: dict, comparisons: list[dict], *, training_ids: set[str],
                     candidate_budget: int) -> dict:
    """Strict gain and no task regression on a separate promotion set.

    Promotion tasks are development selection data, never a final held-out bank.
    The caller owns independent evaluation and must protect its task manifests.
    """
    validate_policy(parent); validate_policy(child)
    if (child['parent_policy_digest'] != parent['policy_digest']
        or child['generation'] != parent['generation'] + 1
        or len(child['strategies']) != len(parent['strategies']) + 1
        or child['strategies'][:-1] != parent['strategies']
        or type(candidate_budget) is not int or not 1 <= candidate_budget <= 32):
        raise ValueError('child is not a bounded direct descendant')
    seen = set(); gains = []; regressions = []
    if not comparisons:
        raise ValueError('separate promotion tasks required')
    for row in comparisons:
        task = row['task_id']
        if task in training_ids or task in seen:
            raise ValueError('training/promotion overlap or duplicate task')
        seen.add(task)
        for name, policy in [('parent', parent), ('child', child)]:
            result = row[name]; checked(result, 'evaluation_digest')
            if (result.get('policy_digest') != policy['policy_digest']
                or result.get('task_id') != task or result.get('role') != 'promotion'
                or result.get('candidate_budget') != candidate_budget
                or type(result.get('passed')) is not bool
                or type(result.get('attempt_count')) is not int
                or not 0 <= result['attempt_count'] <= candidate_budget
                or result.get('external_model_calls') != 0):
                raise ValueError('incomparable or invalid promotion results')
        if row['child']['passed'] and not row['parent']['passed']:
            gains.append(task)
        if row['parent']['passed'] and not row['child']['passed']:
            regressions.append(task)
    body = dict(parent_policy_digest=parent['policy_digest'], child_policy_digest=child['policy_digest'],
        comparisons=comparisons, candidate_budget=candidate_budget, gains=gains, regressions=regressions,
        promoted=bool(gains) and not regressions, rule='strict task gain; no task regression',
        scope='project-authored development selection; not independent RSI evidence',
        new_semantic_primitive_invented=False)
    return sealed(body, 'decision_digest')
