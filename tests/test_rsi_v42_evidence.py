"""The publication gate requires complete evidence even after wholesale deletion."""
from experiment.rsi_v25.commitments import canonical

import pytest

from scripts import check_rsi_v42_evidence as gate


@pytest.fixture
def report(tmp_path, monkeypatch):
    value = {"epochs": 8, "measured_continuing_archive_positive": False,
             "l9_open_ended_passed": False, "l10_independent_passed": False,
             "finite_prefix_cannot_establish_open_endedness": True}
    monkeypatch.setattr(gate.campaign, "DIRECTORY", tmp_path)
    def replay(*, require_prefix, replay):
        assert require_prefix is True
        assert replay is True
        return value
    monkeypatch.setattr(gate.campaign, "check", replay)
    (tmp_path / "PREFIX_REPORT.json").write_bytes(canonical(value) + b"\n")
    return value, tmp_path


def test_preserved_negative_is_valid_evidence(report):
    assert gate.check()["measured_continuing_archive_positive"] is False


def test_missing_report_is_rejected(report):
    _, path = report
    (path / "PREFIX_REPORT.json").unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        gate.check()


def test_forged_positive_report_is_rejected(report):
    value, path = report
    (path / "PREFIX_REPORT.json").write_bytes(canonical({**value, "measured_continuing_archive_positive": True}) + b"\n")
    with pytest.raises(ValueError, match="differs"):
        gate.check()


def test_deleted_campaign_cannot_use_optional_check(monkeypatch, tmp_path):
    monkeypatch.setattr(gate.campaign, "DIRECTORY", tmp_path)
    monkeypatch.setattr(gate.campaign.freeze, "PATH", tmp_path / "absent-freeze.json")
    with pytest.raises(ValueError, match="Missing"):
        gate.check()


@pytest.mark.parametrize("field", ["l9_open_ended_passed", "l10_independent_passed"])
def test_finite_result_cannot_promote_level(report, field):
    value, path = report
    value[field] = True
    (path / "PREFIX_REPORT.json").write_bytes(canonical(value) + b"\n")
    with pytest.raises(ValueError, match="finite"):
        gate.check()
