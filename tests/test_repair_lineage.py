import json

import pytest

from genesis.repair_lineage import (
    SEED_GENOME, BudgetExhausted, Envelope, GenomeError, Ledger, ModelUnavailable, checked_genome,
    exact_sign_test, fits, genome_digest, lineage_proposer, promotes, render_case, training_report,
    write_successor,
)

ENVELOPE = Envelope(model="test/model")


def setup(root):
    (root / "src").mkdir()
    (root / "test").mkdir()
    (root / "src/A.java").write_text("class A {\n  int value() { return 1; }\n}\n")
    return {
        "source_directory": "src", "test_directory": "test", "evidence_digest": "e",
        "failing_tests": ["ATest::value"], "suspects_from_stack_trace": True,
        "suspect_locations": [["src/A.java", 2]],
        "traces": [{"test": "ATest::value", "trace": "\n".join(f"line {n}" for n in range(40))}],
        "test_source": [{"path": "test/ATest.java", "numbered_source": "    1| assertEquals(0, a.value());"}],
        "production_source": [],
    }


def answer(name, arguments, cost=0.001):
    return {"usage": {"cost": cost, "prompt_tokens": 10, "completion_tokens": 5}, "choices": [{
        "finish_reason": "tool_calls", "message": {"role": "assistant", "content": None, "tool_calls": [
            {"id": "t1", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]}}]}


def repair(search="return 1;", path="src/A.java"):
    return {"candidates": [{"hypothesis": "wrong value", "path": path,
                            "edits": [{"search": search, "replace": "return 0;"}]}]}


def scripted(*answers):
    queue, seen = list(answers), []

    def send(payload, timeout):
        seen.append(json.loads(json.dumps(payload)))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    return send, seen


def genome(**search):
    value = json.loads(json.dumps(SEED_GENOME))
    value["search"].update(search)
    return value


def test_seed_genome_is_valid_and_fits_the_envelope():
    seed = checked_genome(SEED_GENOME)
    assert fits(seed, ENVELOPE) and seed["schema"]
    assert genome_digest(seed) == genome_digest(json.loads(json.dumps(seed)))


@pytest.mark.parametrize("change", [
    {"instructions": ""}, {"playbook": "x" * 4001}, {"evidence": {"radius": 500, "max_locations": 2,
     "trace_lines": 10, "test_source": True}}, {"search": {"inspection_requests": 1, "candidates_per_round": 9,
     "rounds": 1}}, {"search": {"inspection_requests": True, "candidates_per_round": 1, "rounds": 1}},
    {"evidence": {"radius": 40, "max_locations": 2, "trace_lines": 10, "test_source": "yes"}},
])
def test_out_of_bounds_genomes_are_refused(change):
    with pytest.raises(GenomeError):
        checked_genome({**SEED_GENOME, **change})


def test_a_genome_cannot_plan_more_requests_than_the_envelope(tmp_path):
    greedy = genome(inspection_requests=7, rounds=4)
    assert not fits(checked_genome(greedy), ENVELOPE)
    with pytest.raises(GenomeError):
        lineage_proposer(greedy, ENVELOPE, Ledger(1.0), [])


def test_rendering_follows_the_genome_and_shows_only_buggy_evidence(tmp_path):
    evidence = setup(tmp_path)
    lean = checked_genome({**SEED_GENOME, "playbook": "Check off-by-one first.",
                           "evidence": {"radius": 10, "max_locations": 1, "trace_lines": 5, "test_source": False}})
    text = render_case(lean, tmp_path, evidence, 2, (), 60_000)
    assert "Check off-by-one first." in text and "line 4" in text and "line 5" not in text
    assert "assertEquals" not in text and "return 1;" in text and "at most 2 candidate" in text
    assert "assertEquals" in render_case(checked_genome(SEED_GENOME), tmp_path, evidence, 2, (), 60_000)


def test_agent_inspects_then_submits_and_leaves_the_checkout_alone(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(answer("read_file", {"path": "src/A.java"}), answer("submit_repairs", repair()))
    calls, ledger = [], Ledger(1.0)
    proposer = lineage_proposer(genome(), ENVELOPE, ledger, calls, transport=send)
    candidates = proposer(tmp_path, evidence, (), 6)
    assert len(candidates) == 1 and "return 0;" in candidates[0].content
    assert "return 1;" in (tmp_path / "src/A.java").read_text()
    assert [call["step"] for call in calls] == [1, 2] and calls[0]["inspections"][0]["tool"] == "read_file"
    assert ledger.spent == pytest.approx(0.002)
    assert len(seen[0]["tools"]) == 3


def test_inapplicable_and_test_edits_are_counted_not_validated(tmp_path):
    evidence = setup(tmp_path)
    both = {"candidates": repair(search="return 7;")["candidates"] + repair(path="test/ATest.java")["candidates"]}
    send, _ = scripted(answer("submit_repairs", both))
    calls = []
    proposer = lineage_proposer(genome(inspection_requests=0), ENVELOPE, Ledger(1.0), calls, transport=send)
    assert proposer(tmp_path, evidence, (), 6) == []
    assert calls[0]["submitted"] == 2 and calls[0]["inapplicable"] == 2 and calls[0]["applicable"] == 0


def test_requests_stop_at_the_envelope(tmp_path):
    evidence = setup(tmp_path)
    looks = [answer("read_file", {"path": "src/A.java"}) for _ in range(3)]
    send, seen = scripted(*looks, answer("submit_repairs", {"candidates": []}), *looks)
    calls = []
    tight = Envelope(model="test/model", requests=5)
    proposer = lineage_proposer(genome(inspection_requests=3, rounds=1), tight, Ledger(1.0), calls, transport=send)
    proposer(tmp_path, evidence, (), 6)
    proposer(tmp_path, evidence, (), 6)
    assert len(seen) == 5 and proposer(tmp_path, evidence, (), 6) == []


def test_malformed_answer_ends_the_round_and_is_recorded(tmp_path):
    evidence = setup(tmp_path)
    plain = {"usage": {"cost": 0.001}, "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "hm"}}]}
    send, _ = scripted(plain)
    calls = []
    proposer = lineage_proposer(genome(), ENVELOPE, Ledger(1.0), calls, transport=send)
    assert proposer(tmp_path, evidence, (), 6) == [] and "no tool call" in calls[0]["malformed"]


def test_unreachable_provider_is_not_a_measurement(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(TimeoutError(), TimeoutError())
    proposer = lineage_proposer(genome(), ENVELOPE, Ledger(1.0), [], transport=send)
    with pytest.raises(ModelUnavailable):
        proposer(tmp_path, evidence, (), 6)
    assert len(seen) == 2


def test_ledger_refuses_before_sending_and_keeps_unknown_costs(tmp_path):
    evidence = setup(tmp_path)
    send, seen = scripted(answer("submit_repairs", repair()))
    with pytest.raises(BudgetExhausted):
        lineage_proposer(genome(), ENVELOPE, Ledger(0.0001), [], transport=send)(tmp_path, evidence, (), 6)
    assert seen == []
    ledger = Ledger(1.0)
    ledger.reserve(0.01)
    ledger.settle(0.01, None)
    assert ledger.spent == pytest.approx(0.01)


def evaluation(solved):
    return {"cases": {name: {
        "solved": flag, "failing_tests": 1, "suspects_from_stack_trace": True, "validated": 1,
        "calls": [{"step": 1, "submitted": 1, "inapplicable": 0,
                   "inspections": [{"tool": "read_file", "arguments": {"path": "src/A.java"}, "characters": 9}]}],
        "verdicts": [{"path": "src/A.java", "stopped_at": "passed" if flag else "compile",
                      "feedback": None if flag else "error: ';' expected"}],
    } for name, flag in solved.items()}}


def test_training_report_withholds_case_names():
    report = training_report(evaluation({"Math-3": True, "Cli-9": False}), ["Math-3", "Cli-9"])
    assert "Repaired 1 of 2" in report and "Case A: REPAIRED" in report and "';' expected" in report
    assert "Math" not in report and "Cli" not in report


def test_promotion_needs_a_strict_gain_without_losing_on_selection():
    parent = evaluation({"t1": True, "t2": False, "s1": True, "s2": False})
    assert promotes(evaluation({"t1": True, "t2": True, "s1": True, "s2": False}), parent, ["s1", "s2"])
    assert not promotes(evaluation({"t1": True, "t2": False, "s1": True, "s2": False}), parent, ["s1", "s2"])
    assert not promotes(evaluation({"t1": True, "t2": True, "s1": False, "s2": False}), parent, ["s1", "s2"])
    gain_on_training_only = evaluation({"t1": True, "t2": True, "s1": False, "s2": True})
    assert promotes(gain_on_training_only, parent, ["s1", "s2"])


def test_successor_is_checked_and_one_correction_is_allowed():
    child = {**json.loads(json.dumps(SEED_GENOME)), "rationale": "fewer wasted reads", "playbook": "Read first."}
    greedy = {**child, "search": {"inspection_requests": 7, "candidates_per_round": 2, "rounds": 4}}
    send, seen = scripted(answer("submit_genome", greedy), answer("submit_genome", child))
    written = write_successor(SEED_GENOME, "Repaired 0 of 2", ENVELOPE, Ledger(1.0), transport=send)
    assert written["genome"]["playbook"] == "Read first." and written["rationale"] == "fewer wasted reads"
    assert "rejected" in written["calls"][0] and "refused" in seen[1]["messages"][-1]["content"]
    assert SEED_GENOME["improver"] in seen[0]["messages"][1]["content"]
    send, seen = scripted(answer("submit_genome", greedy), answer("submit_genome", greedy))
    assert write_successor(SEED_GENOME, "r", ENVELOPE, Ledger(1.0), transport=send)["genome"] is None
    send, seen = scripted(answer("submit_genome", child))
    write_successor(SEED_GENOME, "r", ENVELOPE, Ledger(1.0), improver="OTHER GUIDE", transport=send)
    assert seen[0]["messages"][1]["content"].startswith("OTHER GUIDE")


def test_exact_sign_test():
    assert exact_sign_test(0, 0) == 1.0
    assert exact_sign_test(0, 5) == pytest.approx(1 / 32)
    assert exact_sign_test(3, 3) == pytest.approx(42 / 64)
