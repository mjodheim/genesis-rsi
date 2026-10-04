"""Corrective successor tests: all charged probes are real archived candidates."""
import copy

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import bank
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import engine as original
from experiment.rsi_v34 import development, engine


@pytest.fixture
def tasks():
    return bank.stream(bank.DEV_SEEDS[0])[:24]


def rows_for(tasks, arm="probe", isolated=False):
    rows = []
    for position, task in enumerate(tasks):
        rows.append(engine.episode(task, position, engine.history_from(rows), arm, isolated=isolated))
    return rows


def test_original_probe_only_success_omission_has_a_real_consumed_counterexample(tasks):
    # s101 window 1 task 3: rotation by one is itself a successful paid probe.
    task = tasks[15]
    previous = original.episode(task, 0, {}, "cold", isolated=False)
    assert not previous["solved"] and any(p["quality_milli"] == 1000 for p in previous["probes"])
    corrected = engine.episode(task, 0, {}, "cold", isolated=False)
    assert corrected["solved"] and corrected["solved_by_probes"] and not corrected["solved_by_search"]
    assert corrected["search"] == previous["search"]
    assert corrected["charged_evaluations"] == previous["charged_evaluations"]
    assert engine.verify_stream([task], "cold", [corrected], isolated=False)


@pytest.mark.parametrize("arm", engine.ARMS)
def test_all_paid_candidates_and_failed_probes_survive_in_archive(tasks, arm):
    rows = rows_for(tasks[:4], arm)
    for row in rows:
        sources = {p["source_sha256"] for p in row["programs"]}
        assert sources == ({p["source_sha256"] for p in row["probes"]}
                           | {node["source_sha256"] for node in row["search"]["nodes"].values()})
        assert row["solved"] == (row["solved_by_probes"] or row["solved_by_search"])
        assert row["solved"] == any(p["quality_milli"] == 1000 for p in row["programs"])
        assert row["charged_evaluations"] == len(row["probes"]) + row["search"]["represented_requests"] + 1 <= 14
    history = engine.history_from(rows)
    assert set(history) == {p["source_sha256"] for row in rows for p in row["programs"]}
    assert any(p["quality_milli"] < 1000 for row in rows for p in row["probes"])
    assert engine.verify_stream(tasks[:4], arm, rows, isolated=False)


def test_duplicate_probe_and_search_call_is_charged_twice_but_archived_once(tasks):
    row = rows_for(tasks[:1])[0]
    probe_sources = {p["source_sha256"] for p in row["probes"]}
    search_sources = {n["source_sha256"] for n in row["search"]["nodes"].values()}
    assert len(probe_sources & search_sources) > 1
    assert len(row["programs"]) == len(probe_sources | search_sources)
    assert row["charged_evaluations"] > len(row["programs"]) + 1


def test_probe_descendants_have_actual_root_ancestry(tasks):
    row = engine.episode(tasks[15], 0, {}, "cold", isolated=False)
    root = row["root_evaluation"]["source_sha256"]
    probes = [p for p in row["programs"] if p["evaluation_origin"] == "probe"]
    assert probes
    assert all(p["parent_source_sha256"] == root and p["search_parent_source_sha256"] == root for p in probes)


def test_omitted_paid_probe_or_solve_cannot_replay(tasks):
    task = tasks[15]
    row = engine.episode(task, 0, {}, "cold", isolated=False)
    bad = copy.deepcopy(row)
    bad["programs"] = [p for p in bad["programs"] if p["evaluation_origin"] != "probe"]
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_stream([task], "cold", [bad], isolated=False)
    bad = copy.deepcopy(row)
    bad["solved"] = False
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_stream([task], "cold", [bad], isolated=False)


def test_fresh_process_execution_and_exact_boundary_recovery(tasks, tmp_path):
    # Include the measured omission fixture, with actual isolated candidate and policy workers.
    subset = [tasks[15], tasks[16]]
    first, second = tmp_path / "first", tmp_path / "second"
    complete, head = engine.run_stream(subset, "probe", first, "fixture")
    engine.run_stream(subset, "probe", second, "fixture", stop_after=1)
    resumed, restored_head = engine.run_stream(subset, "probe", second, "fixture")
    assert complete == resumed and head == restored_head and first.read_bytes() == second.read_bytes()
    assert complete[0]["solved_by_probes"]
    assert engine.verify_stream(subset, "probe", resumed)
    with pytest.raises(ValueError, match="binding"):
        original.run_stream(subset, "probe", second, "fixture")


def test_pending_call_and_altered_probe_quality_fail_closed(tasks, tmp_path):
    path = tmp_path / "pending"
    a = Archive(path, engine.binding(tasks[:1], "probe", "fixture", False), create=True)
    a.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 14})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(tasks[:1], "probe", path, "fixture", isolated=False)
    assert path.read_bytes() == before
    rows = rows_for(tasks[:1])
    rows[0]["probes"][1]["quality_milli"] -= 1
    with pytest.raises(ValueError, match="probe receipt"):
        engine.verify_stream(tasks[:1], "probe", rows, isolated=False)


def test_complete_corrected_evidence_and_no_replacement(tasks, tmp_path, monkeypatch):
    monkeypatch.setattr(development, "population", lambda: {"consumed": [tasks[15], tasks[16]]})
    monkeypatch.setattr(development, "manifest", lambda: {"scope": "CONSUMED_FIXTURE_NOT_SCIENCE"})
    report = development.run(tmp_path)
    assert development.check(tmp_path) == report
    assert all(t["tasks"] == 2 for t in report["totals"].values())
    assert report["l9_open_ended_passed"] is False
    assert report["new_recursive_transition_established"] is False
    with pytest.raises(FileExistsError, match="completed"):
        development.run(tmp_path)
