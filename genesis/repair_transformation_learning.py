"""Learn bounded lexical Java edit templates from verified released experience.

This authored abstraction substrate is neither a Java AST nor semantic inference.
Identifier-renaming transfer and executable counterexamples must be measured
separately from exact replay. External-model repair origins remain attributed.
"""
from __future__ import annotations

import difflib
from pathlib import Path
import re

from genesis.repair_bench import Candidate
from genesis.repair_self_improvement import checked, sealed
from genesis.trust_root import digest_of

SCHEMA = 'genesis-java-lexical-repair-policy-v1'
_TOKEN = re.compile(r'(?P<skip>\s+|//[^\n]*|/\*[\s\S]*?\*/)|(?P<literal>"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\')|(?P<id>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<number>\d+(?:\.\d+)?[A-Za-z]*)|(?P<op>>>>=|>>=|<<=|>>>|>>|<<|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|%=|&=|\|=|\^=|->|::|[{}()\[\];,.?:@~!+*/%&|^<>=-])')
_KEYWORDS = set('abstract assert boolean break byte case catch char class const continue default do double else enum extends final finally float for goto if implements import instanceof int interface long native new package private protected public return short static strictfp super switch synchronized this throw throws transient try void volatile while true false null'.split())


def tokens(text: str) -> list[tuple[str, str, int, int]]:
    """Positions retain source boundaries; unsupported lexical input fails closed."""
    result = []; end = 0
    for match in _TOKEN.finditer(text):
        if match.start() != end: raise ValueError('unsupported Java lexical input')
        end = match.end()
        if match.lastgroup != 'skip': result.append((match.group(), match.lastgroup, match.start(), end))
    if end != len(text): raise ValueError('unsupported Java lexical input')
    return result


def _pattern(before: str, after: str) -> dict | None:
    left = tokens(before); right = tokens(after)
    if not 3 <= len(left) <= 100 or not right or len(right) > 140: return None
    a = [t[0] for t in left]; b = [t[0] for t in right]
    if a == b: return None
    # Preserve API/member/class names. Bind only shared unqualified variable names.
    fixed = set(_KEYWORDS)
    for seq in (left, right):
        for index, token in enumerate(seq):
            if token[1] == 'id' and (token[0][0].isupper()
                or index and seq[index-1][0] in {'.', '::'}
                or index+1 < len(seq) and seq[index+1][0] == '('): fixed.add(token[0])
    shared = {t[0] for t in left if t[1] == 'id'} & {t[0] for t in right if t[1] == 'id'}
    bindings = {name: '$'+str(index) for index, name in enumerate(dict.fromkeys(
        t[0] for t in left if t[0] in shared and t[0] not in fixed))}
    if not bindings: return None  # constant-only edits are retained as exact recipes
    encode = lambda seq: [dict(bind=bindings[t[0]]) if t[0] in bindings else dict(literal=t[0]) for t in seq]
    operators = {'<', '>', '<=', '>=', '==', '!='}
    family = 'relational_change' if set(a)^set(b) <= operators else (
        'call_structure_change' if b.count('(') != a.count('(') else 'expression_change')
    return dict(before=encode(left), after=encode(right), family=family,
        introduced_identifiers=sorted({t[0] for t in right if t[1]=='id'}-{t[0] for t in left if t[1]=='id'}),
        guards=['Java production only', 'near observed failure', 'consistent identifier binding',
                'API and literal tokens preserved', 'introduced identifiers already occur in source',
                'compile, triggering tests and full-suite revalidation required'])


def acquire(events: list[dict], parent: dict | None = None) -> dict:
    """Extract proposals from full-suite-passing recipes; do not promote a policy."""
    if parent is not None: validate_policy(parent)
    rules = list(parent['rules']) if parent else []; seen = {r['template_digest'] for r in rules}
    rejected = []
    for event in events:
        if event.get('kind') != 'recipe': continue
        if event.get('scope') != 'released_development': raise ValueError('released development experience required')
        data = event['data']; verdict = data['verdict']; checked(verdict, 'verdict_digest')
        if not verdict.get('plausible') or verdict.get('stopped_at') != 'passed' or verdict.get('candidate_digest') != data['candidate_digest']:
            raise ValueError('only verified full-suite recipes may teach')
        if not data.get('path', verdict.get('path', '')).endswith('.java'): continue
        for before, after in data['edits']:
            left = before.splitlines(keepends=True); right = after.splitlines(keepends=True)
            for tag, a, b, c, d in difflib.SequenceMatcher(None,left,right,autojunk=False).get_opcodes():
                if tag == 'equal': continue
                if tag != 'replace' or max(b-a,d-c)>4:
                    rejected.append(dict(recipe_digest=digest_of(event),reason='not a bounded replacement')); continue
                try: pattern = _pattern(''.join(left[a:b]), ''.join(right[c:d]))
                except ValueError: pattern = None
                if pattern is None:
                    rejected.append(dict(recipe_digest=digest_of(event),reason='unsupported or nongeneralizable edit')); continue
                identity=digest_of(pattern)
                if identity in seen: continue
                if len(rules)>=64: raise ValueError('bounded transformation store full')
                rules.append(sealed(dict(**pattern, template_digest=identity,
                    source_recipe_digest=digest_of(event), source_candidate_digest=data['candidate_digest'],
                    source_verdict_digest=verdict['verdict_digest'], origin=data['origin'],
                    explanation=data['explanation'], abstraction='authored lexical identifier binding; not semantic invention'), 'rule_digest'))
                seen.add(identity)
    return sealed(dict(schema=SCHEMA,generation=parent['generation']+1 if parent else 1,
        parent_policy_digest=parent['policy_digest'] if parent else '',
        training_memory_digest=digest_of(events),rules=rules,rejected=rejected,
        promoted=False,scope='released development proposal; requires separate transfer gate'), 'policy_digest')


