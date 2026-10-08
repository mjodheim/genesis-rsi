"""Representative public test diagnostics, no reference patches."""
import unittest
from genesis.failure_feedback import analyze_public_failures as analyze


class PublicFailureSignalTests(unittest.TestCase):
    def test_value_delta_is_not_called_the_correct_patch(self):
        record = analyze(
            "--- pkg.ParserTest::iteratorBreaking\n"
            "junit.framework.AssertionFailedError: expected:<[3]> but was:<[4]>\n"
            "\tat pkg.ParserTest.iteratorBreaking(ParserTest.java:1053)\n"
        )
        self.assertEqual(record["failure_count"], 1)
        x = record["observations"][0]
        self.assertEqual(x["symptom"], "value_mismatch")
        self.assertEqual(x["expected_public_observation"], "[3]")
        self.assertEqual(x["actual_public_observation"], "[4]")
        self.assertFalse(x["repair_proven"])
        self.assertIsNone(record["operator_family_selected"])

    def test_identity_is_distinct_from_value_equality(self):
        obs = analyze(
            "--- t.FactoryTest::testFactory\n"
            "junit.framework.AssertionFailedError: expected same:<[a]> was not:<[a]>\n"
        )["observations"][0]
        self.assertEqual(obs["symptom"], "identity_mismatch")
        self.assertIsNone(obs["expected_public_observation"])

    def test_nan_as_assertion_without_message_remains_unknown_cause(self):
        obs = analyze(
            "--- pkg.ComplexTest::testAddNaN\n"
            "junit.framework.AssertionFailedError\n"
            "\tat org.junit.Assert.assertTrue(Assert.java:53)\n"
        )["observations"][0]
        self.assertEqual(obs["symptom"], "assertion_unspecified")
        self.assertFalse(obs["fault_location_proven"])

    def test_exception_and_multiple_cases(self):
        out = analyze(
            "--- t.FooTest::testOne\njava.lang.NullPointerException: foo\n"
            "--- t.BarTest::testTwo\njava.lang.ArrayIndexOutOfBoundsException: 9\n"
        )
        self.assertEqual(out["failure_count"], 2)
        self.assertEqual([x["symptom"] for x in out["observations"]],
                         ["runtime_exception", "runtime_exception"])
        self.assertEqual(out["observations"][0]["exception_type"], "java.lang.NullPointerException")

    def test_empty_text(self):
        self.assertEqual(analyze("all tests pass\n")["failure_count"], 0)


if __name__ == "__main__":
    unittest.main()
