from __future__ import annotations

import importlib.util
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


def test_v25_builder_never_infers_missing_v24_evidence():
    module = load_builder()
    if not module.V24_RESULT_ROOT.is_dir():
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
    }
    assert {path.name for path in module.APPARATUS} == expected
