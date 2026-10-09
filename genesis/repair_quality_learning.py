"""Compiler-grounded, attributed repair selection and expression refinement.

An authored substrate, not semantic understanding or autonomous invention.
All project compilation and AST analysis stays in the existing Docker boundary.
"""
from __future__ import annotations

from collections import Counter
import difflib
import json
from pathlib import Path
import re

from genesis.repair_bench import Candidate
from genesis.repair_self_improvement import checked, sealed
from genesis.repair_transformation_learning import _pattern, tokens, validate_policy
from genesis.trust_root import digest_of


def operators(candidate):
    return tuple((candidate.provenance or {}).get('component_operators') or [candidate.origin])


def classify(verdict):
    if verdict.get('plausible') and verdict.get('stopped_at')=='passed':return 'success'
    if verdict.get('stopped_at')=='compile':
        feedback=verdict.get('feedback') or ''
        return 'type' if any(s in feedback for s in ('cannot find symbol','incompatible types','cannot be applied')) else 'syntax_or_other_compile'
    return 'regression' if verdict.get('stopped_at')=='full_suite' else 'behaviour'


def operator_policy(observations):
    counts={}
    for candidate,verdict in observations:
        checked(verdict,'verdict_digest')
        if candidate.digest!=verdict['candidate_digest']:raise ValueError('candidate outcome mismatch')
        for operator in operators(candidate):counts.setdefault(operator,Counter())[classify(verdict)]+=1
    return sealed(dict(schema='genesis-repair-operator-outcome-policy-v1',
        outcomes={k:dict(v) for k,v in sorted(counts.items())},
        observations=len(observations),scope='released development evidence; rank only, never proof'), 'policy_digest')


def rank(candidates, policy, history=()):
    checked(policy,'policy_digest');seen={c.digest for c,_ in history}
    recent=operator_policy(history)['outcomes']
    def score(candidate):
        old=[policy['outcomes'].get(op,{}) for op in operators(candidate)]
        now=[recent.get(op,{}) for op in operators(candidate)]
        compile_risk=sum((v.get('type',0)+v.get('syntax_or_other_compile',0))/(sum(v.values())+2) for v in old+now)
        behaviour_risk=sum(v.get('behaviour',0)+2*v.get('regression',0) for v in now)
        successes=sum(v.get('success',0) for v in old)
        return (compile_risk,behaviour_risk,-successes,len(operators(candidate)))
    return sorted((c for c in candidates if c.digest not in seen),key=score)


def refine(parent):
    """Derive smaller expressions mechanically, retaining the original API names."""
    validate_policy(parent);rules=list(parent['rules']);seen={r['template_digest'] for r in rules}
    for rule in parent['rules']:
        decode=lambda seq:[p.get('literal', 'var'+p.get('bind','')[1:]) for p in seq]
        a=decode(rule['before']);b=decode(rule['after']);pairs=[]
        # A changed comparison inside an if can also occur in a return/assignment.
        if rule['family']=='relational_change' and a[:2]==['if','('] and a[-2:]==[')','{']:
            pairs.append((a[2:-2],b[2:-2]))
        # Find a newly introduced call wrapping a formerly unwrapped expression.
        if rule['family']=='call_structure_change':
            for i in range(len(b)-3):
                if b[i] not in rule['introduced_identifiers']:continue
                if b[i+1]!='(':continue
                depth=1;j=i+2
                while j<len(b) and depth:
                    depth+=(b[j]=='(')-(b[j]==')');j+=1
                if depth:continue
                argument=b[i+2:j-1]
                if len(argument)<3:continue
                matches=[k for k in range(len(a)-len(argument)+1) if a[k:k+len(argument)]==argument]
                if len(matches)!=1:continue
                start=i
                if i>=2 and b[i-1]=='.':start=i-2
                pairs.append((argument,b[start:j]))
        for before,after in pairs:
            pattern=_pattern(' '.join(before),' '.join(after))
            if not pattern:continue
            identity=digest_of(pattern)
            if identity in seen:continue
            rules.append(sealed(dict(**pattern,template_digest=identity,
                source_recipe_digest=rule['source_recipe_digest'],source_candidate_digest=rule['source_candidate_digest'],
                source_verdict_digest=rule['source_verdict_digest'],origin=rule['origin'],explanation=rule['explanation'],
                abstraction='authored expression projection; compiler-node guard required',
                refined_from_rule_digest=rule['rule_digest']),'rule_digest'));seen.add(identity)
    result=sealed(dict(schema=parent['schema'],generation=parent['generation']+1,
        parent_policy_digest=parent['policy_digest'],training_memory_digest=parent['training_memory_digest'],
        rules=rules,rejected=[],promoted=False,scope='released expression proposals; requires separate transfer gate'),'policy_digest')
    return validate_policy(result)


