"""Distinguish development repairs from independently held-out successes."""
import json
from pathlib import Path
import unittest

from genesis.trust_root import digest_of

REPORT = (
    Path(__file__).resolve().parents[1]
    / "experiment/g11/G11_COMPRESS6_POSTHOC_REPAIR_20261008.json"
)


class ReplayIntegrityTests(unittest.TestCase):
    def test_full_suite_development_success_cannot_be_relabelled_blind(self):
        result = json.loads(REPORT.read_text(encoding="utf-8"))
        self.assertEqual(
            result["result_digest"],
            digest_of({k: v for k, v in result.items() if k != "result_digest"}),
        )
        self.assertEqual(result["freeze_digest"], digest_of(result["freeze"]))
        self.assertTrue(result["case_was_already_exposed"])
        self.assertFalse(result["human_reference_patch_seen"])
        self.assertEqual(result["independent_holdout_success_count"], 0)
        self.assertEqual(result["freeze"]["atomic_disabled_rank"], 51)
        self.assertEqual(result["freeze"]["atomic_enabled_rank"], 1)
        self.assertTrue(result["validated_full_project_suite"])
        self.assertTrue(result["full_project_validation"]["compiled"])
        self.assertEqual(result["full_project_validation"]["failing_tests"], 0)


if __name__ == "__main__":
    unittest.main()
