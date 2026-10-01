from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "experiment" / "rsi_v25" / "build_l5_freeze.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("v25_freeze_builder", BUILDER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v25_builder_never_infers_missing_v24_evidence(tmp_path, monkeypatch):
    module = load_builder()
    monkeypatch.setattr(module, "V24_RESULT_ROOT", tmp_path / "missing")
    with pytest.raises(SystemExit, match="V24 final result directory is not committed"):
        module.preserved_v24_files()


def test_v25_forbids_result_artifacts_before_freeze():
    module = load_builder()
    forbidden = {str(path.relative_to(ROOT)) for path in module.FORBIDDEN_PRE_FREEZE}
    assert "results/rsi-v25" in forbidden
    assert "experiment/rsi_v25/V25_L5_ADJUDICATION.json" in forbidden
    assert "experiment/rsi_v25/V25_HOLDOUT_RESULT.json" in forbidden


def test_v25_freeze_hashes_only_explicit_apparatus_and_preserved_evidence():
    module = load_builder()
    expected = {
        "V25_L5_PREREGISTRATION.md",
        "V25_TRANSFER_DIAGNOSIS_AND_PROSPECTIVE_PLAN.md",
        "controls.py",
        "exploration_grammar.py",
        "meta_search.py",
        "build_l5_freeze.py",
        "V24_PRESERVED_EVIDENCE_MANIFEST.json",
    }
    assert {path.name for path in module.APPARATUS} == expected


@pytest.fixture
def committed_apparatus(tmp_path, monkeypatch):
    """Copy the real preserved evidence into a disposable, committed repository."""
    module = load_builder()
    original_root = module.ROOT
    for source in (*module.APPARATUS, *module.preserved_v24_files()):
        target = tmp_path / source.relative_to(original_root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    module.APPARATUS = tuple(tmp_path / path.relative_to(original_root) for path in module.APPARATUS)
    module.FORBIDDEN_PRE_FREEZE = tuple(
        tmp_path / path.relative_to(original_root) for path in module.FORBIDDEN_PRE_FREEZE
    )
    module.ROOT = tmp_path
    module.V25 = tmp_path / "experiment/rsi_v25"
    module.V24_RESULT_ROOT = tmp_path / "results/rsi-v24"
    module.V24_MANIFEST = module.V25 / "V24_PRESERVED_EVIDENCE_MANIFEST.json"
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.test",
                    "commit", "-q", "-m", "Test fixture"], cwd=tmp_path, check=True)
    return module


def test_preserved_v24_evidence_is_complete_and_hash_bound():
    assert len(load_builder().preserved_v24_files()) == 13


def test_changed_preserved_evidence_is_rejected(committed_apparatus):
    module = committed_apparatus
    path = module.preserved_v24_files()[0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SystemExit, match="preserved evidence missing or changed"):
        module.preserved_v24_files()


def test_final_utility_is_recomputed_even_if_a_task_hash_is_rebound(committed_apparatus):
    module = committed_apparatus
    manifest = json.loads(module.V24_MANIFEST.read_text())
    path = module.ROOT / manifest["evidence_directory"] / "g3-brewtrack-brewmath-precision.json"
    row = json.loads(path.read_text())
    row["best_quality_milli"] = 750
    path.write_text(json.dumps(row))
    manifest["files"][path.name] = module.sha256(path)
    module.V24_MANIFEST.write_text(json.dumps(manifest))
    with pytest.raises(SystemExit, match="final utility does not match"):
        module.preserved_v24_files()


def test_head_identity_cannot_cover_untracked_or_modified_inputs(committed_apparatus):
    module = committed_apparatus
    commit = module.git_head()
    path = module.APPARATUS[0]
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(SystemExit, match="differs from committed bytes"):
        module.require_committed_bytes([path], commit)
    untracked = module.ROOT / "not_committed.json"
    untracked.write_text("{}")
    with pytest.raises(SystemExit, match="input is not committed"):
        module.require_committed_bytes([untracked], commit)


def test_committed_development_apparatus_does_not_authorize_final_holdout(committed_apparatus):
    module = committed_apparatus
    payload = module.build(module.git_head())
    assert payload["status"] == "DEVELOPMENT_APPARATUS_COMMITTED_HOLDOUT_NOT_AUTHORIZED"
    assert payload["authorizes_fresh_holdout"] is False
    assert payload["holdout_consumed"] is False
    assert payload["remaining_requirements"]
    assert payload["v24_evidence_file_count"] == 13
