"""Development-only economical repair routing and validated pattern reuse.

This is a bounded integration, not a general-understanding or RSI claim. Memory
contains explicitly released development observations; it must not be used to
adapt a frozen held-out experiment. Every retained pattern is revalidated.
"""
from __future__ import annotations
from dataclasses import dataclass
import difflib
import json
import math
from pathlib import Path
import re
import sqlite3

from genesis.openrouter_repair import _allowed, openrouter_proposer
from genesis.repair_bench import Candidate, apply_edits
from genesis.trust_root import digest_of


@dataclass(frozen=True)
class ModelOption:
    model: str
    input_usd_per_million: float
    output_usd_per_million: float
    reasoning: str | None = 'low'

    def __post_init__(self):
        if not self.model or any(not math.isfinite(v) or v < 0 for v in
            (self.input_usd_per_million, self.output_usd_per_million)):
            raise ValueError('invalid model or tariff')


def task_features(evidence: dict) -> dict:
    """Transparent proxies from buggy-side observations, never expected fixes."""
    sources = evidence.get('production_source', [])
    paths = sorted({item['path'] for item in sources})
    source_chars = sum(len(item.get('numbered_source', '')) for item in sources)
    failing = len(evidence.get('failing_tests', []))
    complexity = 'complex' if len(paths) >= 4 or source_chars > 20000 or failing > 4 else (
        'moderate' if len(paths) > 1 or source_chars > 8000 or failing > 1 else 'simple')
    trace = '\n'.join(item.get('trace', '') for item in evidence.get('traces', []))
    errors = sorted(set(re.findall(r'\b(?:[\w$]+\.)*([\w$]*(?:Exception|Error))\b', trace)))
    languages = sorted({Path(path).suffix for path in paths})
    return dict(complexity=complexity, source_files=len(paths), source_chars=source_chars,
                failing_tests=failing, family=digest_of({'errors': errors, 'languages': languages}))


