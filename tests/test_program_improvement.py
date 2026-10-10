import base64
import json
from pathlib import Path
import pickle

import pytest

from genesis import improvement_harness as harness
from genesis import program_improvement as improvement
from genesis.repair_lineage import Envelope, Ledger

SOURCE = '''\
import re

LIMIT = 3


def helper(value):
    return value + 1


@staticmethod
def total(values, start: int = 0) -> int:
    """Sum of the values."""
    result = start
    for value in values:
        result += helper(value) - 1
    return result


def last():
    return LIMIT
'''
ORIGINAL = improvement.function_text(SOURCE, "total")


def rewrite(body: str = "    return start + sum(values)\n", prefix: str = "") -> str:
    return prefix + '@staticmethod\ndef total(values, start: int = 0) -> int:\n' + body


def test_span_covers_decorators_and_only_top_level_functions_count():
    assert improvement.function_span(SOURCE, "total") == (10, 16)
    assert ORIGINAL.startswith("@staticmethod\n") and ORIGINAL.endswith("return result\n")
    with pytest.raises(improvement.ImprovementError):
        improvement.function_span(SOURCE, "missing")


def test_a_rewrite_may_bring_imports_and_new_private_values():
    text = rewrite(prefix="import itertools\nfrom .util import other\nfrom lib.util import more\n_TABLE = (1, 2)\n")
    assert improvement.checked_candidate(text, SOURCE, "total", "lib") == text
    patched = improvement.patched(SOURCE, "total", text)
    assert "_TABLE = (1, 2)\n@staticmethod\ndef total" in patched and "def last():" in patched
    assert "result += helper" not in patched


@pytest.mark.parametrize("candidate, problem", [
    ("", "no function"),
    ("def total(values, start: int = 0) -> int:\n    return 1\n", "must stay exactly"),
    (rewrite().replace("start: int = 0", "start: int = 1"), "must stay exactly"),
    (rewrite().replace("def total", "def other"), "exactly one top-level function"),
    (rewrite() + "\nX = 1\n", "Nothing may follow".lower()),
    (rewrite(prefix="LIMIT = 4\n"), "only imports and assignments"),
    (rewrite(prefix="_cache = {}\nprint(1)\n"), "only imports and assignments"),
    (rewrite(prefix="import requests\n"), "not allowed"),
    (rewrite("    import ctypes\n    return 1\n"), "mentions 'ctypes'"),
    (rewrite("    global LIMIT\n    return 1\n"), "state between calls"),
    (rewrite("    return (\n"), "does not parse"),
    (rewrite("    return 1\n" + "#" * 13_000), "longer than"),
])
def test_unusable_rewrites_are_refused_without_running(candidate, problem):
    with pytest.raises(improvement.ImprovementError, match=problem):
        improvement.checked_candidate(candidate, SOURCE, "total", "lib")


def test_container_command_keeps_the_boundary(tmp_path):
    command = improvement.container_command("image", tmp_path / "tree", tmp_path / "run", ["outcomes", "/harness/spec.json"],
                                            name="n", overlay=(tmp_path / "run/harness/overlay.py", "pkg/mod.py"))
    joined = " ".join(command)
    assert "--network none" in joined and "--read-only" in joined and "--cap-drop ALL" in joined
    assert f"source={tmp_path / 'tree'},target=/tree,readonly" in joined
    assert "target=/tree/pkg/mod.py,readonly" in joined and "valgrind" not in joined
    counted = improvement.container_command("image", tmp_path, tmp_path, ["measure", "s"], name="n", counted=True)
    assert counted[counted.index("image") + 1:counted.index("python")] == [
        "valgrind", "--tool=callgrind", "--instr-atstart=no", "--collect-atstart=no",
        "--callgrind-out-file=/out/callgrind.out"]


def test_shown_calls_are_fixed_by_content_and_never_measured():
    digests = [f"{index:064x}" for index in range(40)]
    shown, hidden, measured = improvement.split_calls(digests)
    assert len(shown) == improvement.SHOWN_CALLS and not set(shown) & set(hidden) and set(measured) <= set(hidden)
    assert sorted(shown + hidden) == list(range(40))
    again = improvement.split_calls(list(reversed(digests)))
    assert {digests[index] for index in shown} == {list(reversed(digests))[index] for index in again[0]}


def test_a_test_counts_as_passing_only_without_any_failed_phase():
    reports = [["a", "call", "passed"], ["b", "call", "passed"], ["b", "teardown", "failed"],
               ["c", "setup", "failed"], ["d", "call", "failed"], ["e", "call", "skipped"]]
    assert improvement.passed_tests(reports) == {"a"}
    assert improvement.passed_tests(None) == set()


# -- the judge and the chain, with the container replaced ---------------------------------------


