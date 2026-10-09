"""Focus bounded learned/source-observed repair strategies on real bug evidence."""
from __future__ import annotations

import difflib
from pathlib import Path
import tempfile

from genesis import exemplar_strategy
from genesis.repair_bench import Candidate
from genesis.repair_proposers import strategist_proposer
from genesis.repair_search_adaptation import validate_search
from genesis.repair_self_improvement import validate_policy


def _near_failure(before: str, after: str, lines: list[int], radius: int = 40) -> bool:
    changes=[(i1+1,max(i1+1,i2)) for tag,i1,i2,_,_ in
             difflib.SequenceMatcher(None,before.splitlines(),after.splitlines(),autojunk=False).get_opcodes()
             if tag!='equal']
    return bool(changes) and all(any(a-radius<=line<=b+radius for line in lines) for a,b in changes)


def candidate_pool(root:Path,evidence:dict,capabilities:dict,*,pool_budget:int=32) -> dict[str,list[Candidate]]:
    """Only causal production files reach exemplar generation; tests never do."""
    validate_policy(capabilities)
    if type(pool_budget)is not int or not 1<=pool_budget<=128:raise ValueError('bounded pool required')
    root=Path(root).resolve();production=(root/evidence['source_directory']).resolve()
    if not production.is_relative_to(root) or production==root:raise ValueError('production subdirectory required')
    focus={}
    for relative,line in evidence['suspect_locations']:
        if Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('invalid source path')
        source=root/relative
        if (not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(production)
            or source.stat().st_size>512000 or type(line)is not int or line<1):
            raise ValueError('invalid causal production file')
        focus.setdefault(relative,[]).append(line)
    groups={'retained':[],'observed':[],'strategist':[]}
    if not focus:return groups
    with tempfile.TemporaryDirectory(prefix='genesis-source-view-') as temporary:
        view=Path(temporary)
        originals={}
        for relative in sorted(focus):
            originals[relative]=(root/relative).read_text()
            target=view/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(originals[relative])
        generated={
            'retained':exemplar_strategy.generate_from_acquired(view,capabilities['strategies'],max_candidates=512),
            'observed':exemplar_strategy.generate(view,max_candidates=512),
        }
        for name,record in generated.items():
            for item in record['candidates']:
                mutation=item['mutations'][0];path=mutation['path'];content=mutation['content_utf8']
                if path not in focus or not _near_failure(originals[path],content,focus[path]):continue
                candidate=Candidate(path,content,'learned-strategy:'+name,
                    'Bounded '+name+' subscript strategy; delta='+str(item['provenance']['delta']))
                groups[name].append(candidate)
                if len(groups[name])>=pool_budget:break
    groups['strategist']=list(strategist_proposer(pool_budget)(root,evidence,(),pool_budget))
    return groups


def order_pool(groups:dict[str,list[Candidate]],capabilities:dict,search_policy:dict,*,budget:int):
    validate_policy(capabilities);validate_search(search_policy)
    if (search_policy['capability_policy_digest']!=capabilities['policy_digest']
        or type(budget)is not int or not 1<=budget<=32):raise ValueError('bounded matching search policy required')
    names=['retained','observed','strategist'] if search_policy['ordering']=='retained_first' else ['observed','retained','strategist']
    result=[];seen=set()
    for name in names:
        for candidate in groups[name]:
            if candidate.digest not in seen:
                seen.add(candidate.digest);result.append(candidate)
            if len(result)==budget:return result
    return result
