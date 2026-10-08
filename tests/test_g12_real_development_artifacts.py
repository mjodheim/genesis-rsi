"""Two real-project successes demonstrate TRAINING operator acquisition only."""
from pathlib import Path
import json
import unittest

from genesis.trust_root import digest_of

BASE=Path(__file__).resolve().parents[1]/"experiment/g12"


class RealDevelopmentEvidenceTests(unittest.TestCase):
    def test_two_structural_acquisitions_have_full_project_evaluation(self):
        for project,bug in (("COMPRESS6",6),("MATH53",53)):
            with self.subTest(project=project):
                manifest=json.loads((BASE/f"G12_{project}_DEVELOPMENT_MANIFEST_20261008.json").read_text())
                outcome=json.loads((BASE/f"G12_{project}_DEVELOPMENT_RESULT_20261008.json").read_text())
                self.assertEqual(outcome["receipt_digest"],digest_of(
                    {k:v for k,v in outcome.items() if k!="receipt_digest"}
                ))
                self.assertEqual(outcome["memory_generation"],2)
                self.assertEqual(outcome["attempt_count"],1)
                self.assertEqual(outcome["independent_new_bug_successes"],0)
                self.assertFalse(outcome["novel_semantic_operator_autonomously_invented"])
                self.assertTrue(outcome["learning_only_from_validated_candidate"])
                self.assertFalse(outcome["human_patch_accessed"])
                self.assertEqual(outcome["source_role"],"released_training")
                op=outcome["validated_operator_acquisition"]
                self.assertIsNotNone(op)
                self.assertTrue(op["replay_verified_on_training_source"])
                self.assertTrue(op["reused_without_model_calls"])
                self.assertTrue(outcome["attempts"][0]["validated_full_suite"])
                self.assertTrue(outcome["attempts"][0]["outcome"]["full_suite_pass"])
                self.assertEqual(outcome["attempts"][0]["outcome"]["full_suite_failures"],0)
                if project=="COMPRESS6":
                    self.assertEqual(
                        manifest["manifest_digest"],
                        digest_of({k:v for k,v in manifest.items() if k!="manifest_digest"}),
                    )
                    self.assertEqual(manifest["freeze_digest"],outcome["frozen_candidates_digest"])
                else:
                    self.assertEqual(
                        manifest["manifest_digest"],
                        digest_of({k:v for k,v in manifest.items() if k!="manifest_digest"}),
                    )
                    self.assertEqual(manifest["candidate_freeze_digest"],outcome["frozen_candidates_digest"])

if __name__=="__main__":
    unittest.main()
