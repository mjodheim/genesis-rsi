"""Prevent dev CSV-16 fix being misreported as independent autonomous proof."""
import json
from pathlib import Path
import unittest
from genesis.trust_root import digest_of
FILE=Path(__file__).resolve().parents[1]/'experiment/g11/G11_CSV16_POSTHOC_REPAIR_20261008.json'


class StreamingIteratorDevelopmentSuccess(unittest.TestCase):
    def test_full_suite_dev_result_and_provenance(self):
        result=json.loads(FILE.read_text())
        self.assertEqual(result['result_digest'],digest_of({
            k:v for k,v in result.items() if k!='result_digest'
        }))
        self.assertEqual(result['freeze_digest'],digest_of(result['freeze']))
        self.assertTrue(result['freeze']['exposed_development_case'])
        self.assertTrue(result['freeze']['human_implemented_operator'])
        self.assertFalse(result['freeze']['human_fixed_source_seen'])
        self.assertEqual(result['freeze']['first_passing_rank_hypothesis'],1)
        self.assertTrue(result['full_suite_passed'])
        self.assertTrue(result['independent_full_project_validation']['compiled'])
        self.assertTrue(result['independent_full_project_validation']['full_suite_ran'])
        self.assertEqual(result['independent_full_project_validation']['full_suite_failures'],0)
        self.assertEqual(result['blind_successes_counted'],0)


if __name__=='__main__':
    unittest.main()
