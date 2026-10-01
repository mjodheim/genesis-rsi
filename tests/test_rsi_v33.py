"""Probe cost, information, ledger and selection boundaries on consumed fixtures."""
import copy
import gzip
import json
import sys

import pytest

from experiment.rsi_v25.commitments import canonical, digest, digest_bytes
from experiment.rsi_v27 import engine as policy
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank as old_bank, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v32 import bank as v32
from experiment.rsi_v33 import bank, campaign, development, engine, freeze, storage


@pytest.fixture
def tasks():
    return old_bank.stream(old_bank.DEV_SEEDS[0])[:8]


def rows_for(tasks, arm="adaptive", margin=0, isolated=False):
    rows = []
    for position, task in enumerate(tasks):
        rows.append(engine.episode(task, position, engine.history_from(rows), arm, margin, isolated=isolated))
    return rows


def test_prospective_bank_disjointness_and_dimensions_without_behavior():
    assert not set(bank.FRESH_SEEDS) & set(old_bank.DEV_SEEDS + old_bank.FRESH_SEEDS + v32.FRESH_SEEDS)
    population = [task for seed in bank.FRESH_SEEDS for task in bank.stream(seed)]
    assert len(population) == len({digest(row) for row in population}) == 288
    assert {row["width"] for row in population} == set(range(3, 11))


def test_exact_controller_and_selector_removal():
    assert digest_bytes(engine.controller("adaptive").encode()) == programs.PARENT_SHA256
    assert engine.controller("selector_ablation") == family.parent()
    diagnostic = {"exploration": 0, "generation": 1, "scheduling": 0}
    assert meta.select(engine.controller("adaptive"), diagnostic) == "generation"
    assert meta.select(engine.controller("selector_ablation"), diagnostic) == "identity"


@pytest.mark.parametrize("arm", engine.ARMS)
def test_distinct_fully_charged_probes_and_equal_external_caps(tasks, arm, monkeypatch):
    calls = []
    from experiment.rsi_v31 import engine as evaluator
    original = evaluator.execute
    def execute(genome, inputs, *, isolated=True):
        calls.append(genome)
        return original(genome, inputs, isolated=isolated)
    monkeypatch.setattr(evaluator, "execute", execute)
    row = engine.episode(tasks[0], 0, {}, arm, 0, isolated=False)
    assert len(calls) == row["search"]["represented_requests"] + 3
    assert len({digest(genome) for genome in calls}) == len(calls)
    assert row["charged_evaluations"] == len(calls) + 1 <= 14
    assert row["routing"]["probe_evaluations"] == 2
    assert row["routing"]["controller_calls"] == 1
    assert row["search"]["caps"] == engine.CAPS.__dict__
    assert row["search"]["policy_sha256"] == programs.PARENT_SHA256


def test_known_memory_is_probed_before_route_and_all_probe_outcomes_are_retained(tasks):
    first = rows_for(tasks[:1])[0]
    host = engine.Host(tasks[0], engine.history_from([first]), "adaptive", 0, isolated=False)
    assert host.routing["archive_probe_sources"]
    assert host.routing["used_probe_root"]
    row = engine.episode(tasks[0], 1, engine.history_from([first]), "adaptive", 0, isolated=False)
    assert row["solved"] and row["best_quality_milli"] == 1000
    assert set(row["routing"]["probe_source_sha256"]) <= {p["source_sha256"] for p in row["programs"]}


def test_controller_receives_paid_diagnostics_not_inputs_targets_or_future_quality(tasks, monkeypatch):
    original = policy.call
    seen = []
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(x) for x in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(x) for x in value))
        return set()
    def call(path, payload):
        seen.append(payload)
        assert not keys(payload) & {"inputs", "target", "width", "genome", "family", "task_id", "successful_root_qualities"}
        return original(path, payload)
    # Search action descriptors legitimately contain the static family label.
    def selector(path, payload):
        assert set(payload["diagnostics"]) == {"exploration", "generation", "scheduling"}
        return call(path, payload)
    def search_call(path, payload):
        assert not keys(payload) & {"inputs", "target", "width", "genome", "task_id", "successful_root_qualities"}
        seen.append(payload)
        return original(path, payload)
    monkeypatch.setattr(policy, "call", search_call)
    monkeypatch.setattr(meta, "call", selector)
    row = engine.episode(tasks[0], 0, {}, "adaptive", 0)
    assert sum(payload["mode"] == "target" for payload in seen) == 1
    assert row["search"]["isolated_policy_processes"]


