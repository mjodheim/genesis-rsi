"""Only public failing-test class names influence weak source hints."""
import unittest

from genesis.failure_localization import prioritize


class TestSourceHints(unittest.TestCase):
    def test_exact_test_class_match_prioritizes_source_not_oracle(self):
        paths = [
            "src/a/z/ArchiveEntry.java",
            "src/a/z/ZipArchiveEntry.java",
            "src/a/z/ZipExtraField.java",
        ]
        result = prioritize(
            "--- com.acme.ZipArchiveEntryTest::testNotEquals\n"
            "junit.framework.AssertionFailedError\n"
            "\tat com.acme.ZipArchiveEntryTest.testNotEquals(ZipArchiveEntryTest.java:230)",
            paths,
        )
        self.assertEqual(
            result["matched_source_paths"],
            ["src/a/z/ZipArchiveEntry.java"],
        )
        self.assertEqual(result["source_paths"][0], "src/a/z/ZipArchiveEntry.java")
        self.assertFalse(result["fault_location_proven"])
        self.assertFalse(result["human_patch_seen"])

    def test_no_guessing_from_unrelated_tests(self):
        result = prioritize(
            "--- com.acme.UnrelatedTest::failure\n",
            ["src/b/Foo.java", "src/b/Bar.java"],
        )
        self.assertEqual(result["matched_source_paths"], [])
        self.assertEqual(result["source_paths"], ["src/b/Bar.java", "src/b/Foo.java"])

    def test_ambiguous_names_remain_multiple_hints(self):
        result = prioritize(
            "--- tests.OtherTest::first\n"
            "--- tests.AnotherTestCase::second\n",
            ["src/Another.java", "src/Other.java", "src/Else.java"],
        )
        self.assertEqual(result["matched_source_paths"], ["src/Another.java", "src/Other.java"])
        self.assertEqual(result["test_header_count"], 2)

    def test_non_exact_names_do_not_match_substrings(self):
        result = prioritize(
            "--- pkg.CollectionTest::fails\n",
            ["src/Collections.java", "src/CollectionUtils.java"],
        )
        self.assertEqual(result["matched_source_paths"], [])


if __name__ == "__main__":
    unittest.main()
