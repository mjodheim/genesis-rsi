"""Locked 0/3 external study can't be retroactively improved by development."""
import json
from pathlib import Path
import unittest
from genesis.trust_root import digest_of
ROOT=Path(__file__).resolve().parents[1]/'experiment/g11'

class IndependentThreeProjectEvidence(unittest.TestCase):
    def test_preserves_preselected_development_failures(self):
        pre=json.loads((ROOT/'G11_3REPO_PREREG_20261008.json').read_text())
        freeze=json.loads((ROOT/'G11_3REPO_FROZEN_INDEX_20261008.json').read_text())
        result=json.loads((ROOT/'G11_3REPO_RESULTS_20261008.json').read_text())
        self.assertEqual(pre['preregistration_digest'],
            digest_of({k:v for k,v in pre.items() if k!='preregistration_digest'}))
        self.assertEqual(freeze['manifest_digest'],
            digest_of({k:v for k,v in freeze.items() if k!='manifest_digest'}))
        self.assertEqual(result['result_digest'],
            digest_of({k:v for k,v in result.items() if k!='result_digest'}))
        self.assertEqual(result['preregistration_digest'], pre['preregistration_digest'])
        self.assertEqual(result['freeze_digest'],freeze['full_candidate_freeze_digest'])
        self.assertEqual(result['case_count'],3)
        self.assertEqual([(x['project'],x['bug_id']) for x in result['cases']],
            [('Math',53),('Csv',16),('Collections',24)])
        self.assertEqual(result['cases_solved_per_arm'],{
          'legacy_unchanged':0,
          'candidate_atomic_first_plus_source_balancing_plus_testname_hints':0,
        })
        for case in result['cases']:
            self.assertGreater(case['original_failure_count'],0)
            self.assertEqual(case['full_suite_valid_unique_candidates'],0)
            self.assertTrue(all(
                r['first_passing_rank'] is None
                for r in case['arms'].values()))
        self.assertTrue(result['no_fixed_revision_or_human_solution'])

if __name__ == '__main__':
    unittest.main()
