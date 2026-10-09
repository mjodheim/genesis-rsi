import json
from pathlib import Path

import pytest

from genesis import localizer_lineage as lineage
from genesis import localizer_seed
from genesis.repair_lineage import Envelope, Ledger

REVERSE_PATCH = """\
diff --git a/src/a/B.java b/src/a/B.java
index 1..2 100644
--- a/src/a/B.java
+++ b/src/a/B.java
@@ -10,7 +10,7 @@ class B {
 c1
 c2
 c3
-fixed line
+buggy line
 c4
 c5
 c6
@@ -40,9 +40,6 @@ class B {
 d1
 d2
 d3
-added by the fix 1
-added by the fix 2
-added by the fix 3
 d4
 d5
 d6
diff --git a/test/a/BTest.java b/test/a/BTest.java
--- a/test/a/BTest.java
+++ b/test/a/BTest.java
@@ -1,3 +1,3 @@
 t
-x
+y
"""


def test_edit_sites_are_buggy_side_lines_of_production_files_only():
    sites = lineage.edit_sites(REVERSE_PATCH, "src")
    assert sites == [{"path": "src/a/B.java", "first": 13, "last": 13},
                     {"path": "src/a/B.java", "first": 43, "last": 43}]


def test_far_marks_of_one_hunk_are_separate_sites():
    patch = "+++ b/src/X.java\n@@ -1,12 +1,12 @@\n+a\n c\n c\n c\n c\n c\n+b\n+c\n"
    assert lineage.edit_sites(patch, "src") == [{"path": "src/X.java", "first": 1, "last": 1},
                                                 {"path": "src/X.java", "first": 7, "last": 8}]


def test_score_requires_every_site_inside_a_window():
    sites = [{"path": "src/A.java", "first": 100, "last": 102}, {"path": "src/B.java", "first": 5, "last": 5}]
    assert lineage.score(sites, [["src/A.java", 140], ["src/B.java", 45]])["localized"]
    partial = lineage.score(sites, [["src/A.java", 143], ["src/B.java", 45]])
    assert not partial["localized"] and partial["any_site"] and partial["all_files"]
    assert not lineage.score(sites, [["src/A.java", 100]])["all_files"]
    with pytest.raises(lineage.LocalizerError):
        lineage.score([], [])


def test_only_the_first_six_well_formed_locations_count():
    answer = [["a.java", 1], "junk", ["../x.java", 3], ["/abs.java", 3], ["b.java", True], ["c.java", 0]]
    answer += [[f"f{index}.java", index + 1] for index in range(10)]
    kept = lineage.clean_locations(answer)
    assert kept[0] == ["a.java", 1] and len(kept) == lineage.MAX_LOCATIONS
    assert all(".." not in path and not path.startswith("/") for path, _ in kept)
    assert lineage.clean_locations("nonsense") == []


def test_an_unanswered_case_is_a_miss_and_comparison_is_paired():
    truth = {"A-1": [{"path": "s/A.java", "first": 10, "last": 10}],
             "A-2": [{"path": "s/B.java", "first": 10, "last": 10}]}
    parent = lineage.evaluate({"A-1": {"locations": [["s/A.java", 12]]}}, truth, ["A-1", "A-2"])
    child = lineage.evaluate({"A-2": {"locations": [["s/B.java", 9]]}, "A-1": {"error": "Deadline"}}, truth, ["A-1", "A-2"])
    assert parent["localized"] == 1 and child["localized"] == 1 and child["errors"] == 1
    comparison = lineage.compare(child, parent)
    assert comparison["gained_cases"] == ["A-2"] and comparison["lost_cases"] == ["A-1"]
    assert not lineage.promotes(comparison)


def test_promotion_needs_margin_and_significance():
    base = {"parent": 0, "child": 0, "case_count": 100}
    assert lineage.promotes({**base, "gained": 5, "lost": 0, "one_sided_sign_test": 0.03125})
    assert not lineage.promotes({**base, "gained": 4, "lost": 0, "one_sided_sign_test": 0.0625})
    assert not lineage.promotes({**base, "gained": 12, "lost": 7, "one_sided_sign_test": 0.18})


