"""Meaningful boundary, causal ablation, durability and recovery tests on consumed fixtures."""
import copy
import gzip
import json
from pathlib import Path

import pytest

from experiment.rsi_v25.commitments import canonical, digest, digest_bytes
from experiment.rsi_v27 import engine as policy
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank as previous_bank, engine as previous_engine, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v32 import bank, campaign, development, engine, freeze, storage


@pytest.fixture
def tasks():
    # No fresh V32 behavior is allowed in tests, before or after the freeze.
    return previous_bank.stream(previous_bank.DEV_SEEDS[0])[:8]


def rows_for(tasks, arm="adaptive", tolerance=25, isolated=False):
    rows = []
    for position, task in enumerate(tasks):
        rows.append(engine.episode(task, position, engine.history_from(rows), arm, tolerance, isolated=isolated))
    return rows


def test_fresh_bank_dimensions_and_disjointness_without_behavior():
    assert not set(bank.FRESH_SEEDS) & set(previous_bank.DEV_SEEDS + previous_bank.FRESH_SEEDS)
    all_tasks = [task for seed in bank.FRESH_SEEDS for task in bank.stream(seed)]
    assert len(all_tasks) == 216 and len({digest(t) for t in all_tasks}) == 216
    assert {t["width"] for t in all_tasks} == set(range(3, 9))
    assert {t["family"] for t in all_tasks} == {"xor", "rotation", "affine"}


def test_unmodified_acquired_controller_and_precise_selector_ablation():
    assert digest_bytes(engine.controller("adaptive").encode()) == programs.PARENT_SHA256
    assert engine.controller("selector_ablation") == family.parent()
    diagnostics = {"exploration": 0, "generation": 1, "scheduling": 0}
    assert meta.select(engine.controller("adaptive"), diagnostics) == "generation"
    assert meta.select(engine.controller("selector_ablation"), diagnostics) == "identity"


def test_selector_and_search_receive_no_hidden_task_or_future_quality(tasks, monkeypatch):
    original = policy.call
    seen = []
    def observe(path, payload):
        seen.append(payload)
        text = json.dumps(payload)
        assert tasks[0]["task_id"] not in text
        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()
        assert not keys(payload) & {"inputs", "target", "task_family", "width", "genome", "successful_root_qualities"}
        if payload["mode"] == "target":
            assert set(payload["diagnostics"]) == {"exploration", "generation", "scheduling"}
        return original(path, payload)
    monkeypatch.setattr(policy, "call", observe)
    monkeypatch.setattr(meta, "call", observe)
    row = engine.episode(tasks[0], 0, {}, "adaptive", 25)
    assert sum(payload["mode"] == "target" for payload in seen) == 1
    assert row["charged_evaluations"] == row["search"]["represented_requests"] + 2


def test_historical_similarity_can_change_route_without_current_target(tasks):
    rows = rows_for(tasks[:1])
    history = engine.history_from(rows)
    target = tasks[1]
    host = engine.Host(target, history, "adaptive", 25, isolated=False)
    for entry in history.values():
        if entry["successes"]:
            assert entry["successful_root_qualities"] == [rows[0]["root_evaluation"]["quality_milli"]]
    assert host.routing["target"] == "exploration"
    incompatible = copy.deepcopy(history)
    for entry in incompatible.values():
        if entry["successes"]:
            entry["successful_root_qualities"] = [0]
    fallback = engine.Host(target, incompatible, "adaptive", 25, isolated=False)
    ablated = engine.Host(target, incompatible, "selector_ablation", 25, isolated=False)
    assert fallback.initial == ablated.initial == host.initial
    assert fallback.routing["target"] == "generation" and not fallback.retrieved
    assert ablated.routing["target"] == "identity" and ablated.retrieved


@pytest.mark.parametrize("arm", engine.ARMS)
def test_matched_caps_charged_controller_and_root(tasks, arm):
    row = rows_for(tasks[:2], arm)[1]
    assert row["charged_evaluations"] <= 14
    assert row["charged_evaluations"] == row["search"]["represented_requests"] + 2
    assert row["routing"]["controller_calls"] == 1
    assert row["search"]["caps"] == previous_engine.CAPS.__dict__
    assert row["search"]["policy_sha256"] == programs.PARENT_SHA256


