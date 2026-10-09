"""The repair bench: a split nobody chooses, edits that apply or are dropped, one validation for all."""
from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from genesis.repair_bench import (
    EXPOSED, Candidate, RepairBenchError, apply_edits, build_split, next_held_out, run_arm, validate,
)
from genesis.repair_proposers import model_proposer, render_prompt

ACTIVE = [(project, bug) for project in ("Math", "Cli", "Lang", "Codec") for bug in range(1, 41)]


def test_the_split_is_a_function_of_the_case_names_only() -> None:
    first, second = build_split(ACTIVE), build_split(list(reversed(ACTIVE)) + ACTIVE[:5])
    assert first == second
    assert set(first["held_out"]).isdisjoint(first["development"])
    assert len(first["held_out"]) + len(first["development"]) == len(ACTIVE)
    assert 10 < len(first["held_out"]) < 50, "about one unexposed case in five is held out"


def test_an_exposed_case_or_project_is_never_held_out() -> None:
    split = build_split(ACTIVE + sorted(EXPOSED))
    held_out = set(split["held_out"])
    assert not any(name.startswith("Lang-") for name in held_out)
    assert held_out.isdisjoint(f"{project}-{bug}" for project, bug in EXPOSED)
    assert "Codec-15" in split["development"]


def test_trials_consume_held_out_cases_in_the_frozen_order() -> None:
    split = build_split(ACTIVE)
    first = next_held_out(split, [], 3)
    assert first == split["held_out"][:3]
    assert next_held_out(split, first, 2) == split["held_out"][3:5]
    with pytest.raises(RepairBenchError):
        next_held_out(split, ["Math-999"], 1)
    with pytest.raises(RepairBenchError):
        next_held_out(split, [], len(split["held_out"]) + 1)


def test_an_edit_applies_only_when_its_text_occurs_exactly_once(tmp_path) -> None:
    (tmp_path / "A.java").write_text("int a = 1;\nint b = 1;\nreturn a;\n", encoding="utf-8")
    applied = apply_edits(tmp_path, "A.java", [("return a;", "return a + b;")], "t")
    assert applied is not None and applied.content.endswith("return a + b;\n")
    chained = apply_edits(tmp_path, "A.java", [("int a = 1;", "int a = 2;"), ("int a = 2;", "int a = 3;")], "t")
    assert chained is not None and "int a = 3;" in chained.content
    for edits in ([("= 1;", "= 2;")], [("absent", "x")], [("return a;", "return a;")], [("", "x")], []):
        assert apply_edits(tmp_path, "A.java", edits, "t") is None
    for path in ("../A.java", str(tmp_path / "A.java"), "Missing.java", ""):
        assert apply_edits(tmp_path, path, [("return a;", "return b;")], "t") is None


class _Run:
    def __init__(self, ok: bool) -> None:
        self.ok = ok
        self.output = "" if ok else "    [javac] A.java:1: error: not a statement\nBUILD FAILED"