def test_roles_are_fixed_by_name_and_all_three_occur():
    names = [f"Proj-{index}" for index in range(300)]
    roles = {lineage.role_of(name) for name in names}
    assert roles == {"training", "selection", "validation"}
    assert [lineage.role_of(name) for name in names] == [lineage.role_of(name) for name in names]


@pytest.mark.parametrize("source, problem", [
    ("", "empty"),
    ("def other(case):\n    return []\n", "no top-level function"),
    ("import subprocess\ndef localize(case):\n    return []\n", "not allowed"),
    ("from urllib import request\ndef localize(case):\n    return []\n", "not allowed"),
    ("def localize(case:\n", "does not parse"),
    ("def localize(case):\n    return []\n" + "#" * 70_000, "longer than"),
])
def test_unusable_modules_are_refused_without_running(source, problem):
    with pytest.raises(lineage.LocalizerError, match=problem):
        lineage.checked_source(source)


def test_the_seed_passes_the_checks_it_imposes_on_successors():
    source = Path(localizer_seed.__file__).read_text(encoding="utf-8")
    assert lineage.checked_source(source) == source


def test_container_command_keeps_the_boundary(tmp_path):
    command = lineage.container_command("python@sha256:abc", tmp_path / "cases", tmp_path / "run", name="n")
    joined = " ".join(command)
    assert "--network none" in joined and "--read-only" in joined and "--cap-drop ALL" in joined
    assert f"source={tmp_path / 'cases'},target=/cases,readonly" in joined
    assert "target=/candidate,readonly" in joined
    assert "truth" not in joined


def _case(tmp_path: Path) -> Path:
    cases = tmp_path / "cases"
    tree = cases / "P-1" / "tree"
    (tree / "src/p").mkdir(parents=True)
    (tree / "test/p").mkdir(parents=True)
    (tree / "src/p/Thing.java").write_text("\n".join(f"line {n}" for n in range(1, 80)), encoding="utf-8")
    (tree / "test/p/ThingTest.java").write_text("\n".join(f"test {n}" for n in range(1, 40)), encoding="utf-8")
    report = ("--- p.ThingTest::testIt\njunit.framework.AssertionFailedError\n"
              "\tat p.Thing.run(Thing.java:30)\n\tat p.ThingTest.testIt(ThingTest.java:20)\n")
    (cases / "P-1" / "case.json").write_text(json.dumps({
        "source_directory": "src", "test_directory": "test", "failing_tests": ["p.ThingTest::testIt"],
        "report": report}), encoding="utf-8")
    return cases


def test_seed_follows_production_frames_and_falls_back_to_the_tested_class(tmp_path):
    cases = _case(tmp_path)
    case = json.loads((cases / "P-1/case.json").read_text(encoding="utf-8")) | {"root": str(cases / "P-1/tree")}
    assert localizer_seed.localize(case) == [["src/p/Thing.java", 30]]
    case["report"] = "--- p.ThingTest::testIt\n\tat p.ThingTest.testIt(ThingTest.java:20)\n"
    assert localizer_seed.localize(case) == [["src/p/Thing.java", 1]]


def test_miss_description_shows_trace_answer_and_fix_but_no_case_name(tmp_path):
    cases = _case(tmp_path)
    sites = [{"path": "src/p/Thing.java", "first": 75, "last": 75}]
    row = {"locations": [["src/p/Thing.java", 30]], "error": None, **lineage.score(sites, [["src/p/Thing.java", 30]])}
    text = lineage.describe_miss("P-1", row, sites, cases)
    assert "Thing.java:30" in text and "lines 75-75 (MISSED)" in text and "test 20" in text and "line 75" in text
    assert "P-1" not in text
    evaluation = lineage.evaluate({"P-1": {"locations": [["src/p/Thing.java", 30]]}}, {"P-1": sites}, ["P-1"])
    report = lineage.training_report(evaluation, {"P-1": sites}, cases)
    assert report.startswith("Localized 0 of 1 training cases") and "MISSED" in report


