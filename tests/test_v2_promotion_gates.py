"""The immutable scientific authority refuses retrospective RSI promotion."""
from copy import deepcopy
from pathlib import Path
import json
import unittest

from genesis.trust_root import digest_of
from genesis.v2.gates import assess_development, validate_assessment
from genesis.v2.discovery import validate_study

BASE=Path(__file__).resolve().parents[1]/"experiment/v2"


class V2PromotionGateTests(unittest.TestCase):
    def test_real_retro_dev_success_still_cannot_be_promoted(self):
        study=validate_study(json.loads(
            (BASE/"V2_RETROSPECTIVE_DISCOVERY_20261008.json").read_text()
        ))
        assessment=validate_assessment(assess_development(study))
        self.assertEqual(assessment,json.loads(
            (BASE/"V2_RETROSPECTIVE_PROMOTION_GATE_20261008.json").read_text()
        ))
        self.assertEqual(assessment["development_compilation_gain"],5)
        self.assertEqual(assessment["development_full_suite_gain"],0)
        self.assertEqual(assessment["cases_with_regression"],["JxPath-12"])
        self.assertFalse(assessment["production_promotion_allowed"])
        self.assertFalse(assessment["fresh_holdout_evidence_present"])
        self.assertIn("corpus_already_exposed",assessment["gate_reasons"])
        self.assertIn("no_new_full_suite_repairs",assessment["gate_reasons"])
        self.assertIn("per_project_regression",assessment["gate_reasons"])

    def test_rehashed_promotion_forgery_still_fails(self):
        assessment=json.loads(
            (BASE/"V2_RETROSPECTIVE_PROMOTION_GATE_20261008.json").read_text()
        )
        forged=deepcopy(assessment)
        forged["production_promotion_allowed"]=True
        forged["gate_digest"]=digest_of({
            k:v for k,v in forged.items() if k!="gate_digest"
        })
        with self.assertRaisesRegex(ValueError,"cannot approve"):
            validate_assessment(forged)

    def test_equal_budget_invariant(self):
        assessment=json.loads(
            (BASE/"V2_RETROSPECTIVE_PROMOTION_GATE_20261008.json").read_text()
        )
        forged=deepcopy(assessment)
        forged["per_case"][0]["equal_budget"]=False
        forged["gate_digest"]=digest_of({
            k:v for k,v in forged.items() if k!="gate_digest"
        })
        with self.assertRaisesRegex(ValueError,"unequal"):
            validate_assessment(forged)

if __name__=="__main__":
    unittest.main()
