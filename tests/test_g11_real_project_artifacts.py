"""Immutable outcome checks: real-project negative evidence must remain visible."""
from pathlib import Path
import json
import unittest

from genesis.trust_root import digest_of

ROOT = Path(__file__).resolve().parents[1] / "experiment" / "g11"


class IndependentRepairProbeArtifacts(unittest.TestCase):
    def test_negative_results_match_preregistrations(self):
        for case, project, count in (
            ("CODEC15", "Codec", 16),
            ("COMPRESS6", "Compress", 13),
        ):
            with self.subTest(project=project):
                pre = json.loads((ROOT / f"G11_{case}_PREREG_20261008.json").read_text())
                result = json.loads((ROOT / f"G11_{case}_RESULTS_20261008.json").read_text())
                self.assertEqual(
                    pre["preregistration_digest"],
                    digest_of({k: v for k, v in pre.items() if k != "preregistration_digest"}),
                )
                self.assertEqual(
                    result["report_digest"],
                    digest_of({k: v for k, v in result.items() if k != "report_digest"}),
                )
                self.assertEqual(pre["preregistration_digest"], result["preregistration_digest"])
                self.assertEqual(result["project"], project)
                self.assertEqual(result["original_full_suite_failing_count"], 1)
                self.assertTrue(result["all_arms_frozen_before_validation"])
                self.assertFalse(result["fixed_checkout_or_human_patch_used"])
                self.assertEqual(result["unique_candidates_evaluated"], count)
                self.assertEqual(result["fully_validated_unique_candidates"], 0)
                self.assertTrue(all(
                    arm["first_validated_rank"] is None
                    for arm in result["arms"].values()
                ))

    def test_posthoc_compilation_audit_never_claims_repair(self):
        report = json.loads(
            (ROOT / "G11_COMPRESS6_COMPILE_PREFLIGHT_AUDIT_20261008.json").read_text()
        )
        self.assertEqual(
            report["audit_digest"],
            digest_of({k: v for k, v in report.items() if k != "audit_digest"}),
        )
        self.assertTrue(report["development_case_already_exposed"])
        self.assertEqual(report["tested_candidate_count"], 13)
        self.assertEqual(report["agreement_on_decisive_compilation_status"], 13)
        self.assertEqual(report["compiler_valid_count"], 3)
        self.assertEqual(report["compiler_invalid_count"], 10)
        self.assertEqual(report["full_suite_repairs_found"], 0)


if __name__ == "__main__":
    unittest.main()
