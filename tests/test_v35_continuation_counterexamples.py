"""Assumption audits outside the frozen assay; no new fresh task population."""
from experiment.rsi_v27.engine import development_functions
from experiment.rsi_v31 import programs as policy
from experiment.rsi_v35 import engine, native


def retained_prefixes(length):
    history = {}
    for first in range(1, 5):
        value = native.genome(native.DOMAINS[0], [first] + [2] * (length - 2))
        descriptor = native.descriptor(value)
        history[descriptor["source_sha256"]] = {"genome": value, **descriptor,
            "parent_source_sha256": None, "successes": 1, "last_success_position": first}
    return history


def test_raw_screening_disambiguates_prefixes_when_normalized_quality_aliases():
    length = 2001
    target = [3] + [2] * (length - 2) + [4]
    task = {"task_id": "development-rounding-assumption", "domain": native.DOMAINS[0],
            "epoch": length - 1, "slots": length, "target": target,
            "inputs": native.contexts(17, native.DOMAINS[0], length - 1, 0)}
    host = engine.Host(task, retained_prefixes(length), "archive", isolated=False)
    screen = [c["evaluation"] for c in host.calls if c["kind"] == "screen"]
    assert {r["quality_milli"] for r in screen} == {999}
    assert {r["matched_slots"] for r in screen} == {1999, 2000}
    assert host.selected["candidate"]["ops"] == target[:-1]


def test_quality_floor_tie_cannot_trigger_strict_gain_root_dropping():
    functions = development_functions(policy.parent(), ())
    nodes = [
        {"node_id": "root", "parent_node_id": None, "lineage_depth": 0,
         "action": {"target_axes": ["old"]}, "outcome": {"quality_milli": 999}},
        {"node_id": "one", "parent_node_id": "root", "lineage_depth": 1,
         "action": {"target_axes": ["old", "new"]}, "outcome": {"quality_milli": 999}},
        {"node_id": "two", "parent_node_id": "one", "lineage_depth": 2,
         "action": {"target_axes": ["old", "new"]}, "outcome": {"quality_milli": 999}}]
    view = {"root_node_id": "root", "revealed_nodes": nodes, "eligible_parent_ids": ["root", "two"]}
    assert functions["select_parent_batch"](view, 2) == ["two", "root"]


def test_rewriting_old_slots_breaks_the_model_despite_intact_branch_archive():
    length = 12
    task = {"task_id": "development-prefix-rewrite-counterexample", "domain": native.DOMAINS[0],
            "epoch": length - 1, "slots": length, "target": [3] * (length - 1) + [4],
            "inputs": native.contexts(43, native.DOMAINS[0], length - 1, 0)}
    history = retained_prefixes(length)
    assert len(engine.frontiers(history, native.DOMAINS[0], "archive")) == 4
    row = engine.episode(task, 10, history, "archive", isolated=False)
    assert not row["solved"] and row["new_first_solving_semantics"] == []
    assert max(c["evaluation"]["matched_slots"] for c in row["calls"]) <= 4
    assert row["charged_evaluations"] <= 14
    assert engine.verify_episode(task, 10, history, "archive", row, isolated=False)
