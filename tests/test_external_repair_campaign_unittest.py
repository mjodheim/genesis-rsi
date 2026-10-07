from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from genesis import external_repair_campaign as campaign
from genesis import external_repair_learning as learning
from genesis import failure_driven_self_extension as self_extension
from genesis import repair_strategist
from genesis.trust_root import digest_of


class FakeAdapter:
    def __init__(self) -> None:
        self.cases = ["case-a", "case-b"]
        self.revealed: list[str] = []

    def select_case(self, state):
        remaining = [c for c in self.cases if c not in state["attempted_case_ids"]]
        cid = remaining[0]
        payload = {"case_id": cid}
        return {**payload, "selection_digest": digest_of(payload)}

    def prepare_blind(self, state):
        cid = state["current_case"]["case_id"]
        payload = {
            "case_id": cid,
            "human_fix_inspected": False,
            "issue_text_inspected": False,
        }
        return {**payload, "freeze_digest": digest_of(payload)}

    def evaluate_blind(self, state):
        cid = state["current_case"]["case_id"]
        if cid == "case-a":
            payload = {
                "case_id": cid,
                "winner": None,
                "scientific_gate_passed": False,
                "human_fix_inspected": False,
                "issue_text_inspected": False,
            }
        else:
            payload = {
                "case_id": cid,
                "winner": {"id": "blind-win"},
                "scientific_gate_passed": True,
                "human_fix_inspected": False,
                "issue_text_inspected": False,
            }
        return {**payload, "result_digest": digest_of(payload)}

    def validate_success(self, state):
        return {"passed": True, "validation_digest": "success-validation"}

    def diagnose_and_retain(self, state):
        # A retained diagnosis is a machinery-state transition, but it adds no
        # repair capability yet.  Crucially it happens before reveal.
        prior = state["machinery"]["machinery_digest"]
        machinery = {
            "machinery_digest": digest_of({"parent": prior, "gap": "case-a"}),
            "parent_machinery_digest": prior,
            "capability_generation": state["machinery"].get("capability_generation", 0),
        }
        payload = {
            "solution_visible": False,
            "machinery": machinery,
            "diagnosis": {"kind": "synthetic_gap"},
        }
        return {**payload, "learning_digest": digest_of(payload)}

    def reveal_solution(self, state):
        cid = state["current_case"]["case_id"]
        self.revealed.append(cid)
        return {"solution_digest": digest_of({"solution": cid})}

    def learn_from_solution(self, state):
        prior = state["machinery"]["machinery_digest"]
        machinery = {
            "machinery_digest": digest_of({"parent": prior, "operator": "learned-op"}),
            "parent_machinery_digest": prior,
            "capability_generation": state["machinery"].get("capability_generation", 0) + 1,
        }
        payload = {"machinery": machinery, "added": ["learned-op"]}
        return {**payload, "learning_digest": digest_of(payload)}

    def validate_machinery(self, state):
        return {"passed": True, "validation_digest": "machinery-validation"}


