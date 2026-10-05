"""Coupled semantics, causal donors, exact work, containment and recovery."""
import copy
import json

import pytest

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31.archive import Archive, ZERO
from experiment.rsi_v32 import storage
from experiment.rsi_v49 import bank, campaign, engine, native


def fixture(ops, domain="punctuation"):
    texts = native.contexts(41, domain, 2, 0)
    return {"task_id": "public-coupled-fixture", "domain": domain, "epoch": len(ops).bit_length() - 1,
        "slots": len(ops), "target": ops, "inputs": texts,
        "answers": [native.reference(ops, text)["value"] for text in texts]}


def library():
    history = {}
    for length in (1, 2):
        for op in range(1, 5):
            task = fixture([op] * length)
            value = native.genome(task["domain"], task["target"])
            evaluation = native.evaluate(task, value, isolated=False)
            sha = evaluation["source_sha256"]
            history[sha] = {"genome": value, "source_sha256": sha, "semantic_sha256": evaluation["semantic_sha256"],
                "parent_source_sha256": None, "evaluation": evaluation, "successes": 1,
                "first_success_position": length + op, "last_success_position": length + op}
    return history


@pytest.mark.parametrize("domain", native.DOMAINS)
def test_coupled_native_codec_results_and_actual_work_match_independent_reference(domain):
    task = fixture([1, 2, 3, 4], domain)
    value = native.genome(domain, task["target"])
    receipt = native.evaluate(task, value)
    assert receipt["quality_milli"] == 1000 and receipt["primitive_visits"] == 8 * 4
    assert receipt["transformed_bytes"] > 0
    for text, output in zip([*task["inputs"], *native.WITNESSES], receipt["outputs"]):
        assert output == {"ok": True, "value": native.reference(task["target"], text)}
    changed = native.evaluate(task, native.genome(domain, [4, 3, 2, 1]))
    assert changed["matched_contexts"] == 0
    assert changed["semantic_sha256"] != receipt["semantic_sha256"]


def test_removing_latest_acquired_tools_reduces_later_coupled_construction():
    history, task = library(), fixture([4, 4, 3, 3])
    rows = {arm: engine.episode(task, 100, history, arm, isolated=False) for arm in engine.ARMS}
    assert rows["archive"]["solved"] and not rows["archive-ancestor"]["solved"]
    assert rows["archive"]["selected_root_sha256"] == rows["archive-ancestor"]["selected_root_sha256"]
    assert not rows["greedy"]["solved"] and not rows["cold"]["solved"]
    for arm, row in rows.items():
        assert len(row["calls"]) == row["charged_evaluations"] <= 26
        assert row["primitive_visits"] == sum(8 * len(call["genome"]["ops"]) for call in row["calls"])
        assert engine.verify_episode(task, 100, history, arm, row, isolated=False)
        for call in row["calls"]:
            for donor in call["construction"].get("donors", []):
                sha = donor["donor_source_sha256"]
                if sha:
                    assert donor["ops"] == history[sha]["genome"]["ops"]
                    assert donor["acquired_position"] < 100


def test_prior_failed_observation_prevents_relabelling_behavior_as_novel():
    task = fixture([1])
    value = native.genome(task["domain"], [1])
    measured = native.evaluate(task, value, isolated=False)
    history = {measured["source_sha256"]: {"genome": value, "source_sha256": measured["source_sha256"],
        "semantic_sha256": measured["semantic_sha256"], "parent_source_sha256": None,
        "successes": 0, "first_success_position": -1, "last_success_position": -1}}
    row = engine.episode(task, 1, history, "cold", isolated=False)
    assert row["solved"] and row["new_first_solving_semantics"]
    assert row["new_novel_solving_behaviors"] == []


@pytest.mark.parametrize("field", ("primitive_visits", "transformed_bytes", "new_novel_solving_behaviors", "learned_fragments"))
def test_work_donor_and_novelty_tampering_are_rejected(field):
    task, history = fixture([4, 4, 3, 3]), library()
    row = engine.episode(task, 100, history, "archive", isolated=False)
    bad = copy.deepcopy(row)
    bad[field] = None
    with pytest.raises(ValueError, match="Altered"):
        engine.verify_episode(task, 100, history, "archive", bad, isolated=False)


def test_isolated_candidate_payload_has_no_target_reference_or_task_identifier(monkeypatch):
    task = fixture([2])
    original, payloads = native.subprocess.run, []

    def capture(*args, **kwargs):
        if "input" in kwargs:
            payloads.append(json.loads(kwargs["input"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(native.subprocess, "run", capture)
    row = engine.episode(task, 0, {}, "cold")
    assert row["solved"] and payloads
    assert all(set(item) == {"operation", "data"} and set(item["data"]) == {"text"}
        for payload in payloads for item in payload["operations"])


def test_reference_ascii_quote_handles_surrogate_pairs_and_control_characters():
    text = "\x00\b\f\n\r\t\"\\é🙂\x7f"
    assert native.quote_ascii(text) == json.dumps(text, ensure_ascii=True).encode("ascii")


def test_unchanged_completed_prefix_and_pending_reservation_recovery(tmp_path, monkeypatch):
    tasks = bank.stream(41, native.DOMAINS[0], epochs=2, tasks_per_epoch=4)
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


def test_negative_progression_cannot_freeze_fresh_population(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "check", lambda root: {"development_progression_passed": False})
    monkeypatch.setattr(campaign, "FREEZE", tmp_path / "freeze.json")
    with pytest.raises(ValueError, match="no fresh attempt"):
        campaign.freeze()


def test_global_reservation_tampering_is_checked_before_epochs(tmp_path, monkeypatch):
    value = {"mode": "pilot", "tasks_per_arm": 256, "maximum_evaluations_per_arm": 6656}
    storage.publish_json(tmp_path / "MANIFEST.json", value)
    storage.publish_json(tmp_path / "RESERVATION.json", {**campaign.reservation(value), "maximum_charged_evaluations": 1})
    monkeypatch.setattr(campaign, "verify_manifest", lambda value: True)
    with pytest.raises(ValueError, match="global reservation"):
        campaign.collect(tmp_path, replay=True)
