"""V2 discovery: self-proposed policy mutation, budget parity and trust boundaries."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import unittest

from genesis.trust_root import digest_of
from genesis.v2.genome import (
    FEATURES, GenomeError, make_seed, mutate, neighborhood, rank, validate_genome,
)
from genesis.v2.discovery import (
    DiscoveryError, retrospective_study, select, validate_study,
)
from genesis.v2.traces import TraceError, validate_catalogue, SCHEMA as TRACE_SCHEMA

ROOT = Path(__file__).resolve().parents[1] / "experiment/v2"
CATALOGUE = ROOT / "V2_RELEASED_DEVELOPMENT_CATALOGUE_20261008.json"
STUDY = ROOT / "V2_RETROSPECTIVE_DISCOVERY_20261008.json"


def demo_case(name: str) -> dict:
    # None of the evaluator labels are passed to the V2 selection function.
    candidates = []
    for idx in range(4):
        props = {key: 0 for key in FEATURES}
        props["atomic"] = int(idx in (2, 3))
        item = {
            "id": digest_of({"case":name, "i":idx}),
            "features": props,
            "compiled": idx in (2, 3),
            "full_suite_pass": False,
        }
        candidates.append(item)
    core = {
        "case_id":name,
        "released_training_only":True,
        "candidate_count":len(candidates),
        "candidates":candidates,
        "source_freeze_digest":"a"*64,
        "source_result_digest":"b"*64,
    }
    return {**core,"case_digest":digest_of(core)}


def synthetic_catalogue():
    cases = [demo_case(name) for name in ("TrainA", "TrainB", "CheckC")]
    core = {
        "schema":TRACE_SCHEMA,
        "cases":cases,
        "case_count":len(cases),
        "contains_only_already_exposed_cases":True,
        "contains_untouched_holdouts":False,
        "candidate_pools_include_only_evaluated_proposals":True,
        "source_patches_stored":False,
    }
    return {**core,"catalogue_digest":digest_of(core)}


class V2GenomeTests(unittest.TestCase):
    def test_self_mutation_is_bounded_content_addressed_and_reproducible(self):
        parent=make_seed()
        neighbors=neighborhood(parent)
        self.assertEqual(len(neighbors),len(FEATURES)*2)
        assert neighbors[0]["parent_digest"] == parent["genome_digest"]
        self.assertEqual(neighbors[0]["generation"],1)
        self.assertEqual(neighbors[0]["mutation"],{"feature":"atomic","delta":-1})
        self.assertEqual(neighbors[0],mutate(parent,"atomic",-1))
        self.assertTrue(all(x["can_change_trust_root"] is False for x in neighbors))
        self.assertTrue(all(x["can_execute_generated_source"] is False for x in neighbors))
        self.assertEqual(parent,validate_genome(parent))

    def test_mutation_cannot_change_evaluator_or_run_arbitrary_code(self):
        parent=make_seed()
        for feature,delta in (("evaluator",1),("atomic",2),("atomic",True),("atomic",1.0)):
            with self.subTest(feature=feature,delta=delta),self.assertRaises(GenomeError):
                mutate(parent,feature,delta)
        forged=deepcopy(parent)
        forged["can_change_trust_root"]=True
        forged["genome_digest"]=digest_of({k:v for k,v in forged.items() if k!="genome_digest"})
        with self.assertRaisesRegex(GenomeError,"trust root"):
            validate_genome(forged)
        forged=deepcopy(parent)
        forged["weights"]["atomic"]=True
        with self.assertRaises(GenomeError):
            validate_genome(forged)
        with self.assertRaises(GenomeError):
            rank(parent,dict({feature:0 for feature in FEATURES}, compiled=1))

    def test_candidate_ranking_does_not_observe_validator_labels(self):
        case=demo_case("TrainA")
        before=select(mutate(make_seed(),"atomic",1),case,2)
        changed=deepcopy(case)
        for proposal in changed["candidates"]:
            proposal["compiled"]=not proposal["compiled"]
            proposal["full_suite_pass"]=True
        self.assertEqual(before,select(mutate(make_seed(),"atomic",1),changed,2))


class V2EvolutionTests(unittest.TestCase):
    def test_synthesized_descendant_improves_synthetic_training_and_check(self):
        result=retrospective_study(
            synthetic_catalogue(),
            training_case_ids=["TrainA","TrainB"],
            development_check_case_ids=["CheckC"],
            top_k=2,max_generations=2,
        )
        self.assertEqual(result,validate_study(result))
        self.assertEqual(result["training_search"]["learned_genome"]["generation"],1)
        self.assertEqual(result["baseline_check"]["compile_valid_candidates"],0)
        self.assertEqual(result["descendant_check"]["compile_valid_candidates"],2)
        self.assertEqual(result["development_compilation_gain"],2)
        self.assertEqual(result["development_full_suite_gain"],0)
        self.assertEqual(result["decision"],"never_promote_from_exposed_data")
        self.assertTrue(result["production_genome_unchanged"])

    def test_no_train_check_overlap_or_unproven_corpus(self):
        catalogue=synthetic_catalogue()
        for train,check in (
            (["TrainA"],["TrainA","CheckC"]),
            (["TrainA"],["CheckC"]),
        ):
            with self.subTest(train=train,check=check),self.assertRaises(DiscoveryError):
                retrospective_study(
                    catalogue,training_case_ids=train,
                    development_check_case_ids=check,
                )
        forged=deepcopy(catalogue)
        forged["contains_untouched_holdouts"]=True
        forged["catalogue_digest"]=digest_of({k:v for k,v in forged.items()
                                              if k!="catalogue_digest"})
        with self.assertRaisesRegex(TraceError,"unacceptable evidence"):
            retrospective_study(
                forged,training_case_ids=["TrainA","TrainB"],
                development_check_case_ids=["CheckC"],top_k=2,
            )

    def test_study_tamper_cannot_claim_success_or_invent_a_lineage(self):
        report=retrospective_study(
            synthetic_catalogue(),training_case_ids=["TrainA","TrainB"],
            development_check_case_ids=["CheckC"],top_k=2,
        )
        forged=deepcopy(report)
        forged["fresh_unseen_repair_claims"]=1
        forged["study_digest"]=digest_of({k:v for k,v in forged.items() if k!="study_digest"})
        with self.assertRaisesRegex(DiscoveryError,"scientific boundary"):
            validate_study(forged)
        forged=deepcopy(report)
        forged["training_search"]["learned_genome"]["weights"]["rare_source"]=1
        forged["training_search"]["training_search_digest"]=digest_of({
            k:v for k,v in forged["training_search"].items() if k!="training_search_digest"
        })
        forged["study_digest"]=digest_of({k:v for k,v in forged.items() if k!="study_digest"})
        with self.assertRaises(DiscoveryError):
            validate_study(forged)


class V2RealExposedCorpusTests(unittest.TestCase):
    def test_9_exposed_java_cases_are_replayable_without_patch_contents(self):
        catalogue=validate_catalogue(json.loads(CATALOGUE.read_text()))
        self.assertEqual(catalogue["case_count"],9)
        self.assertFalse(catalogue["contains_untouched_holdouts"])
        self.assertTrue(catalogue["candidate_pools_include_only_evaluated_proposals"])
        self.assertFalse(catalogue["source_patches_stored"])
        self.assertEqual(sum(c["candidate_count"] for c in catalogue["cases"]),191)
        self.assertEqual(sum(c["full_suite_pass"] for case in catalogue["cases"]
                             for c in case["candidates"]),0)
        report=validate_study(json.loads(STUDY.read_text()))
        self.assertEqual(report["catalogue_digest"],catalogue["catalogue_digest"])
        self.assertEqual(report["training_search"]["learned_genome"]["generation"],2)
        self.assertEqual(report["training_search"]["total_mutants_considered"],20)
        self.assertEqual(report["baseline_check"]["compile_valid_candidates"],16)
        self.assertEqual(report["descendant_check"]["compile_valid_candidates"],21)
        self.assertEqual(report["development_full_suite_gain"],0)
        self.assertTrue(report["no_new_program_executions"])
        self.assertEqual(report["decision"],"never_promote_from_exposed_data")


if __name__ == "__main__":
    unittest.main()
