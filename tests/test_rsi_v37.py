"""Prospective paid-construction causal efficiency, scaling and evidence tests."""
import copy

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v35 import native
from experiment.rsi_v37 import bank, campaign, engine


def library(domain):
    history = {}
    for index in range(1, 5):
        value = native.genome(domain, [index] * 3)
        sha = native.descriptor(value)["source_sha256"]
        history[sha] = {"genome": value, **native.descriptor(value), "successes": 1,
            "first_success_position": index, "last_success_position": index, "parent_source_sha256": None}
    return history


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_acquired_blocks_reduce_paid_calls_against_identical_point_scheduler(domain):
    history = library(domain)
    task = {"task_id": "v37-public-causal-fixture", "domain": domain, "epoch": 3, "slots": 9,
        "target": [2, 2, 2, 4, 4, 4, 1, 1, 1], "inputs": native.contexts(211, domain, 3, 0)}
    rows = {arm: engine.episode(task, 10, history, arm, isolated=False) for arm in engine.ARMS}
    assert all(row["solved"] for row in (rows["archive"], rows["archive-point"], rows["cold"]))
    assert rows["archive"]["charged_evaluations"] < rows["archive-point"]["charged_evaluations"]
    assert rows["archive"]["selected_root_sha256"] == rows["archive-point"]["selected_root_sha256"]
    for arm, row in rows.items():
        assert row["candidate_cap"] == engine.cap(task) == 51
        assert row["charged_evaluations"] == len(row["calls"]) <= engine.cap(task)
        assert row["policy_calls"] == 0 and row["host_authored_coordinate_scheduler"]
        assert engine.verify_episode(task, 10, history, arm, row, isolated=False)
        assert {p["source_sha256"] for p in row["programs"]} == {c["evaluation"]["source_sha256"] for c in row["calls"]}
        if row["solved"]:
            assert row["calls"][-1]["kind"] == "verify"


@pytest.mark.parametrize("blocks", (5, 17, 33))
def test_paid_arbitrary_recombination_constructs_beyond_fixed_depth(blocks):
    domain = native.DOMAINS[1]
    target = sum(([1 + index % 4] * 3 for index in range(blocks)), [])
    task = {"task_id": f"v37-public-large-fixture-{blocks}", "domain": domain, "epoch": 5,
        "slots": len(target), "target": target, "inputs": native.contexts(211, domain, 5, blocks)}
    row = engine.episode(task, 20, library(domain), "archive", isolated=False)
    assert row["solved"] and row["charged_evaluations"] <= 5 * blocks + 6
    assert engine.verify_episode(task, 20, library(domain), "archive", row, isolated=False)


def test_complete_initial_acquisition_and_rediscovery_with_no_fragment_interference():
    tasks = bank.stream(211, native.DOMAINS[0], epochs=4, tasks_per_epoch=8)
    history, rows = {}, []
    for position, task in enumerate(tasks):
        row = engine.episode(task, position, history, "archive", isolated=False)
        assert row["solved"]
        assert not any(c["kind"] == "learned-splice" for c in row["calls"]) if task["slots"] <= 3 else True
        rows.append(row)
        history = engine.history_from([row], history)
    assert len(engine.fragments(history, native.DOMAINS[0], "archive", 6)) == 4
    assert any(row["rediscovered"] for row in rows)


@pytest.mark.parametrize("field", ("construction_decisions", "candidate_cap", "charged_evaluations", "learned_fragments"))
def test_cost_decision_and_donor_tampering_is_rejected(field):
    task = bank.stream(211, native.DOMAINS[1], epochs=4, tasks_per_epoch=4)[-1]
    history = library(task["domain"])
    row = engine.episode(task, 20, history, "archive", isolated=False)
    bad = copy.deepcopy(row)
    bad[field] = None
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 20, history, "archive", bad, isolated=False)