def validate_policy(policy):
    checked(policy,'policy_digest')
    if policy.get('schema') != SCHEMA or type(policy.get('generation')) is not int or policy['generation']<1:
        raise ValueError('invalid transformation policy')
    if not isinstance(policy.get('rules'),list) or len(policy['rules'])>64: raise ValueError('invalid rule bound')
    identities=set()
    for rule in policy['rules']:
        checked(rule,'rule_digest')
        pattern={k:rule[k] for k in ('before','after','family','introduced_identifiers','guards')}
        if digest_of(pattern)!=rule['template_digest'] or rule['template_digest'] in identities:
            raise ValueError('invalid or duplicate template')
        identities.add(rule['template_digest']);bound=set()
        for part in rule['before']:
            if set(part)=={'bind'} and re.fullmatch(r'\$\d+',part['bind']): bound.add(part['bind'])
            elif set(part)!={'literal'} or not isinstance(part['literal'],str): raise ValueError('invalid pattern')
        if not bound or not 3<=len(rule['before'])<=100 or not 1<=len(rule['after'])<=140:
            raise ValueError('invalid pattern bound')
        for part in rule['after']:
            if set(part)=={'bind'} and part['bind'] in bound: continue
            if set(part)!={'literal'} or not isinstance(part['literal'],str): raise ValueError('unbound replacement')
    return policy


def generate(root: Path, evidence: dict, policy: dict, *, limit: int = 32) -> list[Candidate]:
    validate_policy(policy)
    if type(limit) is not int or not 1<=limit<=128: raise ValueError('bounded candidate limit required')
    root=Path(root).resolve();production=(root/evidence['source_directory']).resolve()
    if production==root or not production.is_relative_to(root): raise ValueError('production boundary required')
    focus={}
    for path,line in evidence['suspect_locations']:
        source=root/path
        if Path(path).is_absolute() or '..' in Path(path).parts or source.is_symlink() or not source.resolve().is_relative_to(production):
            raise ValueError('invalid causal production path')
        if type(line) is not int or line<1: raise ValueError('invalid causal line')
        if source.is_file() and source.suffix=='.java' and source.stat().st_size<=512000:
            focus.setdefault(path,[]).append(line)
    # Bounded production symbol inventory: syntactic existence, not type proof.
    available=set()
    for source in sorted(production.rglob('*.java'))[:256]:
        if source.is_symlink() or not source.resolve().is_relative_to(production) or source.stat().st_size>512000: continue
        try: available.update(t[0] for t in tokens(source.read_text()) if t[1]=='id')
        except (ValueError, OSError): continue
    found=[];seen=set()
    for path in sorted(focus):
        text=(root/path).read_text()
        try: seq=tokens(text)
        except ValueError: continue
        identifiers={t[0] for t in seq if t[1]=='id'}
        for rule in policy['rules']:
            if not set(rule['introduced_identifiers']) <= (identifiers | available): continue
            pattern=rule['before'];size=len(pattern)
            for start in range(len(seq)-size+1):
                segment=seq[start:start+size];bindings={};match=True
                for part,token in zip(pattern,segment):
                    if 'literal' in part:
                        if part['literal']!=token[0]: match=False;break
                    else:
                        if token[1]!='id' or token[0] in _KEYWORDS: match=False;break
                        key=part['bind']
                        if key in bindings and bindings[key]!=token[0]: match=False;break
                        if key not in bindings and token[0] in bindings.values(): match=False;break
                        bindings[key]=token[0]
                if not match: continue
                begin=segment[0][2];end=segment[-1][3];line=text.count('\n',0,begin)+1
                if not any(abs(line-location)<=40 for location in focus[path]): continue
                # Comments inside the replacement are meaningful source; preserve by declining.
                span=text[begin:end]
                if '//' in span or '/*' in span: continue
                replacement=' '.join(bindings[p['bind']] if 'bind' in p else p['literal'] for p in rule['after'])
                candidate=Candidate(path,text[:begin]+replacement+text[end:],
                    'learned-transformation:'+rule['rule_digest'],
                    'Hypothesis '+rule['family']+' from '+rule['origin']+'; full-suite validation required')
                if candidate.digest not in seen:
                    found.append(candidate);seen.add(candidate.digest)
                if len(found)>=limit:return found
    return found


