"""Consumed-fixture tests of information boundaries, full costs and recovery."""
import copy
import gzip
import json

import pytest

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27 import engine as policy
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import development, engine


@pytest.fixture
def tasks():
    return bank.stream(bank.DEV_SEEDS[0])[:8]


def episodes(tasks, arm="probe", isolated=False):
    rows = []
    for position, task in enumerate(tasks):
        rows.append(engine.episode(task, position, engine.history_from(rows), arm, isolated=isolated))
    return rows


def test_all_consumed_populations_and_all_controls_are_present():
    population = development.population()
    assert len(population) == 8 and sum(map(len, population.values())) == 456
    assert set(engine.ARMS) == {"probe", "scalar", "probe_ablation", "cold"}
    assert digest_bytes(engine.controller("probe").encode()) == programs.PARENT_SHA256
    assert engine.controller("probe_ablation") == family.parent()
    assert engine.CAPS.requests == 10 and engine.MAX_EVALUATIONS == 14


@pytest.mark.parametrize("arm", engine.ARMS)
def test_every_arm_pays_for_three_probes_and_one_controller(tasks, arm):
    rows = episodes(tasks[:2], arm)
    for row in rows:
        assert len(row["probes"]) == 3 and len({r["source_sha256"] for r in row["probes"]}) == 3
        assert row["fingerprint"] == [r["quality_milli"] for r in row["probes"]]
        assert row["charged_evaluations"] == row["search"]["represented_requests"] + 4 <= 14
        assert row["search"]["caps"] == engine.CAPS.__dict__
        assert row["search"]["policy_sha256"] == programs.PARENT_SHA256
        assert row["routing"]["controller_calls"] == 1
    assert engine.verify_stream(tasks[:2], arm, rows, isolated=False)


def test_scalar_alias_can_be_distinguished_by_additional_measurements(tasks):
    first, second = (engine.Host(task, {}, "probe", isolated=False) for task in tasks[:2])
    assert first.fingerprint[0] == second.fingerprint[0]
    assert first.fingerprint != second.fingerprint
    assert engine.distance(first.fingerprint, second.fingerprint, "scalar") == 0
    assert engine.distance(first.fingerprint, second.fingerprint, "probe") > 0


def test_isolated_actor_receives_no_hidden_inputs_or_fingerprint(tasks, monkeypatch):
    original = policy.call
    modes = []
    def observe(path, payload):
        modes.append(payload["mode"])
        def keys(value):
            if isinstance(value, dict):
                return set(value) | set().union(*(keys(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(keys(v) for v in value))
            return set()
        assert not keys(payload) & {"inputs", "target", "task_family", "fingerprint", "genome", "probes"}
        assert tasks[0]["task_id"] not in json.dumps(payload)
        if payload["mode"] == "target":
            assert set(payload["diagnostics"]) == {"exploration", "generation", "scheduling"}
        return original(path, payload)
    monkeypatch.setattr(policy, "call", observe)
    monkeypatch.setattr(meta, "call", observe)
    row = engine.episode(tasks[0], 0, {}, "probe")
    assert modes.count("target") == 1
    assert engine.verify_stream(tasks[:1], "probe", [row])


def test_history_keeps_failed_descendants_but_ranks_only_past_successes(tasks):
    rows = episodes(tasks[:2])
    history = engine.history_from(rows)
    assert len(history) == len({r["source_sha256"] for e in rows for r in e["programs"]})
    assert any(not entry["successes"] for entry in history.values())
    host = engine.Host(tasks[2], history, "probe", isolated=False)
    assert all(entry["successes"] and entry["successful_fingerprints"] for entry in host.retrieved)
    assert rows[0]["archive_size_before"] == 0


def test_completed_boundary_recovery_is_byte_exact(tasks, tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    uninterrupted, head = engine.run_stream(tasks, "probe", a, "fixture", isolated=False)
    engine.run_stream(tasks, "probe", b, "fixture", isolated=False, stop_after=3)
    restored, restored_head = engine.run_stream(tasks, "probe", b, "fixture", isolated=False)
    assert restored == uninterrupted and restored_head == head and b.read_bytes() == a.read_bytes()
    assert engine.verify_stream(tasks, "probe", restored, isolated=False)
    with pytest.raises(ValueError, match="binding"):
        engine.run_stream(tasks, "probe", b, "fixture", isolated=True)


@pytest.mark.parametrize("field", ("probes", "fingerprint", "charged_evaluations", "routing"))
def test_altered_diagnostics_or_costs_are_refused(tasks, field):
    rows = episodes(tasks[:2])
    bad = copy.deepcopy(rows)
    if field == "probes":
        bad[0][field][1]["quality_milli"] -= 1
    elif field == "fingerprint":
        bad[0][field][1] -= 1
    elif field == "charged_evaluations":
        bad[0][field] -= 1
    else:
        bad[0][field]["retrieved_sources"].append("substituted")
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_stream(tasks[:2], "probe", bad, isolated=False)
    with pytest.raises(ValueError, match="Omitted"):
        engine.verify_stream(tasks[:2], "probe", rows[:1], isolated=False)


def test_pending_reservation_cannot_be_retried_for_free(tasks, tmp_path):
    path = tmp_path / "pending.jsonl"
    archive = Archive(path, engine.binding(tasks, "probe", "fixture", False), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(tasks, "probe", path, "fixture", isolated=False)
    assert path.read_bytes() == before


def test_complete_evidence_replay_and_no_overwrite(tasks, tmp_path, monkeypatch):
    monkeypatch.setattr(development, "population", lambda: {"consumed-fixture": tasks[:2]})
    monkeypatch.setattr(development, "manifest", lambda: {"scope": "CONSUMED_FIXTURE_NOT_SCIENCE"})
    report = development.run(tmp_path)
    assert development.check(tmp_path) == report
    assert all(t["tasks"] == 2 for t in report["totals"].values())
    assert report["l9_open_ended_passed"] is False and report["new_recursive_transition_established"] is False
    before = (tmp_path / "DEVELOPMENT.json.gz").read_bytes()
    with pytest.raises(FileExistsError, match="completed"):
        development.run(tmp_path)
    assert (tmp_path / "DEVELOPMENT.json.gz").read_bytes() == before
    record = json.loads(gzip.decompress(before))
    del record["streams"]["consumed-fixture"]["cold"]
    (tmp_path / "DEVELOPMENT.json.gz").write_bytes(gzip.compress(json.dumps(record).encode()))
    with pytest.raises(ValueError, match="raw evidence"):
        development.check(tmp_path)
