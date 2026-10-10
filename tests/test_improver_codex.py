import json

import pytest

from genesis import improver_codex as codex
from genesis.repair_lineage import BudgetExhausted, ModelUnavailable


def _runner(answer="```python\nx = 1\n```", log="tokens used\n1,234\n", code=0):
    seen = []

    def run(argv, prompt, directory, timeout):
        seen.append((list(argv), prompt, directory))
        if answer:
            (directory / "answer.txt").write_text(answer, encoding="utf-8")
        return code, log
    run.seen = seen
    return run


def test_a_request_runs_read_only_in_an_empty_directory_and_is_recorded(tmp_path):
    runner = _runner()
    model = codex.CodexModel(tmp_path / "calls.jsonl", {"use": "t"}, per_day=3, runner=runner)
    assert model("write x", None) == "```python\nx = 1\n```"
    argv, prompt, directory = runner.seen[0]
    assert argv[:2] == ["codex", "exec"] and argv[argv.index("-s") + 1] == "read-only" and argv[-1] == "-"
    assert argv[argv.index("-m") + 1] == codex.MODEL and f"model_reasoning_effort={codex.EFFORT}" in argv
    assert prompt.startswith(codex.PREAMBLE) and prompt.endswith("write x") and not directory.exists()
    rows = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert [row["state"] for row in rows] == ["sent", "answered"] and rows[1]["tokens_used"] == 1234
    assert rows[0]["use"] == "t" and rows[0]["day"] == codex.today()


def test_the_daily_ceiling_holds_across_instances_and_other_days_do_not_count(tmp_path):
    journal = tmp_path / "calls.jsonl"
    journal.write_text(json.dumps({"day": "2000-01-01", "state": "sent"}) + "\n", encoding="utf-8")
    first = codex.CodexModel(journal, {}, per_day=2, runner=_runner())
    first("a", None)
    second = codex.CodexModel(journal, {}, per_day=2, runner=_runner())
    second("b", None)
    assert second.used_today() == 2
    with pytest.raises(BudgetExhausted):
        first("c", None)


def test_a_refusal_by_the_subscription_stops_and_another_failure_is_an_empty_answer(tmp_path):
    refused = codex.CodexModel(tmp_path / "a.jsonl", {}, per_day=5, runner=_runner(answer="", log="You've hit your usage limit", code=1))
    with pytest.raises(ModelUnavailable):
        refused("a", None)
    broken = codex.CodexModel(tmp_path / "b.jsonl", {}, per_day=5, runner=_runner(answer="", log="segfault", code=1))
    assert broken("a", None) == ""
    assert json.loads((tmp_path / "b.jsonl").read_text().splitlines()[-1])["state"] == "failed"
