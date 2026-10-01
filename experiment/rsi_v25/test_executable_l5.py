"""Prospective apparatus tests. Never run canonical arms or successor transfer."""
from __future__ import annotations

import copy
import hashlib
import itertools
import json

import pytest

from experiment.rsi_v25.commitments import HERE, digest, digest_bytes
from experiment.rsi_v25.executable_family import (
    G2_SHA256, ROOT_PARAMS, acquired_components, neighbors, predecessor_source, render_source, universe,
)
from experiment.rsi_v25.public_development import DevelopmentHost, population
from experiment.rsi_v25.search_engine import Caps, GUARD, global_utility, run_search
from experiment.rsi_v25.native_transfer import TASKS, render_native
from experiment.rsi_v25.campaign_adjudication import validate_search
from experiment.rsi_v25 import scientific_freeze


def test_identity_is_the_actual_preserved_executable():
    assert render_source(ROOT_PARAMS) == predecessor_source()
    assert digest_bytes(render_source(ROOT_PARAMS).encode()) == G2_SHA256
    assert len(universe()) == 30
    assert len({row["source_sha256"] for row in universe()}) == 30


@pytest.mark.parametrize("row", universe())
def test_entire_executable_grammar_is_guarded_and_runnable(row):
    source = render_source(row["params"])
    assert GUARD.guard_source(source) == []
    functions = {}
    exec(compile(source, "<bounded-test-candidate>", "exec"), functions)
    # ABI/metadata and a fixture where a composed novelty/strategy function runs.
    view = {"root_node_id": "root", "eligible_parent_ids": ["root"],
            "revealed_nodes": [{"node_id": "root", "lineage_depth": 0,
                               "action": {"family": "fixture", "mechanisms": ["root"],
                                          "target_axes": [], "changed_regions": []},
                               "outcome": {"quality_milli": 0, "evolver_profile_generation": 0,
                                           "ever_champion": True, "root_branch_node_id": "root"}}]}
    assert functions["select_parent_batch"](view, 1) == ["root"]
    assert len(functions["policy_metadata"]()) == 10


def test_mutation_order_is_prospective_and_does_not_read_scores():
    first = neighbors(ROOT_PARAMS)[0]
    assert (first["axis"], first["to"]) == ("strategy", "depth_first")
    assert neighbors(first["params"])[0]["axis"] == "stop_quality"
    assert all(sum(parent != row["params"][axis] for axis, parent in ROOT_PARAMS.items()) == 1
               for row in neighbors(ROOT_PARAMS))


@pytest.mark.parametrize("change", [{"new_axis": 1}, {"stop_quality": 123}, {"stall_rounds": True}])
def test_unknown_and_mistyped_mutations_are_rejected(change):
    with pytest.raises(ValueError):
        render_source({**ROOT_PARAMS, **change})


def test_public_population_is_complete_and_identity_addressed():
    assert len(population()) == 36
    assert len({digest(row) for row in population()}) == 36
    calibration = json.loads((HERE / "PUBLIC_DEVELOPMENT_CALIBRATION.json").read_text())
    assert calibration["scope"] == "PUBLIC_DEVELOPMENT_ONLY_NOT_A_SCIENTIFIC_ARM"
    assert calibration["population_sha256"] == digest(population())
    assert not calibration["holdout_consumed"]
    for row in calibration["candidates"]:
        assert row["source_sha256"] == digest_bytes(render_source(row["params"]).encode())
        assert len(row["episodes"]) == 36
        assert tuple(row["utility"]) == global_utility(row["episodes"])
        assert row["eligible_successor"] == bool(
            row["params"] != ROOT_PARAMS and row["parent_choice_witness"]
            and any(axis in acquired_components(row["params"]) for axis in ("strategy", "depth_weight", "novelty_weight"))
            and all(tuple(row["utility"]) > tuple(x["utility"]) for x in row["component_ablations"])
            and tuple(row["utility"]) > tuple(next(x["utility"] for x in calibration["candidates"]
                                                  if x["params"] == ROOT_PARAMS)))


def test_hidden_authority_is_rejected_before_execution():
    source = predecessor_source().replace("    rows = list(view", "    import os\n    rows = list(view")
    with pytest.raises(ValueError, match="source guard"):
        run_search(source, DevelopmentHost(population()[0]))


def test_external_caps_stop_development_search():
    result = run_search(predecessor_source(), DevelopmentHost(population()[0]),
                        caps=Caps(requests=1, rounds=1, parallelism=1, mutation_depth=2), isolated=False)
    assert result["represented_requests"] == result["rounds"] == 1
    assert result["stop_reason"] == "external_request_budget"
    for invalid in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            Caps(requests=invalid).validate()


def test_bad_utility_cannot_create_a_positive_result():
    with pytest.raises(ValueError):
        global_utility([])
    with pytest.raises(ValueError):
        global_utility([{"accepted": False}])


