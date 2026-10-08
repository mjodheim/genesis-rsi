"""Sealed REAL Math-53 development result; never a fresh holdout claim."""
from pathlib import Path
import json
import unittest
from genesis.trust_root import digest_of

BASE=Path(__file__).resolve().parents[1]/"experiment/v2"

class V21RealDevelopmentResultTests(unittest.TestCase):
    def test_prevalidation_freeze_and_full_project_verdict(self):
        frozen=json.loads((BASE/"V21_MATH53_PROPOSAL_FREEZE_20261008.json").read_text())
        result=json.loads((BASE/"V21_MATH53_DEVELOPMENT_VALIDATION_20261008.json").read_text())
        self.assertEqual(
            frozen["freeze_digest"],
            digest_of({k:v for k,v in frozen.items() if k!="freeze_digest"}),
        )
        self.assertEqual(
            result["result_digest"],
            digest_of({k:v for k,v in result.items() if k!="result_digest"}),
        )
        self.assertEqual(result["candidate_freeze_digest"],frozen["freeze_digest"])
        self.assertEqual(frozen["project"],"Math")
        self.assertEqual(frozen["bug_id"],53)
        self.assertEqual(frozen["hypothesis"]["target_method"],"add")
        self.assertEqual(frozen["hypothesis"]["donor_quorum"],3)
        self.assertTrue(frozen["already_exposed_training_case"])
        self.assertFalse(frozen["independent_unseen_holdout"])
        self.assertFalse(frozen["human_reference_patch_seen"])
        self.assertTrue(result["compiled"])
        self.assertTrue(result["full_suite_pass"])
        self.assertTrue(result["validator_result"]["full_suite_ran"])
        self.assertEqual(result["validator_result"]["full_suite_failures"],0)
        self.assertEqual(result["independent_unseen_repairs"],0)
        self.assertTrue(result["semantic_grammar_human_engineered"])

if __name__=="__main__":
    unittest.main()
