"""Scientific-boundary, recovery and external-trust tests on development fixtures."""
import copy
import json
import subprocess
from pathlib import Path

import pytest

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v31 import bank, campaign, engine, freeze, independent, programs
from experiment.rsi_v31.archive import Archive


@pytest.fixture
def tasks():
    return bank.stream(bank.DEV_SEEDS[0])[:8]


def test_actual_source_and_semantic_diversity():
    source = programs.render({"width": 4, "rotation": 1, "mask": 3})
    assert source.startswith(programs.parent())
    assert not programs.GUARD.guard_source(source, [])
    genomes = list(programs.neighbors(programs.identity(4)))
    signatures = {tuple(programs.transform(row, value) for value in range(16)) for row in genomes}
    assert len(signatures) == len(genomes) == 6
    assert len({programs.descriptor(row)["source_sha256"] for row in genomes}) == 6


@pytest.mark.parametrize("field,value", [("width", True), ("width", 65), ("rotation", -1), ("mask", 8)])
def test_genome_authority_limit(field, value):
    row = {"width": 3, "rotation": 0, "mask": 0, field: value}
    with pytest.raises(ValueError):
        programs.render(row)


def test_real_isolated_transducer():
    row = {"width": 5, "rotation": 3, "mask": 17}
    assert engine.execute(row, list(range(32))) == engine.execute(row, list(range(32)), isolated=False)


def test_fresh_and_development_bank_predeclared_disjoint():
    fresh = [task for seed in bank.FRESH_SEEDS for task in bank.stream(seed)]
    dev = [task for seed in bank.DEV_SEEDS for task in bank.stream(seed)]
    assert len(fresh) == 144 and len({task["task_id"] for task in fresh + dev}) == 240
    assert not {digest(task) for task in fresh} & {digest(task) for task in dev}
    for seed in bank.FRESH_SEEDS:
        assert bank.validate_stream(bank.stream(seed))


def test_duplicate_or_reordered_stream_refused(tasks):
    with pytest.raises(ValueError):
        bank.validate_stream(tasks + tasks[:1])
    changed = copy.deepcopy(tasks)
    changed[0]["window"] = 1
    with pytest.raises(ValueError):
        bank.validate_stream(changed)


def test_policy_does_not_receive_hidden_task_or_past_quality(tasks, monkeypatch):
    import experiment.rsi_v27.engine as old
    original = old.call
    calls = []
    def observe(path, payload):
        calls.append(payload)
        text = json.dumps(payload)
        assert tasks[0]["task_id"] not in text
        assert not any(key in text for key in ('"target"', '"inputs"', '"expected"', '"task_family"'))
        return original(path, payload)
    monkeypatch.setattr(old, "call", observe)
    row = engine.episode(tasks[0], 0, {}, "archive")
    assert calls and row["charged_evaluations"] == row["search"]["represented_requests"] + 1


def test_archive_recovery_matches_uninterrupted_bytes(tasks, tmp_path):
    a, b = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    rows, head = engine.run_stream(tasks, "archive", a, "fixture", isolated=False)
    engine.run_stream(tasks, "archive", b, "fixture", isolated=False, stop_after=3)
    restored, restored_head = engine.run_stream(tasks, "archive", b, "fixture", isolated=False)
    assert rows == restored and head == restored_head and a.read_bytes() == b.read_bytes()
    assert engine.verify_stream(tasks, "archive", rows, isolated=False)
    assert all(row["charged_evaluations"] <= 13 for row in rows)
    assert any(row["rediscovered"] for row in rows)


def test_isolated_receipt_replay_and_tampering(tasks):
    rows = []
    for index, task in enumerate(tasks[:2]):
        rows.append(engine.episode(task, index, engine.history_from(rows), "archive"))
    assert engine.verify_stream(tasks[:2], "archive", rows)
    bad = copy.deepcopy(rows)
    bad[0]["programs"][0]["evaluation"]["quality_milli"] = -1
    with pytest.raises(ValueError, match="receipt"):
        engine.verify_stream(tasks[:2], "archive", bad)
    with pytest.raises(ValueError, match="Omitted"):
        engine.verify_stream(tasks, "archive", rows)


