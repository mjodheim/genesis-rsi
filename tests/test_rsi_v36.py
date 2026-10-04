"""Prospective V36 causal controls, privacy, donor identities and durable accounting."""
import copy

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank, campaign, engine


def history_fixture(domain):
    history = {}
    for position, ops in enumerate(([1, 1, 1], [2, 2, 2], [3, 3, 3], [4, 4, 4])):
        value = native.genome(domain, list(ops))
        sha = native.descriptor(value)["source_sha256"]
        history[sha] = {"genome": value, **native.descriptor(value), "successes": 1,
                        "first_success_position": position, "last_success_position": position,
                        "parent_source_sha256": None}
    return history


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_paid_acquired_splice_solves_beyond_point_depth_and_replays(domain):
    history = history_fixture(domain)
    task = {"task_id": "v36-public-causal-fixture", "domain": domain, "epoch": 3, "slots": 6,
            "target": [2, 2, 2, 4, 4, 4], "inputs": native.contexts(71, domain, 3, 0)}
    rows = {arm: engine.episode(task, 10, history, arm, isolated=False) for arm in engine.ARMS}
    assert rows["archive"]["solved"]
    assert not rows["archive-point"]["solved"]
    for arm, row in rows.items():
        assert row["charged_evaluations"] == len(row["calls"]) <= 14
        assert {p["source_sha256"] for p in row["programs"]} == {c["evaluation"]["source_sha256"] for c in row["calls"]}
        assert engine.verify_episode(task, 10, history, arm, row, isolated=False)
        for call in row["calls"]:
            construction = call["construction"]
            if construction["kind"] == "learned-splice":
                donor = history[construction["donor_source_sha256"]]
                start = construction["donor_block_start"]
                assert donor["genome"]["ops"][start:start + 3] == construction["ops"]
                assert donor["successes"] and construction["acquired_position"] < 10
    assert rows["archive"]["selected_root_sha256"] == rows["archive-point"]["selected_root_sha256"]


def test_fragments_require_prior_success_and_removal_is_causal():
    domain = native.DOMAINS[0]
    history = history_fixture(domain)
    assert len(engine.fragments(history, domain, "archive", 6)) == 4
    assert len(engine.fragments(history, domain, "greedy", 6)) == 1
    assert not engine.fragments(history, domain, "archive-point", 6)
    assert not engine.fragments(history, domain, "cold", 6)
    for row in history.values():
        row["successes"] = 0
    assert not engine.fragments(history, domain, "archive", 6)


def test_stream_contains_unfiltered_nonprefix_rewrites_and_distinct_growth():
    tasks = bank.stream(71, native.DOMAINS[0], epochs=6, tasks_per_epoch=8)
    assert bank.validate_stream(tasks) == digest(tasks)
    assert [tasks[epoch * 8]["slots"] for epoch in range(6)] == [1, 2, 3, 6, 9, 12]
    for epoch in range(6):
        targets = {tuple(t["target"]) for t in tasks[epoch * 8:(epoch + 1) * 8]}
        assert len(targets) == 4
    previous = {tuple(t["target"]) for t in tasks[24:32]}
    assert any(tuple(t["target"][:6]) not in previous for t in tasks[32:40])
    assert not set(bank.DEV_SEEDS) & set(bank.FRESH_SEEDS)


