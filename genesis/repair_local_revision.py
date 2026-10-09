"""Single-component proposal constraints; development gains do not prove RSI."""
from genesis.repair_lineage import checked_genome,genome_digest,write_successor
from genesis.repair_self_improvement import sealed

ALLOWED=('instructions','playbook','evidence.radius','evidence.max_locations',
         'evidence.trace_lines','evidence.test_source','search.inspection_requests',
         'search.candidates_per_round','search.rounds')


def changed_leaves(parent,child):
    parent=checked_genome(parent);child=checked_genome(child);changed=[]
    for name,value in parent.items():
        if isinstance(value,dict):
            changed.extend(name+'.'+key for key,item in value.items() if child[name][key]!=item)
        elif child[name]!=value:changed.append(name)
    return sorted(changed)


def propose(parent,report,envelope,ledger,*,transport=None):
    parent=checked_genome(parent)
    constraint=('\n\nLocal revision constraint: change EXACTLY ONE leaf from this list: '+', '.join(ALLOWED)+
        '. Copy every other value exactly, including system and improver. Do not rewrite several sections. '
        'Tie your single change to the supplied training observations. A complete unchanged copy is not a successor.')
    written=write_successor(parent,report,envelope,ledger,improver=parent['improver']+constraint,
        transport=transport,max_tokens=6000)
    child=written['genome'];changes=changed_leaves(parent,child) if child else []
    valid=child is not None and len(changes)==1 and changes[0] in ALLOWED
    return sealed(dict(parent_digest=genome_digest(parent),proposed_genome=child,
        genome=child if valid else None,changed_leaves=changes,accepted_for_measurement=valid,
        reason='single_allowed_leaf' if valid else 'no_valid_single_leaf_revision',
        rationale=written['rationale'],calls=written['calls'],external_model_origin=envelope.model,
        constraint='human-authored single-leaf boundary; no active promotion',promoted=False),'proposal_digest')


def paired_summary(rows):
    identities=set();parent=child=gains=losses=0;cost=0;unknown=0
    for row in rows:
        key=(row['case'],row['replicate'])
        if key in identities:raise ValueError('duplicate case replicate')
        identities.add(key)
        a=row['parent'];b=row['child'];parent+=bool(a['solved']);child+=bool(b['solved'])
        gains+=bool(b['solved'] and not a['solved']);losses+=bool(a['solved'] and not b['solved'])
        for arm in (a,b):
            for call in arm['calls']:
                if call.get('cost_usd') is None:unknown+=1
                else:cost+=call['cost_usd']
    return dict(parent_solved=parent,child_solved=child,case_runs=len(rows),gains=gains,losses=losses,
        known_api_cost_usd=cost,unknown_cost_calls=unknown,
        warrants_larger_test=child>parent and losses==0,policy_promoted=False,
        interpretation='small exposed development pilot; not a generality or independent RSI test')