def make_case(tmp_path: Path, calls: int = 30) -> improvement.Case:
    tree = tmp_path / "packages" / "lib"
    (tree / "lib").mkdir(parents=True)
    (tree / "lib" / "mod.py").write_text(SOURCE, encoding="utf-8")
    blobs = [base64.b64encode(pickle.dumps((([index, index + 1],), {}))).decode() for index in range(calls)]
    shown, hidden, measured = improvement.split_calls([improvement.text_digest(blob) for blob in blobs])
    outcomes = [{"kind": "returned", "digest": f"d{index}", "preview": str(2 * index + 1), "seconds": 0.001,
                 "call": f"[{index}, {index + 1}]"} for index in range(calls)]
    data = {"case": "lib:lib.mod.total", "package": "lib", "version": "1.0", "package_import": "lib", "import_root": "",
            "module": "lib.mod", "name": "total", "file": "lib/mod.py", "file_sha256": improvement.text_digest(SOURCE),
            "outcomes": outcomes, "shown": shown, "hidden": hidden, "measured": measured, "tests": ["tests/test_mod.py"],
            "passing_tests": ["tests/test_mod.py::test_a", "tests/test_mod.py::test_b"], "instructions": 1_000_000}
    directory = tmp_path / "cases" / "lib--lib.mod.total"
    directory.mkdir(parents=True)
    (directory / "case.json").write_text(json.dumps(data), encoding="utf-8")
    (directory / "calls.json").write_text(json.dumps(blobs), encoding="utf-8")
    return improvement.Case(directory, tmp_path / "packages")


def fake_container(case: improvement.Case, seen: list | None = None):
    """Stands for the container: reads directives the test put in the rewritten function."""

    def runner(command, **_):
        harness_directory = Path(next(part for part in command if part.endswith("target=/harness,readonly")).split("source=")[1].split(",")[0])
        out = harness_directory.parent / "out"
        mode = command[command.index("/harness/improvement_harness.py") + 1]
        overlay = harness_directory / "overlay.py"
        text = overlay.read_text(encoding="utf-8") if overlay.is_file() else SOURCE
        count = len(json.loads((harness_directory / "calls.json").read_text(encoding="utf-8")))
        if seen is not None:
            seen.append(mode)
        if mode == "outcomes":
            rows = [dict(row) for row in case.data["outcomes"]]
            if "WRONG_HIDDEN" in text:
                rows[case.data["hidden"][0]]["digest"] = "other"
            if "WRONG_SHOWN" in text:
                rows[case.data["shown"][0]].update(digest="other", preview="41")
            if "HANGS" not in text:
                (out / "result.json").write_text(json.dumps({"outcomes": rows}), encoding="utf-8")
        elif mode == "measure":
            cost = int(text.split("COST=")[1].split()[0]) if "COST=" in text else 1_000_000
            (out / "result.json").write_text(json.dumps({"calls": count}), encoding="utf-8")
            (out / "callgrind.out").write_text(f"events: Ir\ntotals: {cost}\n", encoding="utf-8")
        elif mode == "lines":
            (out / "result.json").write_text(json.dumps({"lines": {"13": 8, "14": 16}}), encoding="utf-8")
        elif mode == "pytest":
            reports = [["tests/test_mod.py::test_a", "call", "passed"],
                       ["tests/test_mod.py::test_b", "call", "failed" if "BREAKS_TEST" in text else "passed"]]
            (out / "tests.json").write_text(json.dumps(reports), encoding="utf-8")

    return runner


def body(directive: str) -> str:
    return rewrite(f"    # {directive}\n    return start + sum(values)\n")


@pytest.mark.parametrize("directive, reason, accepted", [
    ("COST=900000", "accepted", True),
    ("COST=969999", "accepted", True),
    ("COST=970001", "not cheaper", False),
    ("COST=500000 WRONG_HIDDEN", "behaviour differs", False),
    ("COST=500000 WRONG_SHOWN", "behaviour differs", False),
    ("COST=500000 HANGS", "did not finish", False),
    ("COST=500000 BREAKS_TEST", "breaks tests", False),
])
def test_judge_accepts_only_identical_cheaper_and_test_clean(tmp_path, directive, reason, accepted):
    case = make_case(tmp_path)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    verdict = improvement.judge(case, body(directive), 1_000_000, scratch, runner=fake_container(case))
    assert verdict["reason"] == reason and verdict["accepted"] is accepted
    assert list(scratch.iterdir()) == []


def test_a_difference_on_hidden_calls_is_reported_without_showing_them(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "scratch").mkdir()
    hidden = improvement.judge(case, body("WRONG_HIDDEN"), 1_000_000, tmp_path / "scratch", runner=fake_container(case))
    assert hidden["detail"] == "1 of 30 recorded calls behave differently, none of them among the shown calls"
    shown = improvement.judge(case, body("WRONG_SHOWN"), 1_000_000, tmp_path / "scratch", runner=fake_container(case))
    assert "shown call 1 should give returned" in shown["detail"] and "'41'" in shown["detail"]