def analyze_sources(sandbox,directory,evidence,*,max_sources=8):
    """Trusted analyser helper plus bounded project AST/type queries, all recorded."""
    tools=sandbox.workspace/'quality-analyzer';tools.mkdir(exist_ok=True)
    helper=Path(__file__).parent/'java_analysis/GenesisJavaAnalyzer.java'
    destination=tools/helper.name
    setup=[]
    if not destination.exists():
        destination.write_bytes(helper.read_bytes())
        build=sandbox.execute(['javac','-proc:none','-d','/work/quality-analyzer','/work/quality-analyzer/GenesisJavaAnalyzer.java'])
        setup.append(build.record())
        if not build.ok:raise ValueError('trusted Java analyser compilation failed')
    cp=sandbox.defects4j('export','-p','cp.compile','-w','/work/'+directory)
    setup.append(cp.record());classpath=cp.output.strip().splitlines()[-1] if cp.ok and cp.output.strip() else ''
    reports={};runs=[]
    for path in sorted({p for p,_ in evidence['suspect_locations']})[:max_sources]:
        source=sandbox.workspace/directory/path
        if source.is_symlink() or not source.resolve().is_relative_to((sandbox.workspace/directory/evidence['source_directory']).resolve()):raise ValueError('invalid analyser source')
        run=sandbox.execute(['java','-Xmx192m','-cp','/work/quality-analyzer','GenesisJavaAnalyzer','/work/'+directory+'/'+path,classpath])
        runs.append(run.record())
        if run.ok:
            try: report=json.loads(run.output)
            except json.JSONDecodeError:continue
            if report.get('schema')=='genesis-java-understanding-v2':reports[path]=report
    return sealed(dict(reports=reports,setup_runs=setup,analysis_runs=runs,
        analysis_compiler_invocations=len(runs),helper_compiler_invocations=sum(r['command'][0]=='javac' for r in setup),
        type_resolution_partial=True,source_only=True),'analysis_digest')


def structural_screen(root,candidates,analysis):
    """Reject only known invalid modifiers; require AST evidence for refinements."""
    checked(analysis,'analysis_digest');accepted=[];rejected=[]
    for candidate in candidates:
        reason=None
        try:seq=[t[0] for t in tokens(candidate.content)]
        except ValueError:seq=[]  # unsupported syntax is inconclusive, not rejected
        if any(seq[i] in {'static','public','private','protected'} and seq[i+1] in {'return','throw','if','while'} for i in range(max(0,len(seq)-1))):
            reason='modifier before statement is invalid Java'
        if candidate.origin.startswith('learned-transformation:'):
            before=(Path(root)/candidate.path).read_text()
            # Match changed span against an existing expression/statement node.
            changes=[(a,b) for tag,a,b,_,_ in difflib.SequenceMatcher(None,before,candidate.content,autojunk=False).get_opcodes() if tag!='equal']
            nodes=analysis['reports'].get(candidate.path,{}).get('nodes',[])
            expressions={'METHOD_INVOCATION','MEMBER_SELECT','NOT_EQUAL_TO','EQUAL_TO','LESS_THAN','GREATER_THAN','LESS_THAN_EQUAL','GREATER_THAN_EQUAL','RETURN','IF','CONDITIONAL_EXPRESSION'}
            supported=[]
            for a,b in changes:
                start=len(before[:a].encode('utf-16-le'))//2;end=len(before[:b].encode('utf-16-le'))//2
                supported.append(any(n.get('kind') in expressions and n['start']<=start and end<=n['end'] and n.get('type') is not None for n in nodes))
            if not supported or not all(supported):reason='no resolved compiler expression node covers edit'
        if reason:rejected.append(dict(candidate_digest=candidate.digest,reason=reason,operators=list(operators(candidate))))
        else:accepted.append(candidate)
    return accepted,sealed(dict(input_candidates=len(candidates),accepted=len(accepted),rejected=rejected,
        compiler_invocations=0,semantic_correctness_proven=False),'screen_digest')


def search(candidates,policy,validator,*,budget=8,reactive=True,record=None):
    """Every attempt includes its compilation: no free compiler screening."""
    history=[];steps=[];accepted=None
    while len(history)<budget:
        pool=rank(candidates,policy,history) if reactive else [c for c in candidates if c.digest not in {a.digest for a,_ in history}]
        if not pool:break
        candidate=pool[0]
        choice=sealed(dict(index=len(history)+1,candidate_digest=candidate.digest,
            operators=list(operators(candidate)),prior_verdict_digests=[v['verdict_digest'] for _,v in history]),'choice_digest')
        if record:record('choice',choice)
        verdict=validator(candidate);checked(verdict,'verdict_digest')
        if verdict['candidate_digest']!=candidate.digest:raise ValueError('validator identity mismatch')
        history.append((candidate,verdict))
        row=dict(choice=choice,candidate=dict(path=candidate.path,candidate_digest=candidate.digest,
            origin=candidate.origin,provenance=candidate.provenance),verdict=verdict,diagnosis=classify(verdict))
        steps.append(row)
        if record:record('attempt',sealed(row,'attempt_digest'))
        if verdict.get('plausible') and verdict.get('stopped_at')=='passed':accepted=candidate;break
    return dict(solved=accepted is not None,steps=steps,validated=len(history),
        candidate_compilations=len(history),accepted=accepted,external_model_calls=0,api_cost_usd=0)