def test_resume_is_byte_exact_and_tampered_context_or_routing_is_refused(tasks, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    rows, head = engine.run_stream(tasks, "adaptive", 25, a, "fixture", isolated=False)
    engine.run_stream(tasks, "adaptive", 25, b, "fixture", isolated=False, stop_after=3)
    resumed, resumed_head = engine.run_stream(tasks, "adaptive", 25, b, "fixture", isolated=False)
    assert rows == resumed and head == resumed_head and a.read_bytes() == b.read_bytes()
    assert engine.verify_stream(tasks, "adaptive", 25, rows, isolated=False)
    altered = copy.deepcopy(rows)
    altered[1]["routing"]["diagnostics"]["generation"] += 1
    with pytest.raises(ValueError, match="selector"):
        engine.verify_stream(tasks, "adaptive", 25, altered, isolated=False)
    with pytest.raises(ValueError, match="binding"):
        engine.run_stream(tasks, "adaptive", 50, a, "fixture", isolated=False)


def test_isolated_policy_and_evaluator_receipt_replay(tasks):
    rows = rows_for(tasks[:2], isolated=True)
    assert engine.verify_stream(tasks[:2], "adaptive", 25, rows)
    bad = copy.deepcopy(rows)
    bad[0]["programs"][0]["evaluation"]["quality_milli"] = 0
    with pytest.raises(ValueError, match="receipt"):
        engine.verify_stream(tasks[:2], "adaptive", 25, bad)


def test_pending_full_cost_reservation_cannot_retry(tasks, tmp_path):
    path = tmp_path / "pending"
    archive = Archive(path, engine.binding(tasks, "adaptive", 25, "fixture"), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    raw = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(tasks, "adaptive", 25, path, "fixture", isolated=False)
    assert path.read_bytes() == raw


def evidence_fixture(tmp_path):
    reservation = {"schema": "mira-genesis-v32-single-attempt-reservation-v1", "status": "RESERVED",
                   "freeze_sha256": "fixture", "canonical_attempts": 1}
    storage.publish_json(tmp_path / "V32_RESERVATION.json", reservation)
    record = {"status": "COMPLETED", "freeze_sha256": "fixture", "canonical_attempts": 1, "negatives": [0, 1, 0]}
    verdict = {"finite_memory_usefulness_positive": False, "l9_open_ended_passed": False, "l10_independent_passed": False}
    return reservation, record, verdict


def test_completion_never_rewrites_reservation_and_preserves_all_negatives(tmp_path):
    reservation, record, verdict = evidence_fixture(tmp_path)
    before = (tmp_path / "V32_RESERVATION.json").read_bytes()
    storage.complete(tmp_path, record, verdict)
    assert storage.read_complete(tmp_path) == (record, verdict)
    assert (tmp_path / "V32_RESERVATION.json").read_bytes() == before
    with pytest.raises(FileExistsError):
        storage.complete(tmp_path, record, verdict)
    assert json.loads(before) == reservation


@pytest.mark.parametrize("name", ["V32_RESERVATION.json", "V32_ATTEMPT_RAW.json.gz", "V32_FINAL_ADJUDICATION.json",
                                  "V32_COMPLETION.json"])
def test_evidence_tampering_is_refused(tmp_path, name):
    _, record, verdict = evidence_fixture(tmp_path)
    storage.complete(tmp_path, record, verdict)
    path = tmp_path / name
    raw = path.read_bytes()
    path.write_bytes(raw[:-1])
    with pytest.raises((ValueError, EOFError)):
        storage.read_complete(tmp_path)


def test_single_assignment_existing_and_symlink_publication_refused(tmp_path):
    path, alias = tmp_path / "file", tmp_path / "alias"
    storage.publish_once(path, b"original")
    alias.symlink_to(path)
    for target in (path, alias):
        with pytest.raises(FileExistsError):
            storage.publish_once(target, b"replacement")
    with pytest.raises(OSError):
        storage.read_regular(alias)
    assert path.read_bytes() == b"original"


def test_partial_completion_cannot_be_read_or_retried(tmp_path, monkeypatch):
    _, record, verdict = evidence_fixture(tmp_path)
    storage.publish_once(tmp_path / "V32_ATTEMPT_RAW.json.gz", gzip.compress(canonical(record) + b"\n", mtime=0))
    with pytest.raises(FileNotFoundError):
        storage.read_complete(tmp_path)
    monkeypatch.setattr(campaign, "DIRECTORY", tmp_path)
    monkeypatch.setattr(campaign, "RESERVATION", tmp_path / "V32_RESERVATION.json")
    monkeypatch.setattr(campaign, "COMPLETION", tmp_path / "V32_COMPLETION.json")
    monkeypatch.setattr(freeze, "PATH", tmp_path / "freeze.json")
    freeze.PATH.write_text('{}')
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    with pytest.raises(ValueError, match="Missing completion"):
        campaign.check()


def test_existing_raw_must_match_before_completion(tmp_path):
    _, record, verdict = evidence_fixture(tmp_path)
    storage.publish_once(tmp_path / "V32_ATTEMPT_RAW.json.gz", b"different")
    with pytest.raises(ValueError, match="Previously preserved"):
        storage.complete(tmp_path, record, verdict)
    assert not (tmp_path / "V32_COMPLETION.json").exists()


def test_validated_consumed_selection_retains_all_variants():
    assert development.selection() == 25
    row = json.loads(gzip.decompress(development.PATH.read_bytes()))
    assert len(row["variants"]) == 12
    assert all(v["totals"]["tasks"] == 240 for v in row["variants"].values())
    assert row["scope"] == "ALL_240_CONSUMED_V31_TASKS_NOT_FRESH"


def test_unfrozen_work_never_passes_l9_or_l10(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "missing")
    value = campaign.check()
    assert value["status"] == "UNFROZEN"
    assert value["l9_open_ended_passed"] is value["l10_independent_passed"] is False
    with pytest.raises(ValueError):
        freeze.verify({})


def test_complete_assay_retains_negatives_and_rejects_omitted_control_or_checkpoint(tasks, tmp_path, monkeypatch):
    import sys
    monkeypatch.setattr(bank, "FRESH_SEEDS", (101,))
    monkeypatch.setattr(bank, "stream", lambda seed: tasks)
    frozen = {"freeze_sha256": "fixture", "tolerance_milli": 25, "tasks_per_arm": len(tasks),
              "python_version": sys.version.split()[0]}
    record = {"schema": "mira-genesis-v32-complete-attempt-v1", "status": "COMPLETED",
              "freeze_sha256": "fixture", "canonical_attempts": 1, "policy_sha256": programs.PARENT_SHA256,
              "python_version": frozen["python_version"], "track": "B", "scientific_external_model_calls": 0,
              "tolerance_milli": 25, "streams": {"101": {}}}
    for arm in engine.ARMS:
        path = tmp_path / arm
        engine.run_stream(tasks, arm, 25, path, "fixture", stop_after=6)
        checkpoint = Archive(path, engine.binding(tasks, arm, 25, "fixture")).read()[-1]["sha256"]
        rows, head = engine.run_stream(tasks, arm, 25, path, "fixture")
        record["streams"]["101"][arm] = {"episodes": rows, "journal": path.read_text(), "head_sha256": head,
                                        "checkpoint_position": 6, "checkpoint_head_sha256": checkpoint}
    result = campaign.adjudicate(record, frozen)
    assert all(row["tasks"] == len(tasks) for row in result["totals"].values())
    assert result["l9_open_ended_passed"] is result["l10_independent_passed"] is False
    assert result["finite_memory_usefulness_positive"] == all(result["predicates"].values())
    missing = copy.deepcopy(record)
    del missing["streams"]["101"]["cold"]
    with pytest.raises(ValueError, match="Omitted matched"):
        campaign.adjudicate(missing, frozen, replay=False)
    checkpoint_bad = copy.deepcopy(record)
    checkpoint_bad["streams"]["101"]["adaptive"]["checkpoint_head_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checkpoint"):
        campaign.adjudicate(checkpoint_bad, frozen, replay=False)
    incomplete = copy.deepcopy(record)
    incomplete["streams"]["101"]["adaptive"]["episodes"].pop()
    with pytest.raises(ValueError, match="Journal differs"):
        campaign.adjudicate(incomplete, frozen, replay=False)
