"""Verified insertion acquisition with explicit supplied contracts, not inferred semantics."""
from pathlib import Path
import re
from genesis.repair_bench import Candidate
from genesis.repair_self_improvement import checked,sealed
from genesis.repair_transformation_learning import tokens
from genesis.trust_root import digest_of

SCHEMA='genesis-contract-repair-policy-v1'
_PRIMITIVES={'boolean','byte','short','int','long','float','double','char'}


def acquire(events):
    rules=[];rejected=[]
    for event in events:
        if event.get('kind')!='recipe':continue
        data=event['data'];verdict=data['verdict'];checked(verdict,'verdict_digest')
        if event.get('scope')!='released_development' or not verdict.get('plausible') or verdict.get('stopped_at')!='passed' or verdict['candidate_digest']!=data['candidate_digest']:
            raise ValueError('verified released recipe required')
        for before,after in data['edits']:
            try:
                left=[t[0] for t in tokens(before)];right=tokens(after)
            except ValueError:continue
            seq=[t[0] for t in right];removed=set();checks=[];i=0
            while i<len(seq)-12:
                if seq[i:i+2]!=['if','('] or not re.fullmatch(r'[A-Za-z_$][\w$]*',seq[i+2]):i+=1;continue
                if seq[i+3:i+10]!=['==','null',')','{','throw','new','NullPointerException']:i+=1;continue
                j=i+10
                if seq[j]!='(':i+=1;continue
                j+=1
                if j<len(seq) and right[j][1]=='literal':j+=1
                if seq[j:j+3]!=[')',';','}']:i+=1;continue
                end=j+3;checks.append(seq[i+2]);removed.update(range(i,end));i=end
            constructor_parameters=set()
            for start in range(1,len(seq)-2):
                if seq[start-1] not in {'public','protected','private'} or seq[start+1]!='(':continue
                try:finish=seq.index(')',start+2)
                except ValueError:continue
                if finish+1>=len(seq) or seq[finish+1]!='{':continue
                parts=' '.join(seq[start+2:finish]).split(',')
                for part in parts:
                    names=part.split()
                    if names and names[0]=='final':names=names[1:]
                    if len(names)==2 and names[0] not in _PRIMITIVES:constructor_parameters.add(names[-1])
            if checks and set(checks)<=constructor_parameters and [s for j,s in enumerate(seq) if j not in removed]==left:
                if len(rules)>=32:raise ValueError('rule bound exceeded')
                rules.append(sealed(dict(kind='constructor_reference_nonnull',source_recipe_digest=digest_of(event),
                    source_candidate_digest=data['candidate_digest'],source_verdict_digest=verdict['verdict_digest'],
                    origin=data['origin'],training_checked_parameters=checks,
                    projection='authored reference-parameter binding; omit diagnostic message',
                    guards=['explicit nonnull contract','constructor reference parameter','no existing conditional or throw',
                        'no explicit constructor delegation','full-suite revalidation']), 'rule_digest'))
            else:rejected.append(dict(source_recipe_digest=digest_of(event),reason='not pure supported null-check insertion'))
    return sealed(dict(schema=SCHEMA,rules=rules,rejected=rejected,training_memory_digest=digest_of(events),promoted=False),'policy_digest')


def validate_policy(policy):
    checked(policy,'policy_digest')
    if policy.get('schema')!=SCHEMA or not isinstance(policy.get('rules'),list) or len(policy['rules'])>32:raise ValueError('invalid policy')
    for rule in policy['rules']:
        checked(rule,'rule_digest')
        if rule.get('kind')!='constructor_reference_nonnull':raise ValueError('unsupported rule')
    return policy


def generate(root,evidence,policy,contracts,*,limit=16):
    """contracts[path][constructor] names required non-null; no tests/expected values read.

    Types are conservatively recognised lexically. Contracts remain caller-supplied;
    no nullability inference, overload-specific contract proof or policy promotion.
    """
    validate_policy(policy)
    if type(limit) is not int or not 1<=limit<=32:raise ValueError('bounded limit required')
    root=Path(root).resolve();production=(root/evidence['source_directory']).resolve()
    if production==root or not production.is_relative_to(root):raise ValueError('production boundary required')
    candidates=[];seen=set()
    for path,names in contracts.items():
        target=root/path
        if Path(path).is_absolute() or '..' in Path(path).parts or target.is_symlink() or not target.resolve().is_relative_to(production):raise ValueError('invalid production path')
        if not target.is_file() or target.suffix!='.java' or target.stat().st_size>512000:continue
        text=target.read_text()
        try:seq=tokens(text)
        except ValueError:continue
        values=[t[0] for t in seq]
        declared={values[i+1] for i in range(len(values)-1) if values[i]=='class'}
        for i in range(1,len(values)-2):
            name=values[i]
            if name not in declared or name not in names or values[i+1]!='(' or values[i-1] not in {'public','protected','private','{','}',';'}:continue
            try:j=values.index(')',i+2)
            except ValueError:continue
            if j+1>=len(values) or values[j+1]!='{':continue
            params=[];part=[]
            for item in values[i+2:j]+[',']:
                if item==',':
                    if part and part[0]=='final':part=part[1:]
                    if len(part)!=2 or not all(re.fullmatch(r'[A-Za-z_$][\w$]*',p) for p in part):params=[];break
                    params.append((part[0],part[1]));part=[]
                else:part.append(item)
            required=names[name]
            if not isinstance(required,list) or not required or len(required)>8 or any(not isinstance(n,str) for n in required):raise ValueError('bounded explicit parameter contract required')
            reference={n for t,n in params if t not in _PRIMITIVES}
            if not set(required)<=reference:continue
            depth=1;k=j+2
            while k<len(values) and depth:
                depth+=(values[k]=='{')-(values[k]=='}');k+=1
            body=values[j+2:k-1]
            if depth or any(v in {'if','throw','super','this'} and (v in {'if','throw'} or index+1<len(body) and body[index+1]=='(') for index,v in enumerate(body)):continue
            for rule in policy['rules']:
                insertion='\n'+''.join('        if ('+n+' == null) { throw new NullPointerException(); }\n' for n in dict.fromkeys(required))
                position=seq[j+1][3]
                candidate=Candidate(path,text[:position]+insertion+text[position:],
                    'learned-contract:'+rule['rule_digest'],'Explicit nonnull constructor contract from '+rule['origin'],
                    provenance=dict(component_operators=['learned_constructor_nonnull'],rule_digest=rule['rule_digest'],
                        supplied_contract=dict(constructor=name,parameters=required),semantic_guard_inferred=False))
                if candidate.digest not in seen:candidates.append(candidate);seen.add(candidate.digest)
                if len(candidates)>=limit:return candidates
    return candidates
