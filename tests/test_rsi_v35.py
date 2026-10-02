"""Archive continuation, witness and governance boundaries on consumed public data."""
import copy
import gzip
import json
import sys

import pytest

from experiment.rsi_v25.commitments import canonical, digest, digest_bytes
from experiment.rsi_v27 import engine as policy
from experiment.rsi_v30 import meta
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import storage
from experiment.rsi_v35 import bank, campaign, development, engine, freeze, programs


@pytest.fixture
def public_tasks():
    return bank.stream(bank.DEV_SEEDS[0], 0)


def test_bank_progressive_domains_capacity_and_disjointness_without_behavior():
    assert not set(bank.DEV_SEEDS) & set(bank.FRESH_SEEDS)
    assert [len(bank.stream(bank.FRESH_SEEDS[0], e)) for e in range(8)] == [6, 12, 18, 24, 24, 24, 24, 24]
    assert sum(len(bank.stream(seed, e)) for seed in bank.FRESH_SEEDS for e in range(8)) == 468
    for e in range(8):
        assert {t["domain"] for t in bank.stream(bank.FRESH_SEEDS[0], e)} == set(programs.DOMAINS[:min(e + 1, 4)])
    with pytest.raises(ValueError, match="capacity"):
        bank.stream(1, programs.MAX_STEPS)


def test_new_domain_starts_at_one_step_then_grows_without_changing_old_v34():
    from experiment.rsi_v34 import bank as old_bank
    for epoch in range(8):
        tasks = bank.stream(bank.DEV_SEEDS[0], epoch)
        for domain_index, domain in enumerate(programs.DOMAINS[:min(epoch + 1, 4)]):
            local = [task for task in tasks if task["domain"] == domain]
            assert [len(t["target"]["steps"]) for t in local[:4]] == [epoch - domain_index + 1] * 4
    assert len(old_bank.stream(503, 3)[-6]["target"]["steps"]) == 4
    assert len(bank.stream(503, 3)[-6]["target"]["steps"]) == 1


def test_adaptive_probe_slots_do_not_both_go_to_observed_aliases(public_tasks):
    task = public_tasks[0]
    history = {}
    for position, steps in enumerate(([1], [0], [3, 3, 0])):
        genome = {"domain": "arithmetic", "steps": list(steps)}
        sha = programs.descriptor(genome)["source_sha256"]
        history[sha] = {"genome": genome, "source_sha256": sha, "successes": 1,
            "last_success_position": position, "successful_root_qualities": [0],
            "behavior_witness_sha256": digest(engine.execute(genome, programs.WITNESSES["arithmetic"], isolated=False))}
    adaptive = engine.Host(task, history, "adaptive", isolated=False)
    recency = engine.Host(task, history, "recency", isolated=False)
    signatures = lambda host: {history[sha]["behavior_witness_sha256"] for sha in host.routing["archive_probe_sources"]}
    assert len(signatures(adaptive)) == 2
    assert len(signatures(recency)) == 1


@pytest.mark.parametrize("domain", programs.DOMAINS)
def test_pure_execution_same_outputs_isolated_and_development(domain):
    genome = programs.validate({"domain": domain, "steps": [0, 1, 2, 3]})
    assert engine.execute(genome, programs.WITNESSES[domain]) == engine.execute(genome, programs.WITNESSES[domain], isolated=False)
    assert programs.render(genome).startswith(programs.parent())
    assert engine.similarity(domain, engine.execute(genome, programs.WITNESSES[domain], isolated=False)[0],
                             engine.execute(genome, programs.WITNESSES[domain], isolated=False)[0]) == 1000


def test_observed_witness_diversity_does_not_count_obvious_source_aliases():
    identity = programs.identity("arithmetic")
    alias = {"domain": "arithmetic", "steps": [3, 3]}
    assert programs.descriptor(identity)["source_sha256"] != programs.descriptor(alias)["source_sha256"]
    assert engine.execute(identity, programs.WITNESSES["arithmetic"]) == engine.execute(alias, programs.WITNESSES["arithmetic"])
    assert len({programs.descriptor(programs.identity(d))["source_sha256"] for d in programs.DOMAINS}) == 4


