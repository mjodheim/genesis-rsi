import tempfile
import unittest
from pathlib import Path
from genesis import external_repair_learning as learning
from genesis import failure_driven_self_extension as self_extension


class GapIdentityTests(unittest.TestCase):
    def test_report_digest_tracks_frozen_result(self):
        a = learning.blind_result_for_gap(
            {"evaluated_count": 100, "winner": None, "result_digest": "case-a"}
        )
        b = learning.blind_result_for_gap(
            {"evaluated_count": 100, "winner": None, "result_digest": "case-b"}
        )
        self.assertNotEqual(a["report_digest"], b["report_digest"])
        self.assertEqual(a["source_result_digest"], "case-a")

    def test_two_cases_can_be_retained_sequentially(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "src"
            src.mkdir()
            (src / "A.java").write_text("class A {}\n")
            memory = self_extension.empty_memory()
            for case in ("a", "b"):
                report = learning.blind_result_for_gap(
                    {"evaluated_count": 10000, "winner": None, "result_digest": case},
                    candidate_budget=10000,
                )
                outcome = learning.diagnose_and_retain(
                    memory, root, report, target_prefixes=["src"],
                )
                memory = outcome["memory"]
            self.assertEqual(memory["generation"], 2)
            self.assertEqual(len(memory["events"]), 2)


if __name__ == "__main__":
    unittest.main()