@pytest.mark.parametrize("field", ("learned_fragments", "charged_evaluations", "new_first_solving_semantics"))
def test_donor_novelty_and_accounting_substitution_rejected(field):
    domain = native.DOMAINS[0]
    task = bank.stream(71, domain, epochs=4, tasks_per_epoch=4)[-1]
    history = history_fixture(domain)
    row = engine.episode(task, 20, history, "archive", isolated=False)
    bad = copy.deepcopy(row)
    bad[field] = None
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 20, history, "archive", bad, isolated=False)
    splice = next((c for c in row["calls"] if c["construction"]["kind"] == "learned-splice"), None)
    assert splice is not None
    bad = copy.deepcopy(row)
    next(c for c in bad["calls"] if c["construction"]["kind"] == "learned-splice")["construction"]["donor_source_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 20, history, "archive", bad, isolated=False)


def test_candidate_and_policy_workers_receive_no_target_answers_or_donor_ledger(monkeypatch):
    domain = native.DOMAINS[1]
    task = {"task_id": "v36-private-canary", "domain": domain, "epoch": 3, "slots": 6,
            "target": [2, 2, 2, 4, 4, 4], "inputs": native.contexts(71, domain, 3, 0)}
    original, payloads = native.subprocess.run, []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(kwargs["input"])
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    row = engine.episode(task, 10, history_fixture(domain), "archive")
    assert row["solved"]
    assert payloads and all('"answers"' not in p and '"target"' not in p
                            and task["task_id"] not in p and '"donor_source_sha256"' not in p for p in payloads)


def test_exact_mid_epoch_recovery_and_pending_quarantine(tmp_path, monkeypatch):
    tasks = bank.stream(71, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    value = {"mode": "pilot", "isolated": False}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    stopped = campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    assert stopped["completed_tasks"] == 2
    journal = tmp_path / "fixture/archive/epoch-001/journal.jsonl"
    prefix = journal.read_bytes()
    campaign.run_epoch(tmp_path, "fixture", "archive", 1)
    assert journal.read_bytes().startswith(prefix)
    recovery = storage.read_json(journal.parent / "RECOVERY.json")
    assert recovery["completed_tasks_at_resume"] == 2 and not recovery["prefix_reexecuted"]
    pending = Archive(tmp_path / "pending.jsonl", campaign.binding(tasks[:4], "cold", "x", ZERO, {}, False), create=True)
    pending.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    with pytest.raises(ValueError, match="Unfinished"):
        campaign.journal_rows(pending, tasks[:4])


def test_global_reservation_and_guard_sources_are_bound():
    value = {"tasks_per_arm": 384, "arbitrary": "binding"}
    assert campaign.reservation(value)["maximum_charged_evaluations"] == 21504
    inputs = campaign.inputs()
    assert all("experiment/rsi_v23/" + name in inputs for name in
               ("policy_guard.py", "policy_worker.py", "sandbox_policy.py"))


def test_negative_pilot_cannot_spend_fresh_population(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check", lambda root: {"development_progression_passed": False})
    monkeypatch.setattr(campaign, "FREEZE", tmp_path / "freeze.json")
    with pytest.raises(ValueError, match="no fresh attempt"):
        campaign.freeze()
    assert not campaign.FREEZE.exists()


def test_global_reservation_substitution_rejected_before_epoch_reads(tmp_path, monkeypatch):
    value = {"mode": "pilot", "tasks_per_arm": 384}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    bad = {**campaign.reservation(value), "maximum_charged_evaluations": 1}
    storage.publish_json(tmp_path / "RESERVATION.json", bad)
    monkeypatch.setattr(campaign, "verify_manifest", lambda value: True)
    with pytest.raises(ValueError, match="global reservation"):
        campaign.collect(tmp_path, replay=True)


@pytest.mark.parametrize("field", ("head_sha256", "history_sha256"))
def test_changed_interrupted_head_or_state_is_rejected(tmp_path, monkeypatch, field):
    tasks = bank.stream(71, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    storage.publish_json(tmp_path / "MANIFEST.json", {"mode": "pilot", "isolated": False})
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    boundary = tmp_path / "fixture/archive/epoch-001/STOP_BOUNDARY.json"
    changed = storage.read_json(boundary)
    changed[field] = "0" * 64
    boundary.unlink()  # Deliberate corruption in a disposable test fixture only.
    storage.publish_json(boundary, changed)
    with pytest.raises(ValueError, match="interrupted prefix"):
        campaign.run_epoch(tmp_path, "fixture", "archive", 1)