def test_resume_byte_identity_and_tampered_probes_rejected(tasks, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    rows, head = engine.run_stream(tasks, "adaptive", 0, a, "fixture", isolated=False)
    engine.run_stream(tasks, "adaptive", 0, b, "fixture", isolated=False, stop_after=3)
    resumed, resumed_head = engine.run_stream(tasks, "adaptive", 0, b, "fixture", isolated=False)
    assert rows == resumed and head == resumed_head and a.read_bytes() == b.read_bytes()
    assert engine.verify_stream(tasks, "adaptive", 0, rows, isolated=False)
    changed = copy.deepcopy(rows)
    changed[1]["routing"]["observed_probe_gain_milli"] += 1
    with pytest.raises(ValueError, match="probes"):
        engine.verify_stream(tasks, "adaptive", 0, changed, isolated=False)
    with pytest.raises(ValueError, match="binding"):
        engine.run_stream(tasks, "adaptive", 25, a, "fixture", isolated=False)


def test_isolated_execution_replay_and_receipt_tampering(tasks):
    rows = rows_for(tasks[:2], isolated=True)
    assert engine.verify_stream(tasks[:2], "adaptive", 0, rows)
    changed = copy.deepcopy(rows)
    changed[0]["programs"][1]["evaluation"]["quality_milli"] = 1
    with pytest.raises(ValueError, match="receipt"):
        engine.verify_stream(tasks[:2], "adaptive", 0, changed)


def test_unfinished_task_remains_consumed(tasks, tmp_path):
    path = tmp_path / "pending"
    archive = Archive(path, engine.binding(tasks, "adaptive", 0, "fixture"), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(tasks, "adaptive", 0, path, "fixture", isolated=False)
    assert path.read_bytes() == before


def fixture_evidence(directory):
    storage.publish_json(directory / "V33_RESERVATION.json", {
        "schema": "mira-genesis-v33-single-attempt-reservation-v1", "status": "RESERVED",
        "freeze_sha256": "fixture", "canonical_attempts": 1})
    return {"status": "COMPLETED", "freeze_sha256": "fixture", "canonical_attempts": 1, "negatives": [0, 1, 0]}, {
        "finite_archive_utility_positive": False, "l9_open_ended_passed": False, "l10_independent_passed": False}


@pytest.mark.parametrize("name", ["V33_RESERVATION.json", "V33_ATTEMPT_RAW.json.gz", "V33_FINAL_ADJUDICATION.json", "V33_COMPLETION.json"])
def test_each_evidence_file_is_bound_and_single_assignment(tmp_path, name):
    record, verdict = fixture_evidence(tmp_path)
    storage.complete(tmp_path, record, verdict)
    assert storage.read_complete(tmp_path) == (record, verdict)
    with pytest.raises(FileExistsError):
        storage.complete(tmp_path, record, verdict)
    path = tmp_path / name
    path.write_bytes(path.read_bytes()[:-1])
    with pytest.raises((ValueError, EOFError)):
        storage.read_complete(tmp_path)


def test_reservation_cannot_be_retried_without_completion(tmp_path, monkeypatch):
    record, _ = fixture_evidence(tmp_path)
    storage.publish_once(tmp_path / "V33_ATTEMPT_RAW.json.gz", gzip.compress(canonical(record) + b"\n", mtime=0))
    monkeypatch.setattr(campaign, "DIRECTORY", tmp_path)
    monkeypatch.setattr(campaign, "RESERVATION", tmp_path / "V33_RESERVATION.json")
    monkeypatch.setattr(campaign, "COMPLETION", tmp_path / "V33_COMPLETION.json")
    monkeypatch.setattr(freeze, "PATH", tmp_path / "freeze.json")
    freeze.PATH.write_text('{}')
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    with pytest.raises(ValueError, match="Missing completion"):
        campaign.check()


def test_complete_assay_omissions_and_l9_l10_boundaries(tasks, tmp_path, monkeypatch):
    monkeypatch.setattr(bank, "FRESH_SEEDS", (101,))
    monkeypatch.setattr(bank, "stream", lambda seed: tasks)
    frozen = {"freeze_sha256": "fixture", "margin_milli": 0, "tasks_per_arm": len(tasks), "python_version": sys.version.split()[0]}
    record = {"schema": "mira-genesis-v33-complete-attempt-v1", "status": "COMPLETED", "freeze_sha256": "fixture",
              "canonical_attempts": 1, "policy_sha256": programs.PARENT_SHA256, "python_version": frozen["python_version"],
              "track": "B", "scientific_external_model_calls": 0, "margin_milli": 0, "streams": {"101": {}}}
    for arm in engine.ARMS:
        path = tmp_path / arm
        engine.run_stream(tasks, arm, 0, path, "fixture", stop_after=6)
        checkpoint = Archive(path, engine.binding(tasks, arm, 0, "fixture")).read()[-1]["sha256"]
        rows, head = engine.run_stream(tasks, arm, 0, path, "fixture")
        record["streams"]["101"][arm] = {"episodes": rows, "journal": path.read_text(), "head_sha256": head,
            "checkpoint_position": 6, "checkpoint_head_sha256": checkpoint}
    result = campaign.adjudicate(record, frozen, replay=True)
    assert result["l9_open_ended_passed"] is result["l10_independent_passed"] is False
    omitted = copy.deepcopy(record)
    del omitted["streams"]["101"]["cold"]
    with pytest.raises(ValueError, match="control"):
        campaign.adjudicate(omitted, frozen, replay=False)
    changed = copy.deepcopy(record)
    changed["streams"]["101"]["adaptive"]["checkpoint_head_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checkpoint"):
        campaign.adjudicate(changed, frozen, replay=False)


def test_consumed_development_retains_all_predeclared_variants():
    result = development.verify(replay=False)
    assert result["tasks_per_variant"] == 456 and result["variants"] == 8
    assert development.selection() in engine.MARGINS


def test_missing_freeze_never_passes_l9_or_l10(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "absent")
    assert campaign.check() == {"status": "UNFROZEN", "l9_open_ended_passed": False, "l10_independent_passed": False}
    with pytest.raises(ValueError):
        freeze.verify({})