class CampaignTests(unittest.TestCase):
    def test_negative_learn_positive_runs_without_host_sequencing(self):
        with tempfile.TemporaryDirectory() as td:
            store = campaign.CampaignStore(Path(td) / "campaign.json")
            initial = campaign.create_state(
                campaign_id="synthetic-autonomous",
                machinery={"machinery_digest": "m0", "capability_generation": 0},
                max_cases=2,
            )
            adapter = FakeAdapter()
            final = campaign.run(store, adapter, initial_state=initial)

            self.assertEqual(final["phase"], "complete")
            self.assertEqual(final["attempted_case_ids"], ["case-a", "case-b"])
            self.assertEqual(final["success_count"], 1)
            self.assertEqual(adapter.revealed, ["case-a"])
            self.assertEqual(final["machinery"]["capability_generation"], 1)

            kinds = [e["kind"] for e in final["events"]]
            self.assertLess(
                kinds.index("blind_result_frozen"),
                kinds.index("negative_diagnosed_pre_reveal"),
            )
            self.assertLess(
                kinds.index("negative_diagnosed_pre_reveal"),
                kinds.index("solution_revealed_after_negative"),
            )
            self.assertIn("positive_validated", kinds)

    def test_seeded_exclusions_do_not_consume_max_cases(self):
        with tempfile.TemporaryDirectory() as td:
            store = campaign.CampaignStore(Path(td) / "campaign.json")
            initial = campaign.create_state(
                campaign_id="seeded-limit",
                machinery={"machinery_digest": "m0", "capability_generation": 0},
                max_cases=2,
                attempted_case_ids=["old-1", "old-2", "old-3"],
            )
            adapter = FakeAdapter()
            # FakeAdapter only knows case-a/case-b, so old exclusions must not
            # make the campaign complete before those two fresh cases run.
            final = campaign.run(store, adapter, initial_state=initial)
            self.assertEqual(final["phase"], "complete")
            self.assertEqual(final["generation"], 2)
            self.assertEqual(final["attempted_case_ids"][-2:], ["case-a", "case-b"])

    def test_trigger_positive_that_fails_broad_validation_resumes_search(self):
        class OverfitAdapter(FakeAdapter):
            def validate_success(self, state):
                return {
                    "passed": False,
                    "winner_index": 17,
                    "resume_index": 32,
                    "validation_digest": "overfit-validation",
                }

        adapter = OverfitAdapter()
        state = campaign.create_state(
            campaign_id="overfit-resume",
            machinery={"machinery_digest": "m0", "capability_generation": 0},
        )
        state = dict(state)
        state["phase"] = "validate_success"
        state["current_case"] = {"case_id": "case-b"}
        state["blind_result"] = {
            "winner": {"id": "trigger-only", "index": 17},
            "scientific_gate_passed": True,
            "result_digest": "blind-positive",
        }
        state.pop("state_digest")
        state["state_digest"] = digest_of({k: v for k, v in state.items() if k != "state_digest"})

        resumed = campaign.transition(state, adapter)
        self.assertEqual(resumed["phase"], "evaluate")
        self.assertEqual(resumed["success_count"], 0)
        self.assertEqual(resumed["success_validation"]["resume_index"], 32)
        self.assertEqual(resumed["events"][-1]["kind"], "trigger_positive_rejected")

    def test_reveal_gate_refuses_positive_or_unfrozen_state(self):
        adapter = FakeAdapter()
        state = campaign.create_state(
            campaign_id="guard",
            machinery={"machinery_digest": "m0"},
        )
        # Construct a valid state that is at reveal but carries a positive.
        state = dict(state)
        state["phase"] = "reveal"
        state["current_case"] = {"case_id": "x"}
        state["blind_result"] = {
            "winner": {"id": "pass"},
            "scientific_gate_passed": True,
            "result_digest": "r",
        }
        state["pre_reveal_learning"] = {"solution_visible": False}
        state.pop("state_digest")
        state["state_digest"] = digest_of({k: v for k, v in state.items() if k != "state_digest"})
        with self.assertRaises(campaign.ExternalRepairCampaignError):
            campaign.transition(state, adapter)


class RetainedLearningTests(unittest.TestCase):
    def test_revealed_fix_becomes_zero_model_planner_capability(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            buggy = base / "buggy"
            fixed = base / "fixed"
            fresh = base / "fresh"
            for root in (buggy, fixed, fresh):
                (root / "src").mkdir(parents=True)

            before = """class Counter {
    int bump(int value) {
        return value + 1;
    }
}
"""
            after = """class Counter {
    int bump(int value) {
        return value + 2;
    }
}
"""
            fresh_before = """class OtherCounter {
    int bump(int amount) {
        return amount + 1;
    }
}
"""
            (buggy / "src" / "Counter.java").write_text(before, encoding="utf-8")
            (fixed / "src" / "Counter.java").write_text(after, encoding="utf-8")
            (fresh / "src" / "OtherCounter.java").write_text(fresh_before, encoding="utf-8")

            frozen_miss = learning.blind_result_for_gap(
                {
                    "evaluated_count": 10_000,
                    "coverage_pruned_count": 0,
                    "winner": None,
                },
                family_activation={},
                candidate_budget=10_000,
            )
            retained = learning.diagnose_and_retain(
                self_extension.empty_memory(),
                buggy,
                frozen_miss,
                target_prefixes=["src"],
            )
            self.assertFalse(retained["solution_visible"])

            acquired = learning.acquire_from_revealed_solution(
                retained["memory"],
                buggy,
                fixed,
                diagnosis=retained["diagnosis"],
                passing_result_digest="trusted-fixed-reference-pass",
                target_prefixes=["src"],
                context_lines=0,
            )
            memory = acquired["memory"]
            self.assertEqual(len(memory["operators"]), 1)
            self.assertEqual(acquired["external_model_calls"], 0)

            variants = learning.retained_variants(
                memory,
                fresh,
                include_prefixes=["src/OtherCounter.java"],
            )
            self.assertGreaterEqual(variants["candidate_count"], 1)
            self.assertTrue(
                any("amount + 2" in c["content_utf8"] for c in variants["candidates"])
            )

            planned = repair_strategist.generate(
                fresh,
                include_prefixes=["src"],
                focus_paths=["src/OtherCounter.java"],
                max_candidates=64,
                composition_fraction=0.25,
                retained_memory=memory,
            )
            retained_meta = planned["family_activation"]["retained_structural"]
            self.assertTrue(retained_meta["activated"])
            self.assertTrue(
                any(
                    "retained_structural_operator" in c["plan"]["component_operators"]
                    for c in planned["candidates"]
                )
            )
            self.assertEqual(planned["external_model_calls"], 0)


if __name__ == "__main__":
    unittest.main()
