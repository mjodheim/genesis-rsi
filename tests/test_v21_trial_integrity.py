"""Prospective repair study integrity plus validator-copy non-regression."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from genesis.trust_root import digest_of
from scripts.audit_v21_mockito_validator import isolation
from scripts.run_v21_fresh_repair_trial import (
    _open_verified,PREREG,FROZEN,PUBLIC_INDEX,OUTCOME,
)


class V21ProspectiveIntegrity(unittest.TestCase):
    def test_selection_candidate_freeze_and_original_result_are_linked(self):
        manifest=_open_verified(PREREG,"preregistration_digest")
        frozen=_open_verified(FROZEN,"freeze_digest")
        index=_open_verified(PUBLIC_INDEX,"index_digest")
        result=_open_verified(OUTCOME,"result_digest")
        self.assertEqual(manifest["preregistration_digest"],frozen["preregistration_digest"])
        self.assertEqual(index["all_candidates_freeze_digest"],frozen["freeze_digest"])
        self.assertEqual(result["candidate_freeze_digest"],frozen["freeze_digest"])
        self.assertEqual(
            [(c["project"],c["bug_id"]) for c in manifest["projects"]],
            [("Chart",23),("JacksonXml",4),("Mockito",22)],
        )
        self.assertTrue(frozen["candidate_validation_has_not_started"])
        self.assertTrue(index["no_candidate_evaluator_executed_prior_to_freeze"])
        self.assertEqual(result["real_project_full_suite_repairs_by_arm"],{
            "v1_frozen_default":0,
            "v21_typed_semantic_optin":0,
        })
        for case in index["cases"]:
            baseline=case["arms"]["v1_frozen_default"]
            modern=case["arms"]["v21_typed_semantic_optin"]
            self.assertEqual(baseline["generator_index_digest"],modern["generator_index_digest"])
            self.assertEqual(baseline["top_k"],modern["top_k"])
            self.assertEqual(modern["new_v21_hypotheses_generated"],0)
        self.assertTrue(result["human_reference_fix_seen"] is False)

    def test_compilation_control_copy_preserves_nested_build_dependencies(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/"buggy"
            target=root/"copy"
            source.mkdir()
            nested=source/"lib/build"
            nested.mkdir(parents=True)
            (nested/"mockito-dependency.jar").write_bytes(b"example-jar-container")
            (source/"demo.class").write_bytes(b"old compiled artifact")
            (source/".git").mkdir()
            (source/".git"/"HEAD").write_text("ref: refs/heads/original")
            isolation(source,target)
            self.assertEqual(
                (target/"lib/build/mockito-dependency.jar").read_bytes(),
                b"example-jar-container",
            )
            self.assertFalse((target/"demo.class").exists())
            self.assertFalse((target/".git").exists())

    def test_correction_provenance_is_predeclared(self):
        amended=Path("experiment/v2/V21_FRESH_3PROJECT_VALIDATOR_AMENDMENT_20261008.json")
        record=_open_verified(amended,"amendment_digest")
        original=_open_verified(OUTCOME,"result_digest")
        frozen=_open_verified(FROZEN,"freeze_digest")
        self.assertEqual(record["unchanged_candidate_freeze_digest"],frozen["freeze_digest"])
        self.assertEqual(record["original_result_digest"],original["result_digest"])
        self.assertEqual(record["invalidated_validation"],["Mockito-22"])
        self.assertEqual(record["still_valid_cases"],["Chart-23","JacksonXml-4"])
        self.assertTrue(record["source_policy_lock_unchanged"])


if __name__=="__main__":
    unittest.main()