class _Sandbox:
    """Stands in for the container: compiles unless the file says BROKEN, fails tests named in it."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.log: list[str] = []

    def _text(self, directory: str) -> str:
        return (self.workspace / directory / "A.java").read_text(encoding="utf-8")

    def compile(self, directory: str) -> _Run:
        self.log.append("compile")
        return _Run("BROKEN" not in self._text(directory))

    def test(self, directory: str, *, single_test: str | None = None, relevant_only: bool = False) -> _Run:
        self.log.append(f"test:{single_test or 'all'}")
        text = self._text(directory)
        failing = "TRIGGER" in text if single_test else "REGRESSION" in text
        (self.workspace / directory / "failing_tests").write_text("--- x.T::t\n" if failing else "", encoding="utf-8")
        return _Run(True)

    def failing_tests(self, directory: str) -> list[str]:
        text = (self.workspace / directory / "failing_tests").read_text(encoding="utf-8")
        return ["x.T::t"] if text else []


def _case(tmp_path: Path) -> _Sandbox:
    (tmp_path / "case").mkdir()
    (tmp_path / "case" / "A.java").write_text("TRIGGER original\n", encoding="utf-8")
    return _Sandbox(tmp_path)


@pytest.mark.parametrize("content, stage, plausible", [
    ("BROKEN", "compile", False),
    ("TRIGGER still", "failing_tests", False),
    ("REGRESSION elsewhere", "full_suite", False),
    ("fixed", "passed", True),
])
def test_a_candidate_must_compile_pass_the_failing_tests_then_the_whole_suite(tmp_path, content, stage, plausible) -> None:
    sandbox = _case(tmp_path)
    verdict = validate(sandbox, "case", Candidate("A.java", content, "t"), ["x.T::t"])
    assert (verdict["stopped_at"], verdict["plausible"]) == (stage, plausible)
    assert (verdict["feedback"] is not None) == (stage != "passed")
    assert (tmp_path / "case" / "A.java").read_text(encoding="utf-8") == "TRIGGER original\n", "the checkout is restored"


def test_the_full_suite_is_not_run_for_a_candidate_that_still_fails_its_trigger(tmp_path) -> None:
    sandbox = _case(tmp_path)
    validate(sandbox, "case", Candidate("A.java", "TRIGGER still", "t"), ["x.T::t"])
    assert "test:all" not in sandbox.log


def test_an_arm_validates_distinct_candidates_up_to_its_budget_and_stops_when_solved(tmp_path) -> None:
    sandbox = _case(tmp_path)
    proposals = [Candidate("A.java", text, "t") for text in ("BROKEN", "BROKEN", "TRIGGER x", "fixed", "fixed 2")]
    once = lambda root, evidence, history, remaining: [] if history else proposals
    outcome = run_arm(sandbox, "case", {"failing_tests": ["x.T::t"]}, once, budget=4)
    assert (outcome["proposed"], outcome["validated"]) == (5, 3), "duplicates cost nothing; stop at the first pass"
    assert outcome["solved"] and outcome["first_plausible_rank"] == 3
    assert outcome["plausible_patch"].startswith("--- a/A.java") and "+fixed" in outcome["plausible_patch"]
    unlucky = run_arm(sandbox, "case", {"failing_tests": ["x.T::t"]}, once, budget=2)
    assert not unlucky["solved"] and unlucky["validated"] == 2


def test_later_rounds_see_earlier_verdicts_and_the_remaining_budget(tmp_path) -> None:
    sandbox = _case(tmp_path)
    seen: list[tuple[list[str], int]] = []

    def learner(root, evidence, history, remaining):
        seen.append(([verdict["stopped_at"] for _, verdict in history], remaining))
        return [Candidate("A.java", "fixed" if history else "BROKEN", "t", "first try")]

    outcome = run_arm(sandbox, "case", {"failing_tests": ["x.T::t"]}, learner, budget=5)
    assert seen == [([], 5), (["compile"], 4)]
    assert outcome["solved"] and outcome["rounds"] == 2 and outcome["validated"] == 2


def test_an_arm_that_repeats_itself_is_stopped(tmp_path) -> None:
    sandbox = _case(tmp_path)
    stuck = lambda root, evidence, history, remaining: [Candidate("A.java", "BROKEN", "t")]
    outcome = run_arm(sandbox, "case", {"failing_tests": ["x.T::t"]}, stuck, budget=5)
    assert outcome["validated"] == 1 and outcome["rounds"] == 2 and not outcome["solved"]


EVIDENCE = {
    "evidence_digest": "e" * 64, "source_directory": "src", "test_directory": "test",
    "traces": [{"test": "x.FooTest::testBar", "trace": "java.lang.NullPointerException\n\tat x.Foo.bar(Foo.java:3)"}],
    "test_source": [{"path": "test/x/FooTest.java", "first_line": 1, "last_line": 1, "numbered_source": "    1| assertEquals(1, foo.bar());"}],
    "production_source": [{"path": "src/x/Foo.java", "first_line": 1, "last_line": 3, "numbered_source": "    1| class Foo {\n    2|   int bar() {\n    3|     return v.size();"}],
}


def test_the_prompt_carries_the_buggy_side_evidence_and_no_benchmark_identity() -> None:
    prompt = render_prompt(EVIDENCE, 4)
    assert "x.FooTest::testBar" in prompt and "return v.size();" in prompt and "Propose 4 DIFFERENT" in prompt
    assert prompt == render_prompt(EVIDENCE, 4)
    tried = Candidate("src/x/Foo.java", "x", "t", "Hypothesis: null list")
    again = render_prompt(EVIDENCE, 2, [(tried, {"stopped_at": "compile", "feedback": "error: cannot find symbol"})])
    assert "Attempt 1: did not compile" in again and "cannot find symbol" in again and "Hypothesis: null list" in again
    for leak in ("Defects4J", "defects4j", "bug id", "fixed revision"):
        assert leak not in prompt


def _fake_model(tmp_path: Path, answer: dict | None, status: int = 0) -> str:
    path = tmp_path / "claude"
    payload = json.dumps({"structured_output": answer, "total_cost_usd": 0.01}) if answer is not None else "not json"
    path.write_text(f"#!/bin/sh\ncat <<'ANSWER'\n{payload}\nANSWER\nexit {status}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_model_proposals_become_candidates_only_when_they_apply(tmp_path) -> None:
    root = tmp_path / "checkout"
    (root / "src/x").mkdir(parents=True)
    (root / "src/x/Foo.java").write_text("class Foo {\n  int bar() {\n    return v.size();\n  }\n}\n", encoding="utf-8")
    answer = {"candidates": [
        {"hypothesis": "null list", "path": "src/x/Foo.java",
         "edits": [{"search": "return v.size();", "replace": "return v == null ? 0 : v.size();"}]},
        {"hypothesis": "wrong text", "path": "src/x/Foo.java", "edits": [{"search": "return w.size();", "replace": "return 0;"}]},
        {"hypothesis": "edits a test", "path": "test/x/FooTest.java", "edits": [{"search": "assertEquals(1", "replace": "assertEquals(0"}]},
        {"hypothesis": "escapes", "path": "src/../test/x/FooTest.java", "edits": [{"search": "assertEquals(1", "replace": "assertEquals(0"}]},
    ]}
    (root / "test/x").mkdir(parents=True)
    (root / "test/x/FooTest.java").write_text("assertEquals(1, foo.bar());\n", encoding="utf-8")
    calls: list[dict] = []
    proposer = model_proposer("some-model", 5, calls, executable=_fake_model(tmp_path, answer))
    candidates = proposer(root, EVIDENCE, (), 5)
    assert [candidate.origin for candidate in candidates] == ["model:some-model"]
    assert "v == null ? 0" in candidates[0].content and "Hypothesis: null list" in candidates[0].description
    assert calls[0]["returned"] == 4 and calls[0]["applicable"] == 1, "a proposal that edits a test is dropped"
    assert calls[0]["applicable"] == 1 and calls[0]["cost_usd"] == 0.01
    assert calls[0]["benchmark_may_be_in_training_data"] is True


def test_a_model_that_answers_garbage_yields_no_candidate_and_a_recorded_error(tmp_path) -> None:
    calls: list[dict] = []
    proposer = model_proposer("some-model", 5, calls, executable=_fake_model(tmp_path, None), retry_wait_seconds=0)
    assert list(proposer(tmp_path, EVIDENCE, (), 5)) == []
    assert calls[0]["applicable"] == 0 and calls[0]["error"] == "JSONDecodeError" and calls[0]["call_failed"]


def test_a_failed_model_call_is_retried_once_and_recorded_as_a_failure_not_as_an_empty_answer(tmp_path) -> None:
    calls: list[dict] = []
    refused = _fake_model(tmp_path, {"candidates": []}, status=1)
    proposer = model_proposer("some-model", 5, calls, executable=refused, retry_wait_seconds=0)
    assert list(proposer(tmp_path, EVIDENCE, (), 5)) == []
    assert calls[0]["attempts"] == 2 and calls[0]["call_failed"] is True


def test_a_failure_of_the_environment_is_not_held_against_a_candidate(tmp_path) -> None:
    sandbox = _case(tmp_path)
    blamed = validate(sandbox, "case", Candidate("A.java", "REGRESSION elsewhere", "t"), ["x.T::t"])
    spared = validate(sandbox, "case", Candidate("A.java", "REGRESSION elsewhere", "t"), ["x.T::t"], ["x.T::t"])
    assert (blamed["plausible"], spared["plausible"]) == (False, True)


class _EnvironmentSandbox:
    """A buggy revision where one trigger fails and two other tests fail for want of a network."""

    def __init__(self, workspace: Path, triggers: str) -> None:
        self.workspace, self.triggers = workspace, triggers

    def export(self, directory: str, prop: str) -> _Run:
        run = _Run(True)
        run.output = {"dir.src.classes": "src", "dir.src.tests": "test", "tests.trigger": self.triggers}[prop]
        return run

    def compile(self, directory: str) -> _Run:
        return _Run(True)

    def test(self, directory: str, *, single_test: str | None = None, relevant_only: bool = False) -> _Run:
        report = (
            "--- p.ATest::bug\njava.lang.AssertionError\n\tat p.A.value(A.java:2)\n"
            "--- p.ATest::host\njava.net.UnknownHostException\n\tat p.Net.lookup(Net.java:1)\n"
        ) + ("" if relevant_only else "--- q.BTest::home\njava.lang.AssertionError\n")
        (self.workspace / directory / "failing_tests").write_text(report, encoding="utf-8")
        return _Run(True)

    def failing_tests(self, directory: str) -> list[str]:
        text = (self.workspace / directory / "failing_tests").read_text(encoding="utf-8")
        return [line[4:] for line in text.splitlines() if line.startswith("--- ")]


def _environment_case(tmp_path: Path, triggers: str) -> _EnvironmentSandbox:
    for name in ("case/src/p", "case/test/p"):
        (tmp_path / name).mkdir(parents=True)
    (tmp_path / "case/src/p/A.java").write_text("class A {\n int value() { return 1; }\n}\n", encoding="utf-8")
    (tmp_path / "case/src/p/Net.java").write_text("class Net {}\n", encoding="utf-8")
    return _EnvironmentSandbox(tmp_path, triggers)


def test_evidence_keeps_the_declared_triggers_and_sets_environment_failures_aside(tmp_path) -> None:
    from genesis.repair_bench import collect_evidence

    plain = collect_evidence(_environment_case(tmp_path, "p.ATest::bug"), "case")
    assert plain["failing_tests"] == ["p.ATest::bug", "p.ATest::host"] and "tolerated_failures" not in plain
    evidence = collect_evidence(_environment_case(tmp_path / "again", "p.ATest::bug"), "case", separate_environment=True)
    assert evidence["failing_tests"] == ["p.ATest::bug"]
    assert evidence["tolerated_failures"] == ["p.ATest::host", "q.BTest::home"]
    assert [trace["test"] for trace in evidence["traces"]] == ["p.ATest::bug"]
    assert evidence["suspect_locations"] == [["src/p/A.java", 2]]


def test_a_case_whose_triggers_do_not_fail_here_is_unusable(tmp_path) -> None:
    from genesis.repair_bench import RepairBenchError, collect_evidence

    with pytest.raises(RepairBenchError):
        collect_evidence(_environment_case(tmp_path, "p.Other::test"), "case", separate_environment=True)
