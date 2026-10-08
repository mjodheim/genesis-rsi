#!/usr/bin/env python3
"""Post-hoc Math-53 development replay. Not a previously unseen test."""
from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis import repair_strategist
from genesis.failure_localization import prioritize
from genesis.trust_root import digest_of
from scripts.g11_three_repo_repair_eval import paths_for_case, validate, _d4j_export

ROOT_BUGGY=Path('/home/anthony/benchmarks/g11-fresh-three-20261008/Math-53-buggy')
OUT=ROOT/'experiment/g11/G11_MATH53_POSTHOC_REPAIR_20261008.json'

def main():
    source_prefix = _d4j_export(ROOT_BUGGY,'dir.src.classes')[-1]
    paths=paths_for_case('Math',53,ROOT_BUGGY,source_prefix)
    hints=prioritize((ROOT_BUGGY/'failing_tests').read_text(),paths)
    settings=dict(include_prefixes=[source_prefix],focus_paths=paths,max_candidates=80,per_family_budget=80,
                  composition_fraction=0.4,source_balance_experimental=True,
                  atomic_first_experimental=True,priority_focus_paths=hints['matched_source_paths'])
    plain=repair_strategist.generate(ROOT_BUGGY,**settings)
    updated=repair_strategist.generate(ROOT_BUGGY,**settings,sibling_guard_experimental=True)
    op='java_transfer_sibling_invalid_state_guard'
    first=next((i for i,c in enumerate(updated['candidates'],1)
                if c['plan']['component_operators']==[op]),None)
    if first is None or first>8:
        raise RuntimeError('G11 guard transfer outside candidate validation window')
    case=updated['candidates'][first-1]
    frozen={
        'schema':'genesis-g11-math53-posthoc-development-freeze-v1',
        'project':'Math','bug_id':53,
        'original_negative_holdout_digest':json.loads((ROOT/'experiment/g11/G11_3REPO_RESULTS_20261008.json').read_text())['result_digest'],
        'candidate_index_digest':updated['strategy_digest'],
        'previous_candidate_index_digest':plain['strategy_digest'],
        'rank':first,
        'source_file':case['path'],
        'operator':op,
        'source_digest':case['expected_sha256'],
        'candidate_digest':case['candidate_digest'],
        'known_exposed_case':True,
        'human_patch_consulted':False,
    }
    fd=digest_of(frozen)
    triggers=[line.removeprefix('--- ').strip()
              for line in (ROOT_BUGGY/'failing_tests').read_text().splitlines()
              if line.startswith('--- ')]
    result=validate(ROOT_BUGGY,case['path'],case['content_utf8'],case['expected_sha256'],triggers)
    body={
        'schema':'genesis-g11-math53-development-replay-v1',
        'freeze':frozen,'freeze_digest':fd,'validator':result,
        'full_suite_passed':result.get('full_suite_pass') is True,
        'independent_holdout_success_count':0,
        'candidate_was_generated_before_validation':True,
        'claim':'posthoc development repair only; human authored operator family',
    }
    value={**body,'result_digest':digest_of(body)}
    OUT.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    print('POSTHOC_MATH_RANK',first,'FULL_SUITE_PASS',body['full_suite_passed'],'OUTPUT',OUT,flush=True)

if __name__=='__main__':
    main()
