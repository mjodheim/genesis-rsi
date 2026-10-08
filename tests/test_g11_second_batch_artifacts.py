"""Persist negative second prospective batch, with immutable pre-registration."""
import json
from pathlib import Path
import unittest
from genesis.trust_root import digest_of
R=Path(__file__).resolve().parents[1]/'experiment/g11'

class SecondBatchEvidence(unittest.TestCase):
    def test_negative_project_statuses_and_freeze(self):
        m=json.loads((R/'G11_SECOND_BATCH_PREREG_20261008.json').read_text())
        i=json.loads((R/'G11_SECOND_BATCH_FROZEN_INDEX_20261008.json').read_text())
        v=json.loads((R/'G11_SECOND_BATCH_RESULTS_20261008.json').read_text())
        for o, key in ((m,'preregistration_digest'),(i,'index_digest'),(v,'result_digest')):
            self.assertEqual(o[key],digest_of({k:x for k,x in o.items() if k!=key}))
        self.assertEqual(v['preregistration_digest'],m['preregistration_digest'])
        self.assertEqual(v['freeze_digest'],i['full_candidate_freeze_digest'])
        self.assertEqual(v['case_count'],3)
        self.assertEqual([(r['project'],r['bug_id']) for r in v['cases']],
            [('Gson',2),('Jsoup',68),('JacksonCore',11)])
        self.assertEqual(v['cases_solved_per_arm'],
            {'legacy_before_g11':0,'g11_atomics_balancing_sibling_guard':0})
        self.assertTrue(v['no_fixed_revision_or_human_solution'])
        self.assertTrue(all(x['full_suite_valid_unique_candidates']==0 for x in v['cases']))
        self.assertTrue(all(x['original_failure_count']>=1 for x in v['cases']))
