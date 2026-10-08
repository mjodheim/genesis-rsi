#!/usr/bin/env python3
"""Posthoc CSV parser stateful iterator development repair (not blind)."""
from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis import repair_strategist
from genesis.failure_localization import prioritize
from genesis.trust_root import digest_of
from scripts.g11_three_repo_repair_eval import (
    paths_for_case,validate,_d4j_export,
)

PROJECT=Path('/home/anthony/benchmarks/g11-fresh-three-20261008/Csv-16-buggy')
REPORT=ROOT/'experiment/g11/G11_CSV16_POSTHOC_REPAIR_20261008.json'

def main():
    src=_d4j_export(PROJECT,'dir.src.classes')[-1]
    focus=paths_for_case('Csv',16,PROJECT,src)
    hints=prioritize((PROJECT/'failing_tests').read_text(),focus)
    opts={
        'include_prefixes':[src], 'focus_paths':focus,
        'max_candidates':100, 'per_family_budget':100,
        'composition_fraction':0.4,
        'source_balance_experimental':True,
        'atomic_first_experimental':True,
        'priority_focus_paths':hints['matched_source_paths'],
    }
    baseline=repair_strategist.generate(PROJECT,**opts)
    enhanced=repair_strategist.generate(PROJECT,**opts,stream_iterator_experimental=True)
    op='java_reuse_stateful_stream_iterator'
    rank=next((idx for idx,item in enumerate(enhanced['candidates'],1)
        if item['plan']['component_operators']==[op]),None)
    if rank is None or rank>12:
        raise RuntimeError('new operator missing from top-12')
    selected=enhanced['candidates'][rank-1]
    original=json.loads((ROOT/'experiment/g11/G11_3REPO_RESULTS_20261008.json').read_text())
    sealed={
        'schema':'genesis-csv16-posthoc-development-guard-v1',
        'known_bug_project':'Csv','known_bug_id':16,
        'original_independent_negative_report_digest':original['result_digest'],
        'operator':op,
        'first_passing_rank_hypothesis':rank,
        'candidate_digest':selected['candidate_digest'],
        'original_buggy_sha256':selected['expected_sha256'],
        'path':selected['path'],
        'baseline_index_digest':baseline['strategy_digest'],
        'new_index_digest':enhanced['strategy_digest'],
        'human_fixed_source_seen':False,
        'human_implemented_operator':True,
        'exposed_development_case':True,
    }
    frozen=digest_of(sealed)
    public_triggers=[
        line.removeprefix('--- ').strip()
        for line in (PROJECT/'failing_tests').read_text().splitlines()
        if line.startswith('--- ')
    ]
    result=validate(PROJECT,selected['path'],selected['content_utf8'],
                    selected['expected_sha256'],public_triggers)
    body={
        'schema':'genesis-g11-csv16-posthoc-development-repair-v1',
        'freeze':sealed,'freeze_digest':frozen,
        'independent_full_project_validation':result,
        'full_suite_passed':result.get('full_suite_pass',False),
        'blind_successes_counted':0,
        'claim':'assistant-engineered reusable operator, previously examined development defect',
    }
    value={**body,'result_digest':digest_of(body)}
    REPORT.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print('CSV16_DEVELOPMENT_REPLAY_RANK',rank,
          'FULL_SUITE',value['full_suite_passed'],'file',REPORT,flush=True)

if __name__=='__main__':
    main()