class RepairExperience:
    """Durable, digest-chained development events. Digests do not authenticate authors."""
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY, payload TEXT NOT NULL, digest TEXT UNIQUE NOT NULL)')

    def connect(self):
        return sqlite3.connect(self.path, timeout=20)

    def append(self, kind: str, data: dict):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            last = db.execute('SELECT digest FROM events ORDER BY sequence DESC LIMIT 1').fetchone()
            body = dict(kind=kind, data=data, previous_digest=last[0] if last else '', scope='released_development')
            db.execute('INSERT INTO events(payload,digest) VALUES (?,?)', (json.dumps(body, sort_keys=True), digest_of(body)))

    def events(self):
        with self.connect() as db:
            rows = db.execute('SELECT payload,digest FROM events ORDER BY sequence').fetchall()
        previous = ''; events = []
        for payload, checksum in rows:
            event = json.loads(payload)
            if event.get('previous_digest') != previous or digest_of(event) != checksum:
                raise ValueError('experience chain integrity failure')
            previous = checksum; events.append(event)
        return events

    def record_attempt(self, features: dict, model: str, cost_usd: float | None, passed: bool, *, role: str):
        if role != 'released_development':
            raise ValueError('only explicitly released development observations allowed')
        if cost_usd is not None and (not math.isfinite(cost_usd) or cost_usd < 0):
            raise ValueError('invalid cost')
        self.append('attempt', dict(features=features, model=model, cost_usd=cost_usd, passed=bool(passed)))

    def review_transport_failure(self, attempt_digest: str, diagnostic: dict, *, role: str):
        """Exclude a proven incompatible API request from routing statistics, not billing.

        The original attempt and unknown charge remain immutable. This narrowly
        supports the reproduced named-tool Haiku 404; it is not a generic override.
        """
        if role != 'released_development': raise ValueError('development review only')
        body = {k:v for k,v in diagnostic.items() if k != 'diagnostic_digest'}
        if diagnostic.get('diagnostic_digest') != digest_of(body): raise ValueError('invalid diagnostic digest')
        checks = diagnostic.get('checks', [])
        forced = any(isinstance(c.get('tool_choice'), dict) and c['tool_choice'].get('type') == 'function'
            and c.get('status') == 404 and 'tool_choice' in c.get('message', '') for c in checks)
        auto = any(c.get('tool_choice') == 'auto' and c.get('status') == 200 for c in checks)
        endpoints = diagnostic.get('endpoints', [])
        if not forced or not auto or not endpoints or not all(
            e.get('supports_tool_choice', {}).get('function') is False for e in endpoints):
            raise ValueError('diagnostic does not prove named-tool incompatibility')
        events = {digest_of(e):e for e in self.events()}
        attempt = events.get(attempt_digest, {})
        call = events.get(attempt.get('previous_digest'), {})
        if (attempt.get('kind') != 'attempt' or attempt['data'].get('model') != 'anthropic/claude-haiku-5.5'
            or attempt['data'].get('passed') or attempt['data'].get('cost_usd') is not None
            or call.get('kind') != 'call' or call['data'].get('http_status') != 404
            or call['data'].get('step') != 4):
            raise ValueError('attempt is not the diagnosed fourth-call Haiku routing error')
        if any(e.get('kind') == 'routing_review' and e['data'].get('attempt_digest') == attempt_digest
               for e in events.values()): return
        self.append('routing_review', dict(model='anthropic/claude-haiku-5.5',attempt_digest=attempt_digest,
            diagnostic_digest=diagnostic['diagnostic_digest'],reason='unsupported_named_tool_choice',
            billing_resolved=False,role=role))

    def retain(self, root: Path, evidence: dict, candidate: Candidate, verdict: dict, *, role: str):
        if role != 'released_development':
            raise ValueError('only released development repairs may enter memory')
        body = {key: val for key, val in verdict.items() if key != 'verdict_digest'}
        if (verdict.get('verdict_digest') != digest_of(body) or not verdict.get('plausible')
            or verdict.get('stopped_at') != 'passed' or verdict.get('candidate_digest') != candidate.digest):
            raise ValueError('matching sealed full-suite verdict required')
        path = _allowed(root, candidate.path, evidence)
        if not path.resolve().is_relative_to((root / evidence['source_directory']).resolve()):
            raise ValueError('only production repairs retained')
        before = path.read_text().splitlines(keepends=True)
        after = candidate.content.splitlines(keepends=True)
        groups = difflib.SequenceMatcher(None, before, after, autojunk=False).get_grouped_opcodes(3)
        edits = [(''.join(before[g[0][1]:g[-1][2]]), ''.join(after[g[0][3]:g[-1][4]])) for g in groups]
        if not edits or len(edits) > 8 or any(not a or a == b for a, b in edits):
            raise ValueError('repair cannot be represented by bounded exact-text patterns')
        self.append('recipe', dict(family=task_features(evidence)['family'], path=candidate.path, edits=edits,
            explanation=candidate.description, origin=candidate.origin,
            candidate_digest=candidate.digest, verdict=verdict,
            preconditions='matching symptom family; unique production-source context; full-suite revalidation'))

    def candidates(self, root: Path, evidence: dict, limit: int = 2):
        family = task_features(evidence)['family']; found = []; seen = set()
        paths = sorted({item['path'] for item in evidence.get('production_source', [])})
        for event in reversed(self.events()):
            if event['kind'] != 'recipe' or event['data']['family'] != family:
                continue
            recipe = event['data']
            # Exploration can repair a dependency absent from the initial stack trace.
            # Legacy recipes already carry its path in their sealed validator verdict.
            remembered = recipe.get('path') or recipe.get('verdict', {}).get('path')
            candidate_paths = list(dict.fromkeys(paths + ([remembered] if isinstance(remembered, str) else [])))
            for path in candidate_paths:
                try:
                    target = _allowed(root, path, evidence)
                    if not target.resolve().is_relative_to((root / evidence['source_directory']).resolve()):
                        continue
                    candidate = apply_edits(root, path, recipe['edits'], 'retained-experience', recipe['explanation'])
                except (ValueError, OSError):
                    continue  # another project's remembered path may be outside these roots

                if candidate and candidate.digest not in seen:
                    seen.add(candidate.digest); found.append(candidate)
                    if len(found) >= limit: return found
        return found


