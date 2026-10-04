"""Adversarial validation of the original single-attempt reservation."""
import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v32 import storage
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v35 import bank, campaign, engine, native
from scripts import audit_v35_native_campaign as audit


@pytest.mark.parametrize("field,value", (
    ("maximum_charged_evaluations", 1), ("status", "FREE_RETRY"), ("manifest_sha256", "0" * 64)))
def test_modified_whole_campaign_reservation_is_rejected(tmp_path, monkeypatch, field, value):
    manifest = {"mode": "pilot", "tasks_per_arm": 256}
    monkeypatch.setattr(audit.campaign, "verify_manifest", lambda value: True)
    storage.publish_json(tmp_path / "MANIFEST.json", manifest)
    reservation = {"manifest_sha256": digest(manifest), "status": "RESERVED_SINGLE_ATTEMPT",
                   "maximum_charged_evaluations": 256 * 3 * 14}
    reservation[field] = value
    storage.publish_json(tmp_path / "RESERVATION.json", reservation)
    with pytest.raises(ValueError, match="reservation"):
        audit.audit_header(tmp_path)


def test_original_reservation_is_accepted_without_rewriting_it(tmp_path, monkeypatch):
    manifest = {"mode": "pilot", "tasks_per_arm": 256}
    monkeypatch.setattr(audit.campaign, "verify_manifest", lambda value: True)
    storage.publish_json(tmp_path / "MANIFEST.json", manifest)
    storage.publish_json(tmp_path / "RESERVATION.json", {
        "manifest_sha256": digest(manifest), "status": "RESERVED_SINGLE_ATTEMPT",
        "maximum_charged_evaluations": 256 * 3 * 14})
    original = (tmp_path / "RESERVATION.json").read_bytes()
    assert audit.audit_header(tmp_path) == manifest
    assert (tmp_path / "RESERVATION.json").read_bytes() == original


@pytest.mark.parametrize("altered", (False, True))
def test_interruption_head_is_checked_against_actual_journal(tmp_path, monkeypatch, altered):
    tasks = bank.stream(17, native.DOMAINS[0], epochs=7, tasks_per_epoch=32)
    subset = tasks[-32:]
    value = {"mode": "fresh"}
    monkeypatch.setattr(campaign, "population", lambda mode: {"81173-relational-sql": tasks})
    monkeypatch.setattr(campaign, "prior", lambda *args, **kwargs: ({}, ZERO, []))
    directory = tmp_path / "81173-relational-sql/archive/epoch-006"
    archive = Archive(directory / "journal.jsonl", campaign.binding(subset, "archive", digest(value), ZERO, {}, True), create=True)
    rows = []
    for i, task in enumerate(subset):
        row = {"task_sha256": digest(task), "charged_evaluations": 1, "programs": []}
        archive.append("start", {"position": i, "task_sha256": digest(task), "reserved_evaluations": 14})
        archive.append("episode", row)
        rows.append(row)
    stop = {"completed_tasks": 16, "head_sha256": "0" * 64 if altered else archive.read()[32]["sha256"],
            "prefix_sha256": digest(rows[:16]), "history_sha256": digest(engine.history_from(rows[:16]))}
    storage.publish_json(directory / "STOP_BOUNDARY.json", stop)
    storage.publish_json(directory / "RECOVERY.json", {"boundary_sha256": digest(stop), "prefix_reexecuted": False,
        "restored_history_sha256": stop["history_sha256"], "completed_tasks_at_resume": 16})
    if altered:
        with pytest.raises(ValueError, match="actual ledger head"):
            audit.audit_recovery(tmp_path, value)
    else:
        assert audit.audit_recovery(tmp_path, value) is None