def test_parallel_shared_children_are_not_evaluated_twice():
    class SharedHost:
        forbidden_tokens = []
        def __init__(self):
            self.evaluated = []
        def row(self, token):
            return {"candidate": {"token": token}, "quality_milli": 10,
                    "source_sha256": digest(token)}
        def root(self):
            return {**self.row("root"), "quality_milli": 0}
        def children(self, candidate, depth):
            if candidate["token"] == "root":
                return (self.row("first"), self.row("shared"))
            if candidate["token"] == "first":
                return (self.row("shared"),)
            return ()
        def evaluate(self, row):
            self.evaluated.append(row["source_sha256"])
            return {"accepted": True, "quality_milli": 10, "source_sha256": row["source_sha256"]}
        def action(self, row):
            return {"family": "fixture", "target_axes": [], "mechanisms": [], "changed_regions": []}
        def generation(self, row, depth):
            return 0
    source = ("def policy_metadata():\n    return (0,0,0,0,0,0,0,2,8,8)\n"
              "def select_parent_batch(view, max_parallelism):\n"
              "    return list(view['eligible_parent_ids'])[:max_parallelism]\n")
    host = SharedHost()
    result = run_search(source, host, caps=Caps(requests=9, rounds=8, parallelism=2, mutation_depth=2))
    assert result["represented_requests"] == 2
    assert len(host.evaluated) == len(set(host.evaluated)) == 2
    assert len(result["observations"][1]["parent_node_ids"]) == 2
    assert len(result["observations"][1]["result_node_ids"]) == 1


def test_native_grammar_is_separate_and_byte_exact():
    manifest = json.loads((HERE / "native_sources/SOURCE_MANIFEST.json").read_text())
    for source in manifest["sources"]:
        raw = (HERE / "native_sources" / source["file"]).read_bytes()
        assert source["source_sha256"] == digest_bytes(raw)
        assert source["git_blob_sha1"] == hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert not manifest["independent_external_maintainer"]
    assert len(TASKS) == 4
    for task in TASKS:
        assert render_native(task, (0, 0)).encode() == (HERE / "native_sources" / task["source"]).read_bytes()
        assert len({digest_bytes(render_native(task, choices).encode())
                    for choices in itertools.product((0, 1, 2), repeat=2)}) == 9


def test_native_reference_calibration_never_executed_a_successor():
    record = json.loads((HERE / "NATIVE_HOST_CALIBRATION.json").read_text())
    assert record["scope"] == "REFERENCE_AND_SEEDED_ROOT_CALIBRATION_ONLY"
    assert not record["successor_executed"]
    assert record["population_sha256"] == digest(TASKS)
    assert [row["task_id"] for row in record["tasks"]] == [task["task_id"] for task in TASKS]
    assert all(row["reference"]["quality_milli"] == 1000 and row["seeded"]["quality_milli"] < 1000
               for row in record["tasks"])


def test_scientific_freeze_rejects_uncommitted_inputs(tmp_path, monkeypatch):
    fresh = tmp_path / "candidate.py"
    fresh.write_text("uncommitted")
    monkeypatch.setattr(scientific_freeze, "ROOT", tmp_path)
    monkeypatch.setattr(scientific_freeze, "FREEZE_PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(scientific_freeze, "input_paths", lambda: (fresh,))
    monkeypatch.setattr(scientific_freeze, "git", lambda *args: "abc" if args[0] == "rev-parse" else "")
    with pytest.raises(ValueError, match="not committed"):
        scientific_freeze.build()


def test_forged_freeze_and_best_quality_are_rejected():
    with pytest.raises(ValueError, match="altered scientific freeze"):
        scientific_freeze.verify({"schema": scientific_freeze.SCHEMA, "freeze_sha256": "0" * 64})
    result = run_search(predecessor_source(), DevelopmentHost(population()[0]), isolated=False)
    result["isolated_policy_processes"] = True
    result["caps"] = Caps().__dict__
    result["best_quality_milli"] += 1
    with pytest.raises(ValueError, match="best-quality"):
        validate_search(result, calibration={"candidates": []})


def test_meta_and_native_modules_do_not_import_each_other():
    assert "native_transfer" not in (HERE / "executable_meta.py").read_text()
    assert "executable_meta" not in (HERE / "native_transfer.py").read_text()
    assert "native_harnesses" not in (HERE / "executable_family.py").read_text()


def test_one_shot_marker_refuses_restart_without_modifying_evidence(tmp_path, monkeypatch):
    from experiment.rsi_v25 import run_executable_campaign as runner
    marker = tmp_path / "attempt.json"
    marker.write_text("already consumed")
    monkeypatch.setattr(runner, "ATTEMPT", marker)
    monkeypatch.setattr(runner, "committed_freeze", lambda: {"runtime_versions": {}, "freeze_sha256": "fixture"})
    monkeypatch.setattr(runner, "runtime_versions", lambda: {})
    with pytest.raises(FileExistsError):
        runner.run()
    assert marker.read_text() == "already consumed"


def test_missing_result_cannot_report_l5_positive(tmp_path, monkeypatch):
    from experiment.rsi_v25 import check_executable_result as checker
    monkeypatch.setattr(checker, "FREEZE_PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(checker, "ATTEMPT", tmp_path / "attempt.json")
    monkeypatch.setattr(checker, "ADJUDICATION", tmp_path / "verdict.json")
    assert checker.check()["v25_l5_positive"] is False
    with pytest.raises(ValueError, match="committed full scientific freeze"):
        checker.check(require_result=True)


def test_recorded_result_replays_without_consuming_new_cases():
    from experiment.rsi_v25 import check_executable_result as checker
    if not checker.ATTEMPT.exists():
        pytest.skip("Prospective apparatus: canonical record has not been consumed")
    result = checker.check(require_result=True)
    assert result["status"] in ("POSITIVE_BOUNDED_L5", "VALID_NEGATIVE_FRESH_TRANSFER",
                                "NEGATIVE_PRE_TRANSFER", "PRESERVED_INSTRUMENT_ABORT")