class EconomicRouter:
    def __init__(self, options: list[ModelOption], experience: RepairExperience, minimum_observed_success_rate: float = .5):
        if not options or len({o.model for o in options}) != len(options):
            raise ValueError('distinct model options required')
        if not math.isfinite(minimum_observed_success_rate) or not 0 <= minimum_observed_success_rate <= 1:
            raise ValueError('invalid observed success threshold')
        self.options, self.experience = options, experience
        self.minimum_observed_success_rate = minimum_observed_success_rate

    def rank(self, evidence: dict, remaining_usd: float, excluded=()):
        if not math.isfinite(remaining_usd) or remaining_usd < 0:
            raise ValueError('invalid budget')
        features = task_features(evidence)
        events = self.experience.events()
        reviewed = {e['data']['attempt_digest'] for e in events if e['kind'] == 'routing_review'}
        attempts = [e['data'] for e in events if e['kind'] == 'attempt' and digest_of(e) not in reviewed]
        # Byte-based estimate deliberately conservative; actual provider invoices are retained.
        estimated_input = len(json.dumps(evidence).encode()) + 8192
        rankings = []
        for option in self.options:
            if option.model in excluded: continue
            observations = [a for a in attempts if a['model'] == option.model]
            contextual = [a for a in observations if a['features']['complexity'] == features['complexity']]
            if any(a['cost_usd'] is None for a in observations): continue
            observations = contextual or [a for a in observations if a['features']['complexity'] == 'any']
            reserve = (estimated_input * option.input_usd_per_million + 4096 * option.output_usd_per_million) / 1e6
            if reserve > remaining_usd: continue
            n = len(observations); passes = sum(a['passed'] for a in observations)
            if n >= 3 and passes/n < self.minimum_observed_success_rate: continue
            probability = (passes + 1) / (n + 2)  # explicit smoothing, not calibrated confidence
            expected_cost = (sum(a['cost_usd'] for a in observations) + reserve) / (n + 1)
            rankings.append(dict(option=option, score=expected_cost/probability,
                estimated_request_reserve_usd=reserve, observations=n, suite_passes=passes,
                complexity=features['complexity'], basis='contextual' if contextual else ('released_comparison' if observations else 'price_prior')))
        return sorted(rankings, key=lambda r: (r['score'], r['option'].model))


class _CallLedger(list):
    def __init__(self, experience):
        super().__init__(); self.experience = experience
    def append(self, call):
        self.experience.append('call', call)
        super().append(call)