def test_native_isolation_and_reference_privacy(monkeypatch):
    task = bank.stream(211, native.DOMAINS[2], epochs=1, tasks_per_epoch=4)[0]
    original, payloads = native.subprocess.run, []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(kwargs["input"])
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    row = engine.episode(task, 0, {}, "cold")
    assert row["solved"] and all(c["evaluation"]["isolated"] for c in row["calls"])
    assert payloads and all('"answers"' not in p and '"target"' not in p and task["task_id"] not in p for p in payloads)


def test_variable_reservation_recovery_and_no_free_pending_retry(tmp_path, monkeypatch):
    tasks = bank.stream(211, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    value = {"mode": "pilot", "isolated": False}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    journal = tmp_path / "fixture/archive/epoch-001/journal.jsonl"
    prefix = journal.read_bytes()
    campaign.run_epoch(tmp_path, "fixture", "archive", 1)
    assert journal.read_bytes().startswith(prefix)
    assert not storage.read_json(journal.parent / "RECOVERY.json")["prefix_reexecuted"]
    pending = Archive(tmp_path / "pending.jsonl", campaign.binding(tasks[:4], "cold", "x", ZERO, {}, False), create=True)
    pending.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": engine.cap(tasks[0])})
    with pytest.raises(ValueError, match="Unfinished"):
        campaign.journal_rows(pending, tasks[:4])


def test_budget_stops_before_overrun_and_leaves_confirmation_space():
    task = bank.stream(211, native.DOMAINS[0], epochs=1, tasks_per_epoch=4)[0]
    host = engine.Constructor(task, {}, "cold", isolated=False)
    for _ in range(engine.cap(task) - 2):
        host.evaluate(native.genome(task["domain"], []), {"kind": "point"})
    with pytest.raises(engine.BudgetBoundary):
        host.evaluate(native.genome(task["domain"], []), {"kind": "point"})
    assert len(host.calls) == engine.cap(task) - 1
    host.evaluate(native.genome(task["domain"], []), {"kind": "verify"})
    assert len(host.calls) == engine.cap(task)


def test_negative_pilot_prevents_freeze(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check", lambda root: {"development_progression_passed": False})
    monkeypatch.setattr(campaign, "FREEZE", tmp_path / "freeze.json")
    with pytest.raises(ValueError, match="no fresh attempt"):
        campaign.freeze()
    assert not campaign.FREEZE.exists()


def test_dimensioned_global_reservation_substitution_rejected(tmp_path, monkeypatch):
    value = {"mode": "pilot", "tasks_per_arm": 384, "maximum_evaluations_per_arm": 12864}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    correct = campaign.reservation(value)
    assert correct["maximum_charged_evaluations"] == 51456
    storage.publish_json(tmp_path / "RESERVATION.json", {**correct, "maximum_charged_evaluations": 1})
    monkeypatch.setattr(campaign, "verify_manifest", lambda value: True)
    with pytest.raises(ValueError, match="global reservation"):
        campaign.collect(tmp_path, replay=True)


@pytest.mark.parametrize("field", ("head_sha256", "history_sha256"))
def test_interrupted_head_or_state_substitution_rejected(tmp_path, monkeypatch, field):
    tasks = bank.stream(211, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
    monkeypatch.setattr(campaign, "population", lambda mode: {"fixture": tasks})
    storage.publish_json(tmp_path / "MANIFEST.json", {"mode": "pilot", "isolated": False})
    campaign.run_epoch(tmp_path, "fixture", "archive", 0)
    campaign.run_epoch(tmp_path, "fixture", "archive", 1, stop_after=2)
    boundary = tmp_path / "fixture/archive/epoch-001/STOP_BOUNDARY.json"
    bad = storage.read_json(boundary)
    bad[field] = "0" * 64
    boundary.unlink()  # Disposable corruption fixture only.
    storage.publish_json(boundary, bad)
    with pytest.raises(ValueError, match="interrupted prefix"):
        campaign.run_epoch(tmp_path, "fixture", "archive", 1)
