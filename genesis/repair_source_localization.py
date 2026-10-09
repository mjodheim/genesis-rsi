"""Bounded static API-call localisation when assertions yield no production frame.

Expected literals are opaque. Hypotheses are not runtime coverage or causal proof.
"""
from pathlib import Path
import re
from genesis.repair_transformation_learning import tokens
from genesis.trust_root import digest_of


def _safe(root,base,relative):
    path=root/relative
    return (not Path(relative).is_absolute() and '..' not in Path(relative).parts and not path.is_symlink()
        and path.is_file() and path.resolve().is_relative_to((root/base).resolve()) and path.stat().st_size<=512000)


def _method_span(seq,name):
    for i in range(1,len(seq)-1):
        if seq[i][0]!=name or seq[i+1][0]!='(' or seq[i-1][0] in {'.','new'}:continue
        depth=1;j=i+2
        while j<len(seq) and depth:
            depth+=(seq[j][0]=='(')-(seq[j][0]==')');j+=1
        while j<len(seq) and seq[j][0] not in {'{',';','=',')'}:j+=1
        if j>=len(seq) or seq[j][0]!='{':continue
        first=j;depth=1;j+=1
        while j<len(seq) and depth:
            depth+=(seq[j][0]=='{')-(seq[j][0]=='}');j+=1
        if not depth:yield seq[i][2],seq[first][3],seq[j-1][2]


def enrich(root,evidence,*,max_files=6,max_locations=12):
    """Add source hypotheses only if legacy localisation is empty/first-line fallback."""
    from genesis.repair_bench import _excerpts
    root=Path(root).resolve();source=evidence['source_directory'];tests=evidence['test_directory']
    if evidence.get('suspects_from_stack_trace') or (evidence['suspect_locations'] and any(line>1 for _,line in evidence['suspect_locations'])):return evidence
    if not 1<=max_files<=8 or not 1<=max_locations<=16:raise ValueError('bounded localisation required')
    production=(root/source).resolve();test_root=(root/tests).resolve()
    if production==root or test_root==root or not production.is_relative_to(root) or not test_root.is_relative_to(root):raise ValueError('production/test boundary required')
    index={}
    for path in sorted(production.rglob('*.java'))[:2000]:
        relative=str(path.relative_to(root))
        if _safe(root,source,relative):index.setdefault(path.stem,[]).append(relative)
    references=[]
    for test in evidence['failing_tests'][:4]:
        classname,sep,method=test.partition('::')
        if not sep or not re.fullmatch(r'[\w.$]+',classname) or not re.fullmatch(r'\w+',method):continue
        path=tests+'/'+classname.split('$')[0].replace('.','/')+'.java'
        if not _safe(root,tests,path):continue
        text=(root/path).read_text()
        try:seq=tokens(text)
        except ValueError:continue
        spans=list(_method_span(seq,method))
        if not spans:continue
        _,start,end=spans[0];body=[t for t in seq if start<=t[2]<end]
        variables={}
        for i in range(len(body)-2):
            if body[i][1]=='id' and body[i][0] in index and body[i+1][1]=='id' and body[i+2][0] in {'=',';',','}:
                variables[body[i+1][0]]=body[i][0]
        for i in range(len(body)-3):
            owner=None;callee=None
            if body[i+1][0]=='.' and body[i+2][1]=='id' and body[i+3][0]=='(':
                owner=variables.get(body[i][0],body[i][0]);callee=body[i+2][0]
            elif body[i][0]=='new' and body[i+1][0] in index and body[i+2][0]=='(':
                owner=body[i+1][0];callee=owner
            if owner in index:references.append((owner,callee,test))
    locations=[];provenance=[];files=set()
    for owner,method,test in references:
        # Ambiguous same-name classes are not silently resolved by filename.
        if len(index[owner])!=1:continue
        relative=index[owner][0]
        if relative not in files and len(files)>=max_files:continue
        text=(root/relative).read_text()
        try:seq=tokens(text)
        except ValueError:continue
        for begin,body,end in _method_span(seq,method):
            line=text.count('\n',0,begin)+1
            if (relative,line) not in locations:
                locations.append((relative,line));files.add(relative)
                provenance.append(dict(path=relative,line=line,owner=owner,method=method,failing_test=test,
                    hypothesis='declared production method called by failing test; static, not executed coverage'))
            if len(locations)>=max_locations:break
        if len(locations)>=max_locations:break
    if not locations:return evidence
    body={k:v for k,v in evidence.items() if k!='evidence_digest'}
    body.update(suspect_locations=[list(x) for x in locations],production_source=_excerpts(root,locations,80,48000),
        original_evidence_digest=evidence['evidence_digest'],static_localization=dict(method='test API method references; literals excluded',
            references=provenance,source_files=len(files),runtime_coverage=False))
    return {**body,'evidence_digest':digest_of(body)}