@pytest.mark.parametrize("arm", engine.ARMS)
def test_all_probe_calls_are_distinct_charged_and_bounded(public_tasks, arm, monkeypatch):
    candidate_calls = []
    original = engine.execute
    def execute(genome, inputs, *, isolated=True):
        if isolated:
            candidate_calls.append(genome)
        return original(genome, inputs, isolated=isolated)
    monkeypatch.setattr(engine, "execute", execute)
    row = engine.episode(public_tasks[0], 0, [], arm)
    assert len(candidate_calls) == row["search"]["represented_requests"] + 3
    assert len({digest(g) for g in candidate_calls}) == len(candidate_calls)
    assert row["charged_evaluations"] == len(candidate_calls) + 1 <= 14
    assert row["routing"]["controller_sha256"] == programs.PARENT_SHA256
    for program in row["programs"]:
        assert program["evaluation"]["public_behavior_witnesses"] == len(programs.WITNESSES["arithmetic"])


def test_policy_and_selector_receive_no_domain_target_inputs_or_witness_output(public_tasks, monkeypatch):
    original, observed = policy.call, []
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(x) for x in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(x) for x in value))
        return set()
    def call(path, payload):
        assert not keys(payload) & {"domain", "inputs", "target", "task_id", "genome", "behavior_witness_sha256"}
        observed.append(payload)
        return original(path, payload)
    monkeypatch.setattr(policy, "call", call)
    monkeypatch.setattr(meta, "call", call)
    engine.episode(public_tasks[0], 0, [], "adaptive")
    assert sum(x["mode"] == "target" for x in observed) == 1


def test_epoch_resume_and_history_carry_are_exact(public_tasks, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    rows, head = engine.run_stream(public_tasks, "adaptive", a, "fixture", None, [], isolated=False)
    engine.run_stream(public_tasks, "adaptive", b, "fixture", None, [], isolated=False, stop_after=3)
    resumed, resumed_head = engine.run_stream(public_tasks, "adaptive", b, "fixture", None, [], isolated=False)
    assert rows == resumed and head == resumed_head and a.read_bytes() == b.read_bytes()
    next_tasks = bank.stream(bank.DEV_SEEDS[0], 1)
    continued, _ = engine.run_stream(next_tasks, "adaptive", tmp_path / "next", "fixture", "previous", rows, isolated=False)
    assert continued[0]["absolute_position"] == len(rows)
    assert continued[0]["archive_source_size_before"] == len(engine.history_from(rows))
    assert engine.verify_stream(next_tasks, "adaptive", rows, continued, isolated=False)
    with pytest.raises(ValueError, match="binding"):
        engine.run_stream(next_tasks, "adaptive", tmp_path / "next", "fixture", "different", rows, isolated=False)
    with pytest.raises(ValueError, match="binding"):
        engine.run_stream(next_tasks, "adaptive", tmp_path / "next", "fixture", "previous", [], isolated=False)


def test_pending_epoch_task_never_retries(public_tasks, tmp_path):
    path = tmp_path / "pending"
    archive = Archive(path, engine.binding(public_tasks, "adaptive", "fixture", None, []), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(public_tasks[0]), "reserved_evaluations": 14})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(public_tasks, "adaptive", path, "fixture", None, [], isolated=False)
    assert path.read_bytes() == before


