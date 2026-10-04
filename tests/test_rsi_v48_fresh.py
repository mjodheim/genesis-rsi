"""Prospective freeze must preserve finite scope and complete source dependencies."""
import json
import sys

import pytest

from experiment.rsi_v35 import bank as historical
from experiment.rsi_v42 import bank as previous
from experiment.rsi_v33 import storage
from experiment.rsi_v48 import bank, campaign, freeze, proposer


def test_new_population_is_disjoint_without_executing_it():
    assert not set(bank.FRESH_SEEDS) & set(bank.DEV_SEEDS)
    assert not set(bank.FRESH_SEEDS) & set(historical.FRESH_SEEDS)
    assert not set(bank.FRESH_SEEDS) & set(previous.FRESH_SEEDS)
    assert sum(len(bank.stream(seed, epoch)) for seed in bank.FRESH_SEEDS for epoch in range(bank.INITIAL_EPOCHS)) == 468


def test_freeze_preserves_scope_and_both_work_caps():
    constants = freeze.constants()
    assert constants["l9_open_ended_passed"] is False
    assert constants["l10_independent_passed"] is False
    assert constants["new_recursive_transition_established"] is False
    assert constants["finite_prefix_cannot_establish_open_endedness"] is True
    assert constants["selected_variant"] == "inverse4_successors"
    assert constants["maximum_inference_output_calls"] == proposer.MAX_OUTPUT_CALLS
    assert constants["maximum_inference_primitive_visits"] == proposer.MAX_PRIMITIVE_VISITS


def test_missing_freeze_cannot_authorize_fresh_work(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "missing")
    assert campaign.check()["l9_open_ended_passed"] is False
    with pytest.raises(ValueError):
        campaign.check(require_prefix=True)


def test_started_attempt_never_retries(tmp_path, monkeypatch):
    frozen = tmp_path / "freeze.json"
    storage.publish_json(frozen, {"python_version": sys.version.split()[0]})
    monkeypatch.setattr(freeze, "PATH", frozen)
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    monkeypatch.setattr(campaign, "directory", lambda epoch: tmp_path)
    (tmp_path / "STARTED.json").write_text("{}")
    with pytest.raises(ValueError, match="never retry"):
        campaign.run_epoch(0)


def test_uncommitted_reservation_never_starts_behavior(tmp_path, monkeypatch):
    from experiment.rsi_v25.commitments import digest
    frozen = {"python_version": sys.version.split()[0], "freeze_sha256": "f" * 64}
    path = tmp_path / "freeze.json"
    storage.publish_json(path, frozen)
    monkeypatch.setattr(freeze, "PATH", path)
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    monkeypatch.setattr(campaign, "directory", lambda epoch: tmp_path)
    monkeypatch.setattr(campaign, "past", lambda *args, **kwargs: ({}, None, []))
    identity = {"schema": "mira-genesis-v48-epoch-reservation-v1", "status": "RESERVED", "epoch": 0,
                "freeze_sha256": frozen["freeze_sha256"], "previous_receipt_sha256": None,
                "tasks_sha256": digest({str(seed): bank.stream(seed, 0) for seed in bank.FRESH_SEEDS})}
    storage.publish_json(tmp_path / "RESERVATION.json", identity)
    monkeypatch.setattr(freeze, "git", lambda *args: b"not the committed reservation")
    with pytest.raises(ValueError, match="publicly committed"):
        campaign.run_epoch(0)
    assert not (tmp_path / "STARTED.json").exists()
