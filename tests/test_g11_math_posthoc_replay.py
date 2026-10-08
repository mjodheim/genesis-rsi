"""Preserve full-suite development result without mislabeling it unseen."""
import json
from pathlib import Path
import unittest

from genesis.trust_root import digest_of
P = Path(__file__).resolve().parents[1]/'experiment/g11/G11_MATH53_POSTHOC_REPAIR_20261008.json'

class TestMath53DevelopmentReplay(unittest.TestCase):
    def test_proof_and_scientific_scope(self):
        report=json.loads(P.read_text())
        self.assertEqual(report['result_digest'],
            digest_of({k:v for k,v in report.items() if k!='result_digest'}))
        self.assertEqual(report['freeze_digest'],digest_of(report['freeze']))
        self.assertEqual(report['freeze']['rank'],1)
        self.assertTrue(report['full_suite_passed'])
        self.assertTrue(report['validator']['compiled'])
        self.assertTrue(report['validator']['full_suite_ran'])
        self.assertEqual(report['validator']['full_suite_failures'],0)
        self.assertEqual(report['independent_holdout_success_count'],0)
        self.assertTrue(report['freeze']['known_exposed_case'])
        self.assertFalse(report['freeze']['human_patch_consulted'])