def epoch_fixture(tmp_path, tasks, monkeypatch):
    monkeypatch.setattr(bank, "FRESH_SEEDS", (503,))
    monkeypatch.setattr(campaign, "DIRECTORY", tmp_path)
    frozen = {"freeze_sha256": "fixture", "python_version": sys.version.split()[0]}
    record = {"schema": "mira-genesis-v35-complete-epoch-v1", "status": "COMPLETED", "epoch": 0,
        "freeze_sha256": "fixture", "previous_receipt_sha256": None, "tasks_sha256": digest({"503": tasks}),
        "policy_sha256": programs.PARENT_SHA256, "python_version": frozen["python_version"],
        "track": "B", "scientific_external_model_calls": 0, "streams": {"503": {}}}
    histories = {"503": {arm: [] for arm in engine.ARMS}}
    where = campaign.directory(0)
    for arm in engine.ARMS:
        path = where / f"{arm}.jsonl"
        engine.run_stream(tasks, arm, path, "fixture", None, [], stop_after=3)
        checkpoint = Archive(path, engine.binding(tasks, arm, "fixture", None, [])).read()[-1]["sha256"]
        rows, head = engine.run_stream(tasks, arm, path, "fixture", None, [])
        record["streams"]["503"][arm] = {"episodes": rows, "journal": path.read_text(), "head_sha256": head,
                                        "checkpoint_position": 3, "checkpoint_head_sha256": checkpoint}
    return record, frozen, histories


def test_complete_epoch_replay_and_no_false_l9_or_l10(public_tasks, tmp_path, monkeypatch):
    record, frozen, histories = epoch_fixture(tmp_path, public_tasks, monkeypatch)
    verdict = campaign.adjudicate(record, frozen, histories, None)
    assert verdict["l9_open_ended_passed"] is verdict["l10_independent_passed"] is False
    changed = copy.deepcopy(record)
    del changed["streams"]["503"]["cold"]
    with pytest.raises(ValueError, match="control"):
        campaign.adjudicate(changed, frozen, histories, None, replay=False)
    with pytest.raises(ValueError, match="epoch"):
        campaign.adjudicate(record, frozen, histories, "substituted", replay=False)
    changed = copy.deepcopy(record)
    changed["streams"]["503"]["adaptive"]["checkpoint_head_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="checkpoint"):
        campaign.adjudicate(changed, frozen, histories, None, replay=False)


def test_epoch_completion_binds_previous_receipt_and_exact_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "DIRECTORY", tmp_path)
    where = campaign.directory(0)
    record = {"epoch": 0, "freeze_sha256": "fixture", "previous_receipt_sha256": None, "tasks_sha256": "tasks", "status": "COMPLETED"}
    identity = {key: record[key] for key in ("epoch", "freeze_sha256", "previous_receipt_sha256", "tasks_sha256")}
    reservation = {"schema": "mira-genesis-v35-epoch-reservation-v1", "status": "RESERVED", **identity}
    verdict = {"l9_open_ended_passed": False, "l10_independent_passed": False}
    storage.publish_json(where / campaign.NAMES[0], reservation)
    encoded = canonical(record) + b"\n"
    raw = gzip.compress(encoded, mtime=0)
    storage.publish_once(where / campaign.NAMES[1], raw)
    storage.publish_json(where / campaign.NAMES[2], verdict)
    receipt = {"schema": "mira-genesis-v35-epoch-completion-v1", "status": "COMPLETED", **identity,
        "raw_sha256": digest_bytes(raw), "uncompressed_sha256": digest_bytes(encoded), "record_sha256": digest(record),
        "verdict_sha256": digest(verdict), "reservation_sha256": digest_bytes(storage.read_regular(where / campaign.NAMES[0]))}
    storage.publish_json(where / campaign.NAMES[3], receipt)
    assert campaign.read_complete(0) == (record, verdict, receipt)
    monkeypatch.setattr(campaign, "ROOT", tmp_path)
    monkeypatch.setattr(freeze, "git", lambda *args: b"substituted checkout")
    with pytest.raises(ValueError, match="committed"):
        campaign.read_complete(0, committed=True)
    path = where / campaign.NAMES[3]
    altered = copy.deepcopy(receipt)
    altered["previous_receipt_sha256"] = "different"
    path.write_bytes(canonical(altered) + b"\n")
    with pytest.raises(ValueError, match="continuation"):
        campaign.read_complete(0)



def test_no_freeze_never_passes_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "missing")
    assert campaign.check()["l9_open_ended_passed"] is False
    with pytest.raises(ValueError):
        campaign.check(require_prefix=True)