def feedback_order(candidates, history, *, limit=32):
    """Revise selection using own compiler/behavioural outcomes, never an oracle.

    This does not infer a fix from an assertion. It avoids repeated invalid
    symbols, then favours a different hypothesis/location after a failed test.
    """
    tried={c.digest for c,_ in history};bad_symbols=set();failed_origins=set();failed_paths=set()
    for candidate,verdict in history:
        if verdict['stopped_at']=='compile':
            bad_symbols.update(re.findall(r'symbol:\s+(?:variable|class|method)\s+(\w+)',verdict.get('feedback') or ''))
        elif verdict['stopped_at'] in {'failing_tests','full_suite'}:
            failed_origins.add((candidate.origin,candidate.description));failed_paths.add(candidate.path)
    def score(candidate):
        # Do not suppress candidates outright: the next edit might restore a symbol.
        penalty=sum(bool(re.search(r'\b'+re.escape(symbol)+r'\b',candidate.content)) for symbol in bad_symbols)
        return (penalty,(candidate.origin,candidate.description) in failed_origins,candidate.path in failed_paths)
    remaining=[c for c in candidates if c.digest not in tried]
    return sorted(remaining,key=score)[:limit]


def search(root, evidence, policy, memory, local_candidates, validate, *, budget=8, reactive=True, record=None):
    """Memory first, proposed transformations then existing operators, bounded.

    A fixed parent passes policy=None and reactive=False. The child recomputes
    the next choice after every own outcome. The caller owns validation and
    promotion; no evaluator code or test is mutated here.
    """
    if type(budget) is not int or not 1<=budget<=32: raise ValueError('bounded validation budget required')
    exact=list(memory.candidates(root,evidence,2))
    learned=generate(root,evidence,policy,limit=32) if policy else []
    pool=[];seen=set()
    for candidate in exact+learned+list(local_candidates):
        if candidate.digest not in seen: pool.append(candidate);seen.add(candidate.digest)
    history=[];steps=[];accepted=None
    while len(history)<budget:
        remaining=feedback_order(pool,history) if reactive else [c for c in pool if c.digest not in {a.digest for a,_ in history}]
        if not remaining:break
        candidate=remaining[0]
        choice=sealed(dict(index=len(history)+1,candidate_digest=candidate.digest,
            prior_verdict_digests=[v['verdict_digest'] for _,v in history],
            selection='feedback revised' if reactive and history else 'initial priority',
            remaining_pool_size=len(remaining)), 'choice_digest')
        if record:record('choice',choice)
        verdict=validate(candidate);checked(verdict,'verdict_digest')
        if verdict['candidate_digest']!=candidate.digest:raise ValueError('validator candidate mismatch')
        history.append((candidate,verdict))
        row=dict(choice=choice,candidate=dict(path=candidate.path,origin=candidate.origin,
            description=candidate.description,candidate_digest=candidate.digest),verdict=verdict)
        steps.append(row)
        if record:record('attempt',sealed(row,'attempt_digest'))
        if verdict.get('plausible') and verdict.get('stopped_at')=='passed':accepted=candidate;break
    return dict(solved=accepted is not None,steps=steps,validated=len(history),
        exact_candidates=len(exact),learned_candidates=len(learned),pool_candidates=len(pool),
        accepted=accepted,external_model_calls=0,api_cost_usd=0,reactive=reactive)


def proposer(policy, *, pool_budget=32):
    """Explicit opt-in bridge to adaptive repair's iterative local phase."""
    validate_policy(policy)
    from genesis.repair_proposers import strategist_proposer
    cached={}
    def propose(root,evidence,history,remaining):
        identity=(str(Path(root).resolve()),evidence.get('evidence_digest',digest_of(evidence)))
        if identity not in cached:
            pool=generate(root,evidence,policy,limit=pool_budget)
            pool+=list(strategist_proposer(pool_budget)(root,evidence,(),pool_budget))
            unique={}
            for candidate in pool:unique.setdefault(candidate.digest,candidate)
            cached[identity]=list(unique.values())
        return feedback_order(cached[identity],history,limit=min(remaining,pool_budget))
    return propose