@pytest.mark.parametrize("arm", engine.ARMS)
def test_equal_root_probe_and_request_caps(tasks, arm):
    row = engine.episode(tasks[0], 0, {}, arm, isolated=False)
    assert row["charged_evaluations"] == row["search"]["represented_requests"] + 1
    assert row["search"]["caps"] == engine.CAPS.__dict__


def test_retention_changes_candidates_without_changing_current_evaluator(tasks):
    rows = [engine.episode(tasks[0], 0, {}, "archive", isolated=False)]
    history = engine.history_from(rows)
    hosts = {arm: engine.Host(tasks[1], history, arm, isolated=False) for arm in engine.ARMS}
    assert len(hosts["archive"].history) > len(hosts["greedy"].history) == 1
    assert not hosts["cold"].history
    assert len({digest(host.initial) for host in hosts.values()}) == 1


def test_stale_writer_torn_tail_tamper_and_truncation_refused(tmp_path):
    path = tmp_path / "journal.jsonl"
    archive = Archive(path, {"fixture": True}, create=True)
    head = archive.read()[-1]["sha256"]
    archive.append("start", {"position": 0}, expected_head=head)
    with pytest.raises(ValueError, match="stale"):
        archive.append("start", {}, expected_head=head)
    with pytest.raises(ValueError, match="externally"):
        archive.read(expected_head=head)
    raw = path.read_bytes()
    path.write_bytes(raw[:-1])
    with pytest.raises(ValueError, match="Torn"):
        archive.read()
    path.write_bytes(raw.replace(b'"position":0', b'"position":1'))
    with pytest.raises(ValueError, match="Altered"):
        archive.read()


def test_symlink_and_existing_create_refused(tmp_path):
    path = tmp_path / "journal"
    Archive(path, {}, create=True)
    with pytest.raises(FileExistsError):
        Archive(path, {}, create=True)
    alias = tmp_path / "alias"
    alias.symlink_to(path)
    with pytest.raises(OSError):
        Archive(alias, {})


def test_pending_task_reservation_cannot_retry(tasks, tmp_path):
    path = tmp_path / "journal"
    archive = Archive(path, engine.binding(tasks, "archive", "fixture"), create=True)
    archive.append("start", {"position": 0, "task_sha256": digest(tasks[0]), "reserved_evaluations": 13})
    before = path.read_bytes()
    with pytest.raises(ValueError, match="Unfinished"):
        engine.run_stream(tasks, "archive", path, "fixture", isolated=False)
    assert path.read_bytes() == before


def test_cross_arm_bank_or_freeze_checkpoint_rejected(tasks, tmp_path):
    path = tmp_path / "journal"
    engine.run_stream(tasks, "archive", path, "fixture", isolated=False, stop_after=1)
    for arm, frozen in (("cold", "fixture"), ("archive", "different")):
        with pytest.raises(ValueError, match="binding"):
            engine.run_stream(tasks, arm, path, frozen, isolated=False)


def test_lossless_raw_archive_refuses_changed_negatives(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, "ATTEMPT", tmp_path / "index.json")
    monkeypatch.setattr(campaign, "RAW", tmp_path / "raw.json.gz")
    value = {"status": "COMPLETED", "freeze_sha256": "fixture", "canonical_attempts": 1, "negatives": [0, 0, 1]}
    campaign.preserve(value)
    assert campaign.read_attempt() == value
    campaign.RAW.write_bytes(b"altered")
    with pytest.raises(Exception):
        campaign.read_attempt()


def test_unfrozen_claims_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "absent.json")
    assert campaign.check()["l9_open_ended_passed"] is False
    with pytest.raises(ValueError, match="Missing"):
        campaign.check(require_result=True)
    with pytest.raises(ValueError, match="Altered"):
        freeze.verify({})
    assert independent.readiness()["l10_independent_passed"] is False


