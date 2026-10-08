"""Prevent accidental rewriting or misreporting of the frozen negative pilot."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from genesis.trust_root import digest_of
from scripts.g11_repair_pilot import CASES, PREREG, REPORT, preregistration


class FrozenRepairPilotTests(unittest.TestCase):
    def test_preregistration_is_still_frozen(self):
        manifest = json.loads(PREREG.read_text(encoding="utf-8"))
        self.assertEqual(manifest, preregistration())
        self.assertEqual(len(CASES), 8)
        self.assertFalse(manifest["er4_holdout_cases_used"])
        self.assertTrue(manifest["all_arms_freeze_before_oracle"])

    def test_report_integrity_and_no_false_promotion(self):
        result = json.loads(REPORT.read_text(encoding="utf-8"))
        payload = {k: v for k, v in result.items() if k != "report_digest"}
        self.assertEqual(result["report_digest"], digest_of(payload))
        self.assertEqual(result["preregistration_digest"], preregistration()["preregistration_digest"])
        self.assertEqual(
            result["full_suite_passed_case_counts_by_arm"],
            {"baseline": 7, "understanding": 6,
             "understanding_security_performance": 6},
        )
        self.assertTrue(all(
            x["original_compiles"] and x["original_fails_full_suite"]
            for x in result["cases"]
        ))
        self.assertTrue(all(
            x["arms"]["understanding"]["candidate_order_digest"]
            == x["arms"]["understanding_security_performance"]["candidate_order_digest"]
            for x in result["cases"]
        ))
        self.assertFalse(result["er4_holdouts_used"])
        self.assertFalse(result["training_memory_used"])


if __name__ == "__main__":
    unittest.main()
