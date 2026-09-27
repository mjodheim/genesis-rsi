"""Regressions for the prospective V24 freeze builder.

These tests do not evaluate the complete semantic candidate universe. The
expensive complete-universe bridge validation is intentionally performed once
by build_l5_freeze.py when the scientific freeze is created.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V24 = ROOT / "experiment" / "rsi_v24"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = _load("test_v24_freeze_builder", V24 / "build_l5_freeze.py")


def test_v24_freeze_builder_recognizes_preserved_v23_negative_and_fresh_holdout():
    freeze, negative = builder.verify_v23_predecessor()
    assert freeze["freeze_payload_sha256"] == builder.EXPECTED_V23_FREEZE_PAYLOAD_SHA256
    assert negative["fresh_holdout_consumed"] is False
    assert negative["eligible_for_fresh_holdout"] is False
    assert negative["l5_positive"] is False


def test_v24_freeze_builder_binds_final_preregistration_and_v23_results():
    rels = {
        str(path.relative_to(ROOT))
        for path in builder.required_files()
    }
    assert "experiment/rsi_v24/V24_L5_PREREGISTRATION.md" in rels
    assert "experiment/rsi_v24/l5_meta_search.py" in rels
    assert "experiment/rsi_v24/semantic_quality_bridge.py" in rels
    assert "experiment/rsi_v24/build_l5_freeze.py" in rels
    assert "experiment/rsi_v23/V23_FREEZE.json" in rels
    assert ".github/workflows/v24-l5-freeze-build.yml" in rels
    assert (
        "results/rsi-v23/l5-20260924/"
        "V23_L5_PRE_HOLDOUT_ADJUDICATION.json"
    ) in rels


def test_v24_freeze_builder_forbids_result_contamination_before_freeze():
    rels = {str(path.relative_to(ROOT)) for path in builder.FORBIDDEN_PRE_FREEZE}
    assert "results/rsi-v24" in rels
    assert "experiment/rsi_v24/V24_META_SEARCH_RESULT.json" in rels
    assert "experiment/rsi_v24/G3_SELECTED.py" in rels
