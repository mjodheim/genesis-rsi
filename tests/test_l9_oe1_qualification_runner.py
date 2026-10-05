import json

from experiment.l9_oe1 import qualification_epoch
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank


def _tasks_by_epoch():
    tasks = bank.stream(
        bank.DEV_SEEDS[0],
        native.DOMAINS[0],
        epochs=4,
        tasks_per_epoch=4,
    )
    return {
        epoch: [task for task in tasks if task["epoch"] == epoch]
        for epoch in range(4)
    }


def test_qualification_coded_runner_recovers_on_consumed_v36():
    epochs = _tasks_by_epoch()
    state = None
    previous_after = None

    for epoch in range(4):
        summary, state = qualification_epoch.run_epoch(
            epochs[epoch],
            "coded-archive",
            state,
            isolated=False,
        )
        assert summary["solved"] == len(epochs[epoch])
        assert summary["max_task_evaluations"] <= 14
        if previous_after is not None:
            assert summary["state_before_sha256"] == previous_after
        previous_after = summary["state_after_sha256"]
        state = json.loads(
            json.dumps(state, sort_keys=True, separators=(",", ":"))
        )

    assert len(state["motifs"]) == 4
    assert len(state["code_hashes"]) == 1


def test_qualification_control_runner_keeps_cap_on_consumed_v36():
    tasks = _tasks_by_epoch()[0]
    summary, state = qualification_epoch.run_epoch(
        tasks,
        "archive-g7",
        None,
        isolated=False,
    )
    assert summary["tasks"] == len(tasks)
    assert summary["max_task_evaluations"] <= 14
    assert state["kind"] == "control"
