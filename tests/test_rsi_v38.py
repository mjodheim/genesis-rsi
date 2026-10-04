"""Prospective recursive tool acquisition, latest-tool ablation and fixed caps."""
import copy

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import native
from experiment.rsi_v38 import bank, campaign, engine


def recursive_library(domain, parent_width):
    history = {}
    for width in (parent_width // 2, parent_width):
        for operator in range(1, 5):
            value = native.genome(domain, [operator] * width)
            sha = native.descriptor(value)["source_sha256"]
            history[sha] = {"genome": value, **native.descriptor(value), "successes": 1,
                "first_success_position": width + operator, "last_success_position": width + operator,
                "parent_source_sha256": None}
    return history


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_latest_whole_program_tools_causally_reduce_successor_construction_cost(domain):
    history = recursive_library(domain, 4)
    task = {"task_id": "v38-public-tool-fixture", "domain": domain, "epoch": 3,
        "slots": 8, "target": [2] * 4 + [4] * 4, "inputs": native.contexts(503, domain, 3, 0)}
    rows = {arm: engine.episode(task, 100, history, arm, isolated=False) for arm in engine.ARMS}
    assert rows["archive"]["solved"] and rows["archive-ancestor"]["solved"]
    assert rows["archive"]["charged_evaluations"] < rows["archive-ancestor"]["charged_evaluations"]
    assert rows["archive"]["selected_root_sha256"] == rows["archive-ancestor"]["selected_root_sha256"]
    assert not rows["cold"]["solved"]
    for arm, row in rows.items():
        assert row["candidate_cap"] == 26 and len(row["calls"]) == row["charged_evaluations"] <= 26
        assert engine.verify_episode(task, 100, history, arm, row, isolated=False)
        assert {p["source_sha256"] for p in row["programs"]} == {c["evaluation"]["source_sha256"] for c in row["calls"]}
    for fragment in rows["archive"]["learned_fragments"]:
        assert history[fragment["donor_source_sha256"]]["genome"]["ops"] == fragment["ops"]
        assert len(fragment["ops"]) == 4
    assert all(len(f["ops"]) == 2 for f in rows["archive-ancestor"]["learned_fragments"])


@pytest.mark.parametrize("epoch", (4, 8, 10))
def test_two_program_construction_keeps_call_bound_as_macro_size_grows(epoch):
    domain, n = native.DOMAINS[1], 1 << epoch
    history = recursive_library(domain, n // 2)
    task = {"task_id": f"v38-public-large-tools-{epoch}", "domain": domain, "epoch": epoch,
        "slots": n, "target": [2] * (n // 2) + [4] * (n // 2),
        "inputs": native.contexts(503, domain, epoch, 0)}
    row = engine.episode(task, 10000, history, "archive", isolated=False)
    assert row["solved"] and row["charged_evaluations"] <= 16
    assert engine.verify_episode(task, 10000, history, "archive", row, isolated=False)


def test_newly_acquired_programs_are_successful_donors_for_later_generations():
    tasks = bank.stream(503, native.DOMAINS[0], epochs=5, tasks_per_epoch=8)
    history = {}
    for position, task in enumerate(tasks):
        row = engine.episode(task, position, history, "archive", isolated=False)
        assert row["solved"] and row["charged_evaluations"] <= 16
        if task["epoch"]:
            assert len(row["learned_fragments"]) == 4
            for fragment in row["learned_fragments"]:
                donor = history[fragment["donor_source_sha256"]]
                assert donor["successes"] and len(donor["genome"]["ops"]) == task["slots"] // 2
                assert fragment["acquired_position"] < position
        history = engine.history_from([row], history)
    assert len({entry["semantic_sha256"] for entry in history.values() if entry["successes"]}) == 20


def test_recursive_stream_is_fixed_distinct_and_can_rewrite_old_positions():
    tasks = bank.stream(503, native.DOMAINS[0], epochs=6, tasks_per_epoch=8)
    assert bank.validate_stream(tasks) == digest(tasks)
    assert [tasks[i * 8]["slots"] for i in range(6)] == [1, 2, 4, 8, 16, 32]
    for epoch in range(6):
        targets = {tuple(t["target"]) for t in tasks[epoch * 8:(epoch + 1) * 8]}
        assert len(targets) == 4
        if epoch:
            previous = {tuple(t["target"]) for t in tasks[(epoch - 1) * 8:epoch * 8]}
            half = 1 << (epoch - 1)
            assert all(t[:half] in previous and t[half:] in previous for t in targets)
    assert not set(bank.DEV_SEEDS) & set(bank.FRESH_SEEDS)


@pytest.mark.parametrize("field", ("macro_width", "learned_fragments", "construction_decisions", "charged_evaluations"))
def test_new_tool_identity_decision_and_charge_tampering_rejected(field):
    domain = native.DOMAINS[1]
    task = bank.stream(503, domain, epochs=4, tasks_per_epoch=4)[-1]
    history = recursive_library(domain, 4)
    row = engine.episode(task, 100, history, "archive", isolated=False)
    bad = copy.deepcopy(row)
    bad[field] = None
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 100, history, "archive", bad, isolated=False)


def test_isolated_native_worker_never_receives_target_or_references(monkeypatch):
    task = bank.stream(503, native.DOMAINS[2], epochs=1, tasks_per_epoch=4)[0]
    original, payloads = native.subprocess.run, []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(kwargs["input"])
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    row = engine.episode(task, 0, {}, "cold")
    assert row["solved"]
    assert payloads and all('"answers"' not in p and '"target"' not in p and task["task_id"] not in p for p in payloads)


def test_fixed_task_reservation_and_completed_boundary_recovery(tmp_path, monkeypatch):
    tasks = bank.stream(503, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    storage.publish_json(tmp_path / "MANIFEST.json", {"mode": "pilot", "isolated": False})
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    journal = tmp_path / "fixture/archive/epoch-001/journal.jsonl"
    prefix = journal.read_bytes()
    campaign.run_epoch(tmp_path, "fixture", "archive", 1)
    assert journal.read_bytes().startswith(prefix)
    assert not storage.read_json(journal.parent / "RECOVERY.json")["prefix_reexecuted"]
    pending = Archive(tmp_path / "pending.jsonl", campaign.binding(tasks[:4], "cold", "x", ZERO, {}, False), create=True)
    pending.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 26})
    with pytest.raises(ValueError, match="Unfinished"):
        campaign.journal_rows(pending, tasks[:4])


def test_negative_progression_blocks_fresh_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check", lambda root: {"development_progression_passed": False})
    monkeypatch.setattr(campaign, "FREEZE", tmp_path / "freeze.json")
    with pytest.raises(ValueError, match="no fresh attempt"):
        campaign.freeze()


def test_fixed_global_reservation_is_checked_before_reading_epochs(tmp_path, monkeypatch):
    value = {"mode": "pilot", "tasks_per_arm": 384, "maximum_evaluations_per_arm": 9984}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    expected = campaign.reservation(value)
    assert expected["maximum_charged_evaluations"] == 39936
    storage.publish_json(tmp_path / "RESERVATION.json", {**expected, "maximum_charged_evaluations": 1})
    monkeypatch.setattr(campaign, "verify_manifest", lambda value: True)
    with pytest.raises(ValueError, match="global reservation"):
        campaign.collect(tmp_path, replay=True)


@pytest.mark.parametrize("field", ("head_sha256", "history_sha256"))
def test_corrupted_interruption_receipt_is_rejected(tmp_path, monkeypatch, field):
    tasks = bank.stream(503, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    storage.publish_json(tmp_path / "MANIFEST.json", {"mode": "pilot", "isolated": False})
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    boundary = tmp_path / "fixture/archive/epoch-001/STOP_BOUNDARY.json"
    value = storage.read_json(boundary)
    value[field] = "0" * 64
    boundary.unlink()  # Disposable hostile test fixture only.
    storage.publish_json(boundary, value)
    with pytest.raises(ValueError, match="interrupted prefix"):
        campaign.run_epoch(tmp_path, "fixture", "archive", 1)