def test_tests_run_only_for_a_rewrite_that_is_identical_and_cheaper(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "scratch").mkdir()
    seen: list = []
    improvement.judge(case, body("COST=990000"), 1_000_000, tmp_path / "scratch", runner=fake_container(case, seen))
    assert seen == ["outcomes", "measure", "measure"]


def answers(*directives: str):
    queue = list(directives)
    sent: list = []

    def transport(payload, timeout):
        sent.append(payload)
        text = "I replaced the loop.\n\n```python\n" + body(queue.pop(0)) + "```"
        return {"choices": [{"finish_reason": "stop", "message": {"content": text}}], "usage": {"cost": 0.001}}

    return transport, sent


def test_each_accepted_rewrite_is_the_base_of_the_next(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "scratch").mkdir()
    transport, sent = answers("COST=800000", "COST=790000", "COST=600000", "COST=595000", "COST=599000")
    saved: dict = {}
    record = improvement.improve(case, Envelope(model="m"), Ledger(1.0), tmp_path / "scratch", memory="note",
                                 save=saved.__setitem__, transport=transport, runner=fake_container(case))
    assert [step["instructions"] for step in record["chain"]] == [800000, 600000]
    assert record["chain_length"] == 2 and record["final_ratio"] == 0.6 and record["requests"] == 5
    assert [(row["step"], row["attempt"], row["reason"]) for row in record["attempts"]] == [
        (1, 1, "accepted"), (2, 1, "not cheaper"), (2, 2, "accepted"), (3, 1, "not cheaper"), (3, 2, "not cheaper")]
    assert sorted(saved) == ["step1_attempt1.py", "step2_attempt1.py", "step2_attempt2.py", "step3_attempt1.py", "step3_attempt2.py"]
    second = sent[1]["messages"][1]["content"]
    assert "COST=800000" in second and "result += helper" not in second.split("## Current version")[1]
    assert "the current one executes 800000 (-20.0%)" in second and "## What was learned on other functions\n\nnote" in second
    assert "step 2, attempt 1: not cheaper" in sent[2]["messages"][1]["content"]
    assert record["cost_usd"] == pytest.approx(0.005)


def test_without_memory_the_prompt_has_no_such_section_and_shows_only_shown_calls(tmp_path):
    case = make_case(tmp_path)
    (tmp_path / "scratch").mkdir()
    transport, sent = answers("COST=999000", "COST=999000")
    record = improvement.improve(case, Envelope(model="m"), Ledger(1.0), tmp_path / "scratch",
                                 transport=transport, runner=fake_container(case))
    prompt = sent[0]["messages"][1]["content"]
    assert record["chain_length"] == 0 and "What was learned" not in prompt
    for index in case.data["hidden"]:
        assert f"total({case.data['outcomes'][index]['call']})" not in prompt
    for index in case.data["shown"]:
        assert f"total({case.data['outcomes'][index]['call']})" in prompt
    assert "     16 |     for value in values:" in prompt and "def helper(value):" in prompt


def test_a_refused_answer_gets_one_correction():
    replies = iter(["no code here", "```python\n" + body("COST=1") + "```"])

    class Stub:
        source, name, data = SOURCE, "total", {"package_import": "lib"}

    written = improvement.write_candidate(
        [{"role": "user", "content": "x"}], Stub(), ORIGINAL, Envelope(model="m"), Ledger(1.0),
        transport=lambda payload, timeout: {"choices": [{"finish_reason": "stop", "message": {"content": next(replies)}}], "usage": {}})
    assert written["candidate"] == body("COST=1") and len(written["calls"]) == 2
    assert "no fenced Python block" in written["calls"][0]["refused"] and written["calls"][1]["cost_usd"] is None


def record_of(case: str, ratios: list[float], refusals: list[str] = ()) -> dict:
    chain = [{"step": index + 1, "attempt": 1, "instructions": int(ratio * 1000), "ratio_to_original": ratio,
              "note": f"note {case} {index}"} for index, ratio in enumerate(ratios)]
    attempts = [{"accepted": True, "reason": "accepted", "note": step["note"]} for step in chain]
    attempts += [{"accepted": False, "reason": reason, "note": f"tried {reason}"} for reason in refusals]
    return {"case": case, "original_instructions": 1000, "chain_length": len(chain), "chain": chain, "attempts": attempts,
            "final_ratio": ratios[-1] if ratios else 1.0, "requests": len(attempts), "cost_usd": 0.001,
            "unknown_cost_requests": 0}