def test_archive_keeps_failures_and_their_measured_outcome():
    text = lineage.archive_report([
        {"generation": 1, "index": 1, "outcome": "rejected on unseen cases", "training_localized": 50,
         "training_cases": 200, "selection": {"gained": 3, "lost": 4}, "notes": "ranked by name similarity"},
        {"generation": 1, "index": 2, "outcome": "no usable module", "training_localized": None, "training_cases": 200},
    ])
    assert "rejected on unseen cases (training 50/200, unseen cases +3 -4)" in text and "name similarity" in text
    assert lineage.archive_report([]) == "No earlier attempt."


def _answer(source: str, finish: str = "stop") -> dict:
    return {"choices": [{"finish_reason": finish, "message": {"content": "I rank by X.\n\n```python\n" + source + "\n```"}}],
            "usage": {"cost": 0.001}}


def test_successor_is_extracted_checked_and_charged():
    seed = "def localize(case):\n    return []\n"
    better = "import re\n\ndef localize(case):\n    return [['a.java', 1]]"
    sent = []

    def transport(payload, timeout):
        sent.append(payload)
        return _answer(better)

    ledger = Ledger(1.0)
    written = lineage.write_successor(seed, "report", "No earlier attempt.", Envelope(model="m"), ledger, transport=transport)
    assert written["source"] == better + "\n" and written["notes"] == "I rank by X."
    assert written["calls"][0]["cost_usd"] == 0.001 and ledger.spent == pytest.approx(0.001)
    assert sent[0]["max_tokens"] == 4096 and written["calls"][0]["tokens"] == {"prompt_tokens": None, "completion_tokens": None}
    assert "tools" not in sent[0] and "Earlier attempts" in sent[0]["messages"][1]["content"]


def test_refused_answer_gets_one_correction_then_gives_up():
    seed = "def localize(case):\n    return []\n"
    answers = iter([_answer("import socket\ndef localize(case):\n    return []"), _answer(seed.strip()),
                    _answer("def localize(case):\n    return [['a', 1]]")])
    written = lineage.write_successor(seed, "r", "a", Envelope(model="m"), Ledger(1.0),
                                      transport=lambda payload, timeout: next(answers))
    assert written["source"] is None and len(written["calls"]) == 2
    assert "not allowed" in written["calls"][0]["rejected"] and "identical" in written["calls"][1]["rejected"]


def test_truncated_answer_is_refused():
    written = lineage.write_successor("def localize(case):\n    return []\n", "r", "a", Envelope(model="m"), Ledger(1.0),
                                      transport=lambda payload, timeout: _answer("def localize(case):\n    return [1]", "length"))
    assert written["source"] is None and "cut off" in written["calls"][0]["rejected"]


def test_run_module_reads_partial_output_and_cleans_up(tmp_path):
    cases = _case(tmp_path)
    scratch = tmp_path / "scratch"
    scratch.mkdir()

    def runner(command, **_):
        out = Path(next(part for part in command if part.endswith("target=/out")).split("source=")[1].split(",")[0])
        candidate = out.parent / "candidate"
        assert json.loads((candidate / "cases.json").read_text()) == ["P-1"]
        assert (candidate / "localizer.py").read_text().startswith("def localize")
        (out / "result.json.partial").write_text(json.dumps({"P-1": {"locations": [["src/p/Thing.java", 70]]}}))

    outputs = lineage.run_module("def localize(case):\n    return []\n", ["P-1"], image="i",
                                 cases_directory=cases, scratch=scratch, runner=runner)
    assert outputs == {"P-1": {"locations": [["src/p/Thing.java", 70]]}}
    assert list(scratch.iterdir()) == []
