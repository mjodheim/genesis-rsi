"""Scientific contamination guards and durable generalized outcome evidence."""
from pathlib import Path
import tempfile
import unittest

from genesis.operator_outcome_memory import OperatorOutcomeMemory

D = "a"*64
E = "b"*64
F = "c"*64
G = "d"*64


def example(mem, **changes):
    options = dict(
        project="ExampleProject",
        case_digest=D,
        candidate_sha256=E,
        operators=["java_state_consistency"],
        public_failure_symptom="value_mismatch",
        outcome="compile_failed",
        freeze_digest=F,
        independent_evaluator_digest=G,
        role="released_training",
    )
    options.update(changes)
    return mem.record(**options)


class OperatorOutcomeMemoryTests(unittest.TestCase):
    def test_refuses_fresh_holdout_or_unsupported_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = OperatorOutcomeMemory(Path(tmp) / "experience.sqlite")
            with self.assertRaisesRegex(ValueError, "released training"):
                example(mem, role="fresh_holdout")
            with self.assertRaisesRegex(ValueError, "invalid outcome"):
                example(mem, outcome="perfect_RSI")
            with self.assertRaisesRegex(ValueError, "invalid"):
                example(mem, candidate_sha256="not_hash")
            self.assertEqual(mem.events(), [])

    def test_hash_chain_persists_without_any_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            name = Path(tmp) / "ledger.sqlite"
            mem = OperatorOutcomeMemory(name)
            first = example(mem)
            second = example(mem, candidate_sha256=G, outcome="public_trigger_failed")
            other = OperatorOutcomeMemory(name)
            events = other.events()
            self.assertEqual(len(events), 2)
            self.assertEqual(events[1]["previous_digest"], first["event_digest"])
            self.assertEqual(events[1]["event_digest"], second["event_digest"])
            summary = other.evidence_summary()
            self.assertEqual(summary["event_count"], 2)
            self.assertEqual(
                summary["operator_evidence"]["java_state_consistency"]["distinct_training_cases"], 1
            )
            self.assertFalse(
                summary["operator_evidence"]["java_state_consistency"]["eligible_for_future_ranking_study"]
            )
            self.assertEqual(summary["independently_verified_repair_successes"], 0)

    def test_too_few_cases_cannot_trigger_learning_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            mem = OperatorOutcomeMemory(Path(tmp) / "e.sqlite")
            example(mem, outcome="full_suite_passed")
            s = mem.evidence_summary()["operator_evidence"]["java_state_consistency"]
            self.assertEqual(s["cases_with_reported_full_suite_pass"], 1)
            self.assertFalse(s["eligible_for_future_ranking_study"])
            self.assertFalse(s["ranking_automatically_changed"])


if __name__ == "__main__":
    unittest.main()
