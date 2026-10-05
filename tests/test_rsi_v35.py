"""Native witnesses, adversarial continuations, complete cost and durable recovery."""
import copy

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import bank, campaign, engine, native


def run_rows(tasks, arm="archive", previous=None):
    history, rows = previous or {}, []
    for i, task in enumerate(tasks):
        row = engine.episode(task, i, history, arm, isolated=False)
        engine.verify_episode(task, i, history, arm, row, isolated=False)
        rows.append(row)
        history = engine.history_from([row], history)
    return rows, history


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_actual_native_kernels_and_independent_distinguishing_witnesses(domain):
    task = bank.stream(17, domain, epochs=1, tasks_per_epoch=4)[0]
    for op in range(5):
        body = native.genome(domain, [op])
        measured = native.evaluate(task, body)
        local = native.evaluate(task, body, isolated=False)
        assert measured == {**local, "isolated": True}
        assert measured["matched_slots"] == int(op == task["target"][0])
        assert measured["outputs"][0]["value"] == task["inputs"][0]["answers"][op]


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_complete_paid_search_probes_confirmation_and_archive(domain):
    tasks = bank.stream(17, domain, epochs=2, tasks_per_epoch=4)
    rows, history = run_rows(tasks)
    for row in rows:
        calls = row["calls"]
        assert row["charged_evaluations"] == len(calls) <= 14
        assert row["solved"] == any(c["evaluation"]["quality_milli"] == 1000 for c in calls)
        assert calls[-1]["kind"] == "verify"
        assert {p["source_sha256"] for p in row["programs"]} == {c["evaluation"]["source_sha256"] for c in calls}
        assert len(row["programs"]) < len(calls)  # paid repeat, deduplicated source
    assert all(r["solved"] for r in rows)
    assert len(engine.frontiers(history, domain, "archive")) == 4
    assert len(engine.frontiers(history, domain, "greedy")) == 1
    assert engine.frontiers(history, domain, "cold") == []
    assert any(c["kind"] == "screen" and c["evaluation"]["matched_slots"] == 0 for r in rows for c in r["calls"])


def test_incremental_history_preserves_old_success_ancestry_and_counts():
    tasks = bank.stream(17, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    rows, history = run_rows(tasks)
    assert history == engine.history_from(rows)
    assert engine.summary(rows[4:], engine.history_from(rows[:4]))["solved_semantic_size"] == 8
    source = next(p["source_sha256"] for p in rows[0]["programs"] if p["evaluation"]["quality_milli"] == 1000)
    assert history[source]["successes"] >= 1
    assert history[source]["parent_source_sha256"] == engine.history_from(rows[:4])[source]["parent_source_sha256"]


def test_candidate_worker_and_policy_never_receive_private_answers(monkeypatch):
    task = bank.stream(17, native.DOMAINS[0], epochs=1, tasks_per_epoch=4)[0]
    original = native.subprocess.run
    payloads = []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(kwargs["input"])
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    row = engine.episode(task, 0, {}, "cold")
    engine.verify_episode(task, 0, {}, "cold", row)
    assert payloads
    assert all('"answers"' not in p and '"target"' not in p and task["task_id"] not in p for p in payloads)


@pytest.mark.parametrize("field", ("charged_evaluations", "solved", "new_first_solving_semantics"))
def test_output_novelty_cost_and_ancestry_tampering_rejected(field):
    task = bank.stream(17, native.DOMAINS[0], epochs=1, tasks_per_epoch=4)[0]
    row = engine.episode(task, 0, {}, "cold", isolated=False)
    bad = copy.deepcopy(row)
    bad[field] = None
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 0, {}, "cold", bad, isolated=False)
    bad = copy.deepcopy(row)
    bad["calls"][0]["evaluation"]["outputs"][0]["value"] = 123
    with pytest.raises(ValueError, match="receipt"):
        engine.verify_episode(task, 0, {}, "cold", bad, isolated=False)


def test_canonical_semantics_has_no_fixed_length_cap_and_real_extension_witness():
    value = native.genome(native.DOMAINS[0], [1] * 129 + [0, 0])
    assert len(value["ops"]) == 129
    shorter = native.genome(value["domain"], value["ops"][:-1])
    assert native.descriptor(value)["semantic_sha256"] != native.descriptor(shorter)["semantic_sha256"]
    context = native.contexts(17, value["domain"], 128, 0)
    assert native.execute(value, context, 129)[-1] != native.execute(shorter, context, 129)[-1]
    with pytest.raises(ValueError, match="Noncanonical"):
        native.validate({"domain": value["domain"], "ops": [1, 0]})
    with pytest.raises(ValueError):
        native.genome(value["domain"], [True])


@pytest.mark.parametrize("length", (2, 12, 65, 129))
def test_continuation_tries_each_new_operator_with_four_retained_branches(length):
    domain = native.DOMAINS[0]
    history = {}
    for branch in range(1, 5):
        body = native.genome(domain, [branch] + [2] * (length - 2))
        descriptor = native.descriptor(body)
        history[descriptor["source_sha256"]] = {"genome": body, **descriptor,
            "parent_source_sha256": None, "successes": 1, "last_success_position": branch}
    for op in range(1, 5):
        target = [3] + [2] * (length - 2) + [op]
        task = {"task_id": f"development-continuation-{length}-{op}", "domain": domain,
                "epoch": length - 1, "slots": length, "target": target,
                "inputs": native.contexts(17, domain, length - 1, op)}
        row = engine.episode(task, 10, history, "archive", isolated=False)
        assert row["solved"] and row["charged_evaluations"] <= 14
        assert row["selected_root_sha256"] == native.descriptor(native.genome(domain, target[:-1]))["source_sha256"]
        assert any(p["genome"]["ops"] == target for p in row["programs"])


def test_missing_frontier_and_incorrect_witness_are_exposed():
    domain = native.DOMAINS[0]
    task = bank.stream(17, domain, epochs=5, tasks_per_epoch=4)[-1]
    row = engine.episode(task, 0, {}, "archive", isolated=False)
    assert not row["solved"]  # induction requires the previous correct frontier
    bad = copy.deepcopy(task)
    bad["inputs"][0]["answers"][2] = bad["inputs"][0]["answers"][1]
    with pytest.raises(ValueError, match="aliased"):
        bank.validate_task(bad)


def test_segmented_exact_boundary_recovery_and_pending_quarantine(tmp_path, monkeypatch):
    domain = native.DOMAINS[0]
    tasks = bank.stream(17, domain, epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    value = {"mode": "pilot", "isolated": False}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    stopped = campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    assert stopped["completed_tasks"] == 2
    journal = tmp_path / "fixture/archive/epoch-001/journal.jsonl"
    prefix = journal.read_bytes()
    report = campaign.run_epoch(tmp_path, "fixture", "archive", 1)
    assert report["solved"] == 4 and journal.read_bytes().startswith(prefix)
    receipt = storage.read_json(journal.parent / "RECOVERY.json")
    assert receipt["completed_tasks_at_resume"] == 2 and not receipt["prefix_reexecuted"]
    previous, old_head, _ = campaign.prior(tmp_path / "fixture/archive", tasks, "archive", digest(value), 1, False)
    assert campaign.read_epoch(journal.parent, tasks[4:], "archive", digest(value), old_head, previous, False, replay=True)[3] == report
    pending = tmp_path / "pending.jsonl"
    archive = Archive(pending, campaign.binding(tasks[:4], "cold", "x", ZERO, {}, False), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    original = pending.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        campaign.journal_rows(archive, tasks[:4])
    assert pending.read_bytes() == original
