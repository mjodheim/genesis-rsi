"""Provenance du lanceur CIRCUIT2 : hors réseau, fixtures synthétiques (plan factice, coûts 100)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

import freeze_circuit2_plan as freeze
import run_circuit2_campaign as campaign
import seal_circuit2_launcher as sealing

COMMIT = "a" * 40
FORBIDDEN = ("gain", "yield", "rendement", "succ")
EXPECTED_KEYS = {"launcher_path", "launcher_sha256", "verifier_sha256", "seal_sha256", "seal_digest", "plan_digest", "git_head"}


@pytest.fixture(scope="module")
def sealed():
    """Fixture synthétique : plan factice aux coûts de référence 100."""
    return freeze.build_plan(measure=lambda: {str(s): 100 for s in freeze.SEEDS}, machinery_commit=COMMIT)


@pytest.fixture(autouse=True)
def canonical(tmp_path, sealed, monkeypatch):
    path = tmp_path / "CANONICAL.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    monkeypatch.setattr(campaign, "CANONICAL_PLAN_PATH", path)
    return path


@pytest.fixture(autouse=True)
def launcher_seal(tmp_path, sealed, monkeypatch):
    """Fixture synthétique : sceau valide écrit dans tmp_path pour le vrai lanceur et le plan factice."""
    path = tmp_path / "LAUNCHER_SEAL.json"
    path.write_text(json.dumps(sealing.build_seal(sealed["digest"])), encoding="utf-8")
    monkeypatch.setattr(campaign, "SEAL_PATH", path)
    return path


@pytest.fixture
def calls(monkeypatch):
    """Fixture synthétique : new_run factice, aucune génération réelle ; enregistre les appels."""
    recorded = []

    class _FakeRun:
        def step(self):
            return {"exhausted": False, "digest": "d", "spent": 0, "transmission": {"digest": "d"}}

    def new_run(arm, seed, learn, limit, budget):
        recorded.append((arm, seed))
        return _FakeRun()

    monkeypatch.setattr(campaign, "new_run", new_run)
    return recorded


@pytest.fixture
def plan_path(tmp_path, sealed):
    path = tmp_path / "PLAN.json"
    path.write_text(json.dumps(sealed), encoding="utf-8")
    return path


def _invalid_seal(path, sealed):
    """Fixture synthétique : sceau cohérent en soi mais lié à un autre plan."""
    body = {k: v for k, v in sealing.build_seal(sealed["digest"]).items() if k != "digest"}
    body["plan_digest"] = "f" * 64
    path.write_text(json.dumps({**body, "digest": sealing.digest_of(body)}), encoding="utf-8")


def test_provenance_carries_the_expected_hashes_and_digests(sealed, launcher_seal, calls):
    provenance = campaign.run_campaign(sealed, seeds=[0], generations=1)["launcher_provenance"]
    seal = json.loads(launcher_seal.read_text(encoding="utf-8"))
    assert set(provenance) == EXPECTED_KEYS
    assert provenance["launcher_path"] == campaign.LAUNCHER_REL == "scripts/run_circuit2_campaign.py"
    assert provenance["launcher_sha256"] == sealing.file_sha256(campaign.LAUNCHER_FILE) == seal["launcher_sha256"]
    assert provenance["verifier_sha256"] == sealing.file_sha256(Path(sealing.__file__)) == seal["verifier_sha256"]
    assert provenance["seal_sha256"] == hashlib.sha256(launcher_seal.read_bytes()).hexdigest()
    assert provenance["seal_digest"] == seal["digest"]
    assert provenance["plan_digest"] == sealed["digest"]
    assert calls


def test_git_head_is_a_string(sealed, calls):
    head = campaign.run_campaign(sealed, seeds=[0], generations=1)["launcher_provenance"]["git_head"]
    assert isinstance(head, str) and head


def test_git_head_is_unavailable_when_git_fails(sealed, calls, monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("git absent")

    monkeypatch.setattr(campaign.subprocess, "run", broken)
    assert campaign.run_campaign(sealed, seeds=[0], generations=1)["launcher_provenance"]["git_head"] == "unavailable"


def test_main_records_the_exact_command(plan_path, tmp_path, sealed, calls):
    out = tmp_path / "OUT.json"
    argv = ["--plan", str(plan_path), "--seeds", "0", "--generations", "1", "--out", str(out)]
    assert campaign.main(argv) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["command"] == argv
    assert written["launcher_provenance"]["plan_digest"] == sealed["digest"]


def test_main_without_argv_records_sys_argv(plan_path, tmp_path, calls, monkeypatch):
    out = tmp_path / "OUT_SYS.json"
    args = ["--plan", str(plan_path), "--seeds", "0", "--generations", "1", "--out", str(out)]
    monkeypatch.setattr(sys, "argv", ["run_circuit2_campaign.py", *args])
    assert campaign.main() == 0
    assert json.loads(out.read_text(encoding="utf-8"))["command"] == args


def test_no_provenance_with_an_invalid_seal(sealed, launcher_seal, calls, monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("la provenance ne doit pas être calculée avec un sceau invalide")

    monkeypatch.setattr(campaign, "_launcher_provenance", refused)
    _invalid_seal(launcher_seal, sealed)
    with pytest.raises(campaign.PlanError):
        campaign.run_campaign(sealed, seeds=[0], generations=1)
    assert calls == []


def test_main_with_an_invalid_seal_writes_nothing(plan_path, tmp_path, sealed, launcher_seal, calls):
    _invalid_seal(launcher_seal, sealed)
    out = tmp_path / "OUT_INVALID.json"
    assert campaign.main(["--plan", str(plan_path), "--seeds", "0", "--generations", "1", "--out", str(out)]) == 2
    assert not out.exists()
    assert calls == []


def test_new_keys_contain_no_forbidden_word(sealed, calls):
    result = campaign.run_campaign(sealed, seeds=[0], generations=1)
    keys = [k.lower() for k in [*result["launcher_provenance"], "launcher_provenance", "command"]]
    assert keys and not [k for k in keys if any(word in k for word in FORBIDDEN)]
