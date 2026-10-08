"""Immutable negative third cross-project study, verified against pre-registration."""
import json
from pathlib import Path
import unittest
from genesis.trust_root import digest_of
R=Path(__file__).resolve().parents[1]/'experiment/g11'


class ThirdBlindCaseIntegrity(unittest.TestCase):
    def test_three_separate_new_projects_remain_negative(self):
        prereg=json.loads((R/'G11_THIRD_BATCH_PREREG_20261008.json').read_text())
        freeze=json.loads((R/'G11_THIRD_BATCH_FROZEN_INDEX_20261008.json').read_text())
        res=json.loads((R/'G11_THIRD_BATCH_RESULTS_20261008.json').read_text())
        for item,key in (
            (prereg,'preregistration_digest'),
            (freeze,'index_digest'),
            (res,'result_digest'),
        ):
            self.assertEqual(item[key],digest_of({k:v for k,v in item.items() if k!=key}))
        self.assertEqual(res['preregistration_digest'],prereg['preregistration_digest'])
        self.assertEqual(res['freeze_digest'],freeze['full_freeze_digest'])
        self.assertEqual(res['case_count'],3)
        self.assertEqual([(x['project'],x['bug_id']) for x in res['cases']],
            [('Cli',34),('Time',22),('JxPath',12)])
        self.assertEqual(res['cases_solved_per_arm'],{
            'legacy_operators':0,
            'testbody_source_localization_g11':0,
        })
        self.assertTrue(all(row['original_failure_count']>0 for row in res['cases']))
        self.assertTrue(all(row['full_suite_valid_unique_candidates']==0 for row in res['cases']))
        self.assertTrue(res['no_fixed_revision_or_human_solution'])
        self.assertTrue(res['independent_full_suite_required'])


if __name__=='__main__':
    unittest.main()