def test_blank_templates_do_not_assert_external_work():
    for path in freeze.HERE.glob("*.template.json"):
        row = json.loads(path.read_text())
        assert row["identity"] is None and row["project_pin_sha256"] is None
        assert not row.get("independent_of_project") and not row.get("independently_authored")


def test_private_artifacts_cannot_be_written_to_public_repo():
    with pytest.raises(ValueError, match="outside"):
        independent.outside_repo(freeze.HERE / "private.json")


def test_unsigned_owner_or_untrusted_statement_rejected(tmp_path):
    path = tmp_path / "statement.json"
    path.write_text("{}")
    for identity in ("mjodheim", "Anthony Mets", "external"):
        with pytest.raises(ValueError):
            independent.signed_statement(path, tmp_path / "missing-trust", identity)


def test_real_external_signature_and_mutation_refusal(tmp_path):
    key = tmp_path / "key"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
    trust = tmp_path / "allowed-signers"
    trust.write_text('external-test namespaces="' + independent.NAMESPACE + '" ' + key.with_suffix(".pub").read_text())
    message = tmp_path / "statement.json"
    message.write_text('{"fixture":true}\n')
    subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n", independent.NAMESPACE, str(message)],
                   check=True, capture_output=True)
    assert independent.signed_statement(message, trust, "external-test") == {"fixture": True}
    message.write_text('{"fixture":false}\n')
    with pytest.raises(ValueError, match="signature"):
        independent.signed_statement(message, trust, "external-test")


def test_task_commitment_hash_count_and_authorship_required(tasks):
    raw = json.dumps(tasks).encode()
    project = {"project_pin_sha256": "fixture"}
    row = {"schema": "mira-genesis-l10-bank-commitment-v1", "project_pin_sha256": "fixture",
           "bank_bytes_sha256": digest_bytes(raw), "task_count": len(tasks), "identity": "outside",
           "independently_authored": True, "committed_before_first_candidate_execution": True,
           "custody": "EXTERNAL_PRIVATE", "domain_description": "fixture only", "conflicts_disclosed": "none"}
    assert independent.validate_bank_statement(row, project, raw, tasks, "outside")
    for field, value in (("task_count", len(tasks) - 1), ("independently_authored", False),
                         ("committed_before_first_candidate_execution", False), ("bank_bytes_sha256", "wrong")):
        with pytest.raises(ValueError):
            independent.validate_bank_statement({**row, field: value}, project, raw, tasks, "outside")


def test_internal_consistency_cannot_pass_l10():
    project = {"project_pin_sha256": "fixture"}
    report = {"status": "COMPLETED", "project_pin_sha256": "fixture", "policy_sha256": programs.PARENT_SHA256,
              "l9_open_ended_passed": False, "l10_independent_passed": False}
    identities = {role: "external-" + role for role in independent.ROLES}
    statements = {role: {"schema": "mira-genesis-l10-" + role + "-attestation-v1", "project_pin_sha256": "fixture",
                        "report_sha256": digest(report), "identity": identities[role],
                        "independent_of_project": True, "conflicts_disclosed": "fixture only"}
                  for role in ("reproducer", "auditor")}
    statements["reproducer"]["reran_unchanged_lineage_and_private_bank"] = True
    statements["auditor"]["checks"] = {key: True for key in independent.AUDIT_CHECKS}
    result = independent.validate_attestations(project, report, report, statements, identities)
    assert result["signed_packet_consistent"] and result["l10_independent_passed"] is False
    bad = copy.deepcopy(statements)
    bad["auditor"]["checks"]["claim_scope_and_open_endedness"] = False
    with pytest.raises(ValueError, match="audit"):
        independent.validate_attestations(project, report, report, bad, identities)
    with pytest.raises(ValueError, match="roles"):
        independent.validate_attestations(project, report, report, statements, dict.fromkeys(independent.ROLES, "same"))