def test_memory_ranks_accepted_rewrites_by_their_own_step_gain():
    text = improvement.memory_of([record_of("a", [0.9, 0.45]), record_of("b", [], ["behaviour differs", "not cheaper"])])
    assert text.startswith("2 other functions were worked on; 1 got at least one accepted rewrite.")
    assert "1 behaviour differs, 1 not cheaper" in text
    assert text.index("50% fewer instructions: note a 1") < text.index("10% fewer instructions: note a 0")
    assert "- tried behaviour differs" in text
    assert improvement.memory_of([]).startswith("Nothing yet")


def test_summary_pairs_the_arms_after_the_warm_up():
    isolated = [record_of("w", [0.5]), record_of("a", []), record_of("b", [0.9]), record_of("c", [])]
    accumulating = [record_of("w", []), record_of("a", [0.8, 0.7]), record_of("b", [0.6]), record_of("c", [0.95])]
    summary = improvement.summarize({"isolated": isolated, "accumulating": accumulating}, warm_up=1)
    assert summary["arms"]["accumulating"]["chain_lengths"] == {"0": 1, "1": 2, "2": 1}
    assert summary["arms"]["accumulating"]["improved_by_a_second_step"] == 1
    paired = summary["accumulating_against_isolated"]
    assert paired["cases_after_warm_up"] == 3 and paired["improved_only_accumulating"] == 2
    assert paired["improved_only_isolated"] == 0 and paired["improved_sign_test"] == 0.25
    assert paired["cheaper_by_a_point_accumulating"] == 3 and paired["cheaper_sign_test"] == 0.125


# -- the container side, exercised in process ---------------------------------------------------


def test_canonical_form_ignores_set_order_and_keeps_sequence_and_mapping_order():
    canon = harness.canon
    assert canon({3, 1, 2}) == canon({2, 3, 1})
    assert canon([1, 2]) != canon([2, 1]) and canon([1, 2]) != canon((1, 2))
    assert canon({"a": 1, "b": 2}) != canon({"b": 2, "a": 1})
    assert canon(1) != canon(1.0) and canon(True) != canon(1)
    assert canon(iter([1, 2])) == canon(x for x in (1, 2)) != canon([1, 2])


def test_canonical_form_compares_objects_by_state_and_survives_cycles():
    class Box:
        def __init__(self, value):
            self.value = value

    loop: list = [1]
    loop.append(loop)
    assert harness.canon(Box(1)) == harness.canon(Box(1)) != harness.canon(Box(2))
    assert harness.canon(loop)[1][1] == ("cycle",)
    assert harness.canon(object()) == harness.canon(object())
    with pytest.raises(harness.Uncanonical):
        harness.canon(list(range(harness.NODE_LIMIT + 1)))


def test_outcome_covers_result_exception_and_mutated_arguments():
    def blob(*args, **kwargs):
        return pickle.dumps((args, kwargs))

    def push(items, value=0):
        items.append(value)

    def quiet(items, value=0):
        return None

    assert harness.outcome(push, blob([1]), 2)["digest"] != harness.outcome(quiet, blob([1]), 2)["digest"]
    raised = harness.outcome(lambda value: 1 // value, blob(0), 2)
    assert raised["kind"] == "raised" and raised["preview"].startswith("ZeroDivisionError")
    lazy = harness.outcome(lambda count: (index for index in range(count)), blob(3), 2)
    assert lazy["kind"] == "returned" and lazy["digest"] != harness.outcome(lambda count: list(range(count)), blob(3), 2)["digest"]
    assert harness.outcome(push, b"not a pickle", 2)["kind"] == "unloadable"
    assert harness.outcome(push, blob([1], value=2), 2)["call"] == "[1], value=2"


def test_only_plain_top_level_functions_of_a_few_lines_are_recorded():
    found = harness.top_level_functions(SOURCE)
    assert found == [{"name": "total", "first": 10, "last": 16}]


def test_a_rewrite_that_drops_a_value_it_still_uses_is_refused_before_running():
    champion = rewrite("    return start + sum(values) + _BASE\n", prefix="_BASE = 0\n")
    replies = iter(["```python\n" + rewrite("    return _BASE + start + sum(values)\n") + "```",
                    "```python\n" + rewrite("    return _BASE + start + sum(values)\n", prefix="_BASE = 0\n") + "```"])

    class Stub:
        source, name, data = SOURCE, "total", {"package_import": "lib"}

    written = improvement.write_candidate(
        [{"role": "user", "content": "x"}], Stub(), champion, Envelope(model="m"), Ledger(1.0),
        transport=lambda payload, timeout: {"choices": [{"finish_reason": "stop", "message": {"content": next(replies)}}], "usage": {}})
    assert "uses _BASE without defining it" in written["calls"][0]["refused"]
    assert written["candidate"].startswith("_BASE = 0\n")
