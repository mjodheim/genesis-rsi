"""V29 provenance and oracle-boundary tests; no candidate-policy bank transfer."""
import copy
import itertools
import json

import pytest

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v29 import campaign, freeze, native_bank, native_worker


def test_four_material_domains_and_closed_native_source_grammar():
    assert native_bank.DOMAINS == ("relational-sql", "regular-expressions", "structured-json", "binary-compression")
    for domain in native_bank.DOMAINS:
        sources = [native_bank.render(domain, c) for c in itertools.product(range(4), repeat=3)]
        assert len({digest_bytes(s.encode()) for s in sources}) == 64
        assert all(compile(s, "<native-proposal>", "exec") for s in sources)
    with pytest.raises(ValueError):
        native_bank.render("unknown", (0, 0, 0))
    with pytest.raises(ValueError):
        native_bank.render(native_bank.DOMAINS[0], (True, 0, 0))


def test_serialized_bank_is_fixed_and_operation_coverage_is_balanced():
    assert digest(native_bank.TASKS) == digest(json.loads((native_bank.HERE / "NATIVE_TASKS.json").read_text()))
    for task in native_bank.TASKS:
        assert [sum(c["operation"] == op for c in task["cases"]) for op in ("a", "b", "c")] == [8, 6, 6]
        assert len({c["case_id"] for c in task["cases"]}) == 20


def test_preparation_only_executed_reference_and_seed_and_has_consistent_receipts():
    native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
    assert not native["controller_executed"] and native["population_sha256"] == digest(native_bank.TASKS)
    for task, prepared in zip(native_bank.TASKS, native["tasks"]):
        campaign.verify_receipt(prepared["reference"], task, (0, 0, 0))
        campaign.verify_receipt(prepared["seeded"], task, (1, 1, 1))
        assert prepared["reference"]["quality_milli"] == 1000
        assert prepared["seeded"]["quality_milli"] < 1000


def test_forged_or_malformed_native_receipts_are_rejected():
    native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
    receipt = copy.deepcopy(native["tasks"][0]["seeded"])
    receipt["quality_milli"] = 1000
    receipt["receipt_sha256"] = digest({k: v for k, v in receipt.items() if k != "receipt_sha256"})
    with pytest.raises(ValueError, match="receipt"):
        campaign.verify_receipt(receipt, native_bank.TASKS[0], (1, 1, 1))
    receipt["observed"][0]["ok"] = "true"
    with pytest.raises(ValueError, match="output"):
        campaign.verify_receipt(receipt, native_bank.TASKS[0], (1, 1, 1))


def test_candidate_inputs_do_not_contain_oracle_answers(monkeypatch):
    native = json.loads((native_bank.HERE / "NATIVE_CALIBRATION.json").read_text())
    observed = native["tasks"][0]["reference"]["observed"]
    class Completed:
        returncode = 0
        stdout = json.dumps(observed)
    def execute(*args, **kwargs):
        payload = json.loads(kwargs["input"])
        assert all(set(case) == {"operation", "data"} for case in payload["operations"])
        assert "expected" not in kwargs["input"]
        return Completed()
    monkeypatch.setattr(native_bank.subprocess, "run", execute)
    assert native_bank.evaluate(native_bank.TASKS[0], (0, 0, 0))["quality_milli"] == 1000
    assert callable(native_worker.main)


def test_whole_terminal_source_is_unchanged_and_all_controls_are_declared():
    policies = campaign.policies()
    assert set(policies) == {"g3", "g4", "g5", "g6", "ablation_persistence", "ablation_ordering", "ablation_scheduling"}
    assert digest_bytes(policies["g6"].encode()) == "154745c2f306c4e7ece2fd5bf4ce9fa8916e27df741711ec343d26ac653ca172"


def test_incomplete_or_unfrozen_evidence_cannot_claim_l7(tmp_path, monkeypatch):
    monkeypatch.setattr(freeze, "PATH", tmp_path / "freeze.json")
    monkeypatch.setattr(campaign, "ATTEMPT", tmp_path / "attempt.json")
    assert campaign.check()["v29_l7_positive"] is False
    with pytest.raises(ValueError):
        campaign.check(require_result=True)
    with pytest.raises(ValueError):
        freeze.verify({"schema": "mira-genesis-v29-full-freeze-v1", "freeze_sha256": "0" * 64})


def test_exclusive_marker_refuses_a_native_bank_retry(tmp_path, monkeypatch):
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps({"runtime_versions": native_bank.runtime_versions(), "freeze_sha256": "fixture"}))
    marker = tmp_path / "attempt.json"
    marker.write_text("consumed")
    monkeypatch.setattr(freeze, "PATH", path)
    monkeypatch.setattr(freeze, "verify", lambda value: True)
    monkeypatch.setattr(campaign, "ATTEMPT", marker)
    with pytest.raises(FileExistsError):
        campaign.run()
    assert marker.read_text() == "consumed"
