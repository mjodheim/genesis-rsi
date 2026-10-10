import json
import sys

import pytest

from genesis import improver_lineage as lineage
from genesis import improver_runtime as runtime

LOCAL = [sys.executable, "-I", str(lineage.RUNTIME)]
GREEDY = '''
def solve(instance):
    points = instance["points"]
    left, order = set(range(1, len(points))), [0]
    while left:
        last = points[order[-1]]
        nearest = min(left, key=lambda i: (points[i][0] - last[0]) ** 2 + (points[i][1] - last[1]) ** 2)
        left.remove(nearest)
        order.append(nearest)
    return order
'''


def test_every_family_scores_its_trivial_answer_zero_and_is_reproducible():
    assert len(runtime.FAMILIES) == 12
    assert sorted(name for name, spec in runtime.FAMILIES.items() if spec["role"] == "development") == sorted(lineage.DEVELOPMENT)
    assert sorted(name for name, spec in runtime.FAMILIES.items() if spec["role"] == "held_out") == sorted(lineage.HELD_OUT)
    for name, spec in runtime.FAMILIES.items():
        assert spec["gen"](3) == spec["gen"](3) and spec["gen"](3) != spec["gen"](4)
        assert runtime.evaluated(runtime.baseline_source(name), name, [3])[0] == {"seed": 3, "quality": 0.0, "cost": runtime.evaluated(runtime.baseline_source(name), name, [3])[0]["cost"], "error": None}, name


def test_a_better_program_scores_higher_and_failures_score_zero():
    rows = runtime.evaluated(GREEDY, "tsp", [1, 2])
    assert all(0.5 < row["quality"] < 1 and row["error"] is None for row in rows)
    assert [row["quality"] for row in runtime.evaluated("def solve(i):\n    return [0]", "tsp", [1])] == [0.0]
    assert "timeout" in runtime.evaluated("def solve(i):\n    while True: pass", "tsp", [1])[0]["error"]
    assert runtime.evaluated("import nothing_here", "tsp", [1])[0]["quality"] == 0.0
    assert "runtime" in runtime.evaluated("import improver_runtime\ndef solve(i): return []", "tsp", [1])[0]["error"]
    main_guard = GREEDY + "\nif __name__ == '__main__':\n    print(1)\n"
    assert runtime.evaluated(main_guard, "tsp", [1])[0]["quality"] > 0.5
    assert lineage.score(GREEDY, "tsp", [5, 6], command=[*LOCAL, "score"]) > 0.5
    assert lineage.score(None, "tsp", [5]) == 0.0


def test_hidden_answers_are_not_in_what_a_program_receives():
    for name in ("regression", "sequence"):
        public, secret = runtime.FAMILIES[name]["gen"](7)
        assert secret and json.dumps(secret) not in json.dumps(public)


def _model(replies):
    asked = []

    def model(prompt, temperature):
        asked.append(prompt)
        return replies(prompt, len(asked))
    model.asked = asked
    return model


def test_the_seed_improver_runs_on_a_task_within_its_budget():
    model = _model(lambda prompt, count: f"Here:\n```python\n{GREEDY}\n```" if count == 1 else "no code")
    spec = lineage.object_spec("tsp", 4)
    ran = lineage.run_improver(lineage.SEED.read_text(), spec, model, command=[*LOCAL, "run"])
    assert ran["error"] is None and "nearest" in ran["solution"]
    assert ran["lm_calls"] == len(model.asked) == spec["budget"]["lm_calls"]
    assert "Travelling salesman" in model.asked[0] and "score 0.0000" in model.asked[0]


def test_the_host_refuses_requests_beyond_the_budget_whatever_the_improver_counts():
    greedy_improver = '''
def improve(task, lm, budget):
    budget.lm_calls = 10 ** 6
    answers = []
    try:
        for _ in range(50):
            answers.append(lm("more"))
    except Exception:
        pass
    return "# " + str(len(answers))
'''
    model = _model(lambda prompt, count: "ok")
    ran = lineage.run_improver(greedy_improver, lineage.object_spec("tsp", 4), model, command=[*LOCAL, "run"])
    assert len(model.asked) == lineage.OBJECT_BUDGET["lm_calls"] and ran["solution"] == "# 6"


def test_a_failing_improver_gives_back_the_initial_program():
    ran = lineage.run_improver("def improve(task, lm, budget):\n    raise RuntimeError('x')", lineage.object_spec("tsp", 4),
                               _model(lambda prompt, count: ""), command=[*LOCAL, "run"])
    assert ran["error"].startswith("RuntimeError") and ran["solution"] == runtime.baseline_source("tsp")


def test_the_seed_improver_improves_an_improver_and_its_requests_are_all_counted():
    better = lineage.SEED.read_text().replace("You are improving a program.", "You are improving a program. Think first.")

    def replies(prompt, count):
        if "itself an improver" in prompt:
            return f"```python\n{better}\n```"
        return f"```python\n{GREEDY}\n```" if "Travelling" in prompt and "Think first." in prompt else "nothing"
    model = _model(replies)
    spec = lineage.meta_spec(lineage.SEED.read_text(), [("tsp", 1), ("binpack", 2)])
    spec["budget"] = {"lm_calls": 30, "evaluations": 2, "seconds": 300}
    spec["child_budget"] = {"lm_calls": 2, "evaluations": 3, "seconds": 120}
    ran = lineage.run_improver(lineage.SEED.read_text(), spec, model, command=[*LOCAL, "run"])
    assert ran["error"] is None and "Think first." in ran["solution"]
    meta = [prompt for prompt in model.asked if "itself an improver" in prompt]
    assert len(meta) == 1 and "score 0.0000" in meta[0] and "def improve(task, lm, budget)" in meta[0]
    assert ran["lm_calls"] == len(model.asked) == 1 + 2 * 2 * 2
    assert sum("Think first." in prompt for prompt in model.asked) == 4


def test_promotion_needs_wins_a_higher_mean_and_the_test():
    rows = lambda scores: [{"family": "tsp", "task": index, "score": value} for index, value in enumerate(scores)]  # noqa: E731
    even = lineage.compared(rows([0.5] * 10), rows([0.6] * 5 + [0.4] * 5))
    assert even["wins"] == even["losses"] == 5 and not lineage.promoted(even, margin=3, level=0.05)
    clear = lineage.compared(rows([0.5] * 10), rows([0.6] * 8 + [0.5, 0.502]))
    assert clear["wins"] == 8 and clear["losses"] == 0 and lineage.promoted(clear, margin=3, level=0.05)
    assert clear["by_family"]["tsp"]["parent"] == 0.5
    with pytest.raises(ValueError):
        lineage.compared(rows([0.5] * 3), rows([0.5] * 2))


def test_the_container_has_no_network_and_cannot_write_outside_tmp():
    argv = lineage.docker_argv("n", "run", cpus=2)
    assert argv[argv.index("--network") + 1] == "none" and "--read-only" in argv and "ALL" in argv
    assert any(item.endswith("improver_runtime.py,readonly") for item in argv) and lineage.IMAGE in argv
    assert lineage.seeds(12, lineage.VISIBLE) == [120, 121, 122] and lineage.seeds(12, lineage.HIDDEN)[0] == 125
    assert not set(lineage.VISIBLE) & set(lineage.HIDDEN) and not set(lineage.CHECK) & set(lineage.HIDDEN)
