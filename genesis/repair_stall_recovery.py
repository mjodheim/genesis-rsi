"""Bounded failure-derived search generations; proposals are never promoted implicitly."""
from genesis.repair_quality_learning import classify, rank
from genesis.repair_self_improvement import checked, sealed


def diagnose(candidates, history, *, budget):
    seen = {c.digest for c, _ in history}
    if any(v.get('plausible') and v.get('stopped_at') == 'passed' for _, v in history):
        return 'success'
    if len(history) >= budget:
        return 'validation_budget_exhausted'
    if not candidates:
        return 'empty_candidate_pool'
    if all(c.digest in seen for c in candidates):
        return 'candidate_pool_exhausted'
    return 'candidates_remaining'


def recover(generator, policy, validator, *, generation_sizes=(8, 32, 128), budget=24, record=None):
    """Generator receives failed history; each size is a proposal, not a capability gain.

    The total validation budget spans generations. Repeated candidates are never charged
    twice. Compile/test verdicts remain observable. All candidate acceptance requires the
    validator's sealed full-suite passing receipt. No model calls or automatic promotion.
    """
    if not generation_sizes or len(generation_sizes) > 8 or budget < 1:
        raise ValueError('positive bounded generations and validation budget required')
    if any(type(n) is not int or not 1 <= n <= 1024 for n in generation_sizes):
        raise ValueError('bounded candidate sizes required')
    checked(policy, 'policy_digest')
    history = []; generations = []; accepted = None; parent = None
    for index, size in enumerate(generation_sizes):
        if len(history) >= budget or accepted is not None:
            break
        pool = list(generator(size, tuple(history)))
        unique = {c.digest: c for c in pool}
        fresh = rank(list(unique.values()), policy, history)
        proposal = sealed(dict(generation=index, parent_generation_digest=parent,
            requested_candidates=size, generated=len(pool), unique_candidates=len(unique),
            new_candidates=len(fresh), prior_verdict_digests=[v['verdict_digest'] for _, v in history],
            cause='initial_search' if index == 0 else generations[-1]['stop_reason'],
            promoted=False), 'generation_digest')
        if record: record('generation', proposal)
        attempts = []
        while fresh and len(history) < budget:
            candidate = fresh[0]; verdict = validator(candidate)
            checked(verdict, 'verdict_digest')
            if verdict['candidate_digest'] != candidate.digest:
                raise ValueError('validator identity mismatch')
            history.append((candidate, verdict))
            attempt = dict(candidate_digest=candidate.digest, verdict=verdict, diagnosis=classify(verdict))
            attempts.append(attempt)
            if record: record('attempt', sealed(attempt, 'attempt_digest'))
            if verdict.get('plausible') and verdict.get('stopped_at') == 'passed':
                accepted = candidate; break
            fresh = rank(list(unique.values()), policy, history)
        reason = diagnose(list(unique.values()), history, budget=budget)
        generations.append(dict(proposal=proposal, attempts=attempts, stop_reason=reason))
        parent = proposal['generation_digest']
    reason = 'success' if accepted else ('validation_budget_exhausted' if len(history) >= budget else 'generation_budget_exhausted')
    return dict(solved=accepted is not None, accepted=accepted, generations=generations,
        validated=len(history), stop_reason=reason, external_model_calls=0, api_cost_usd=0,
        promoted=False)