def solve_development(root: Path, evidence: dict, router: EconomicRouter, validate_candidate,
                      *, role: str, budget_usd: float = .05, validation_budget: int = 4,
                      max_models: int = 2, proposer_factory=openrouter_proposer, local_proposer=None,
                      local_validation_budget: int = 4, allow_llm: bool = True,
                      max_rounds_per_model: int = 1, fallback_router=None,
                      local_feedback_rounds: int = 1, transformation_policy=None,
                      learn_transformation_proposals: bool = False):
    """Validate memory first, then bounded price/outcome-aware model proposals.

    The supplied validator owns execution authority and must return real full-suite
    verdicts. A checksum alone does not establish an independent scientific proof.
    No candidate is applied permanently and no existing frozen protocol is changed.
    """
    if role != 'released_development': raise ValueError('development-only service')
    if (not math.isfinite(budget_usd) or budget_usd <= 0 or validation_budget <= 0
        or max_models <= 0 or local_validation_budget < 0 or max_rounds_per_model <= 0
        or type(local_feedback_rounds) is not int or local_feedback_rounds <= 0):
        raise ValueError('positive finite budgets required')
    root = Path(root); features = task_features(evidence); ledger = _CallLedger(router.experience)
    history = []; decisions = []; accepted = None; unknown = False
    if transformation_policy is not None:
        if local_proposer is not None: raise ValueError('choose one local proposer')
        from genesis.repair_transformation_learning import proposer
        local_proposer = proposer(transformation_policy)

    def retain(candidate, verdict):
        router.experience.retain(root, evidence, candidate, verdict, role=role)
        if learn_transformation_proposals:
            from genesis.repair_transformation_learning import acquire
            proposal = acquire(router.experience.events(), transformation_policy)
            router.experience.append('transformation_proposal', dict(policy=proposal,
                source_candidate_digest=candidate.digest, promoted=False))

    def check(candidate):
        verdict = validate_candidate(candidate)
        body = {key: val for key, val in verdict.items() if key != 'verdict_digest'}
        if verdict.get('candidate_digest') != candidate.digest or verdict.get('verdict_digest') != digest_of(body):
            raise ValueError('validator returned a mismatched or unsealed verdict')
        router.experience.append('validation', dict(evidence_digest=evidence.get('evidence_digest'),
            features=features, candidate_digest=candidate.digest, origin=candidate.origin, verdict=verdict))
        history.append((candidate, verdict))
        return bool(verdict.get('plausible')) and verdict.get('stopped_at') == 'passed'

    for candidate in router.experience.candidates(root, evidence, min(2, validation_budget)):
        if check(candidate): accepted = candidate; break
    local_used = 0
    for _ in range(local_feedback_rounds):
        if accepted is not None or local_proposer is None: break
        remaining = min(local_validation_budget-local_used, validation_budget-len(history))
        if remaining <= 0: break
        seen = {candidate.digest for candidate, _ in history}
        proposals = local_proposer(root, evidence, tuple(history), remaining)
        fresh = []
        for candidate in proposals:
            if candidate.digest not in seen:
                fresh.append(candidate); seen.add(candidate.digest)
        if not fresh: break
        # One observation at a time in reactive mode; legacy batch mode is unchanged.
        chosen = fresh[:1] if local_feedback_rounds > 1 else fresh[:remaining]
        for candidate in chosen:
            local_used += 1
            if check(candidate):
                retain(candidate, history[-1][1])
                accepted = candidate; break
    tried = set()
    while allow_llm and accepted is None and len(history) < validation_budget and len(tried) < max_models:
        spent = sum(c['cost_usd'] for c in ledger if c.get('cost_usd') is not None)
        if spent >= budget_usd: break
        ranking = router.rank(evidence, budget_usd-spent, tried)
        relaxed = False
        if not ranking and fallback_router is not None:
            ranking = fallback_router.rank(evidence, budget_usd-spent, tried)
            relaxed = bool(ranking)
        if not ranking: break
        decision = ranking[0]; option = decision['option']; tried.add(option.model)
        decisions.append({**{k:v for k,v in decision.items() if k!='option'}, 'model': option.model, 'fallback_quality_threshold_relaxed': relaxed})
        start = len(ledger)
        for _ in range(max_rounds_per_model):
            remaining = budget_usd-sum(c['cost_usd'] for c in ledger if c.get('cost_usd') is not None)
            if remaining <= 0 or len(history) >= validation_budget: break
            proposer = proposer_factory(option.model, 1, ledger, explore=True, max_requests=4,
                max_tokens=4096, max_call_usd=remaining, max_round_usd=remaining,
                max_price=dict(prompt=option.input_usd_per_million, completion=option.output_usd_per_million, request=0),
                reasoning_effort=option.reasoning)
            proposals = proposer(root, evidence, tuple(history), validation_budget-len(history))
            seen = {candidate.digest for candidate, _ in history}
            fresh = [candidate for candidate in proposals if candidate.digest not in seen]
            for candidate in fresh[:validation_budget-len(history)]:
                if check(candidate):
                    retain(candidate, history[-1][1])
                    accepted = candidate; break
            if accepted is not None or not fresh or any(c.get('cost_usd') is None for c in ledger[start:]): break
        current = ledger[start:]; unknown = any(c.get('cost_usd') is None for c in current)
        cost = None if unknown else sum(c['cost_usd'] for c in current)
        router.experience.record_attempt(features, option.model, cost, accepted is not None, role=role)
        if unknown: break  # unknown charges cannot silently become a zero-cost retry
    known_cost = sum(c['cost_usd'] for c in ledger if c.get('cost_usd') is not None)
    return dict(solved=accepted is not None, candidate=accepted, model_calls=list(ledger),
        decisions=decisions, verdicts=[v for _,v in history], unknown_cost=unknown,
        known_cost_usd=known_cost, total_cost_usd=None if unknown else known_cost,
        reuse_without_llm=accepted is not None and accepted.origin == 'retained-experience' and not ledger,
        solved_without_llm=accepted is not None and not ledger, scope='released_development')
