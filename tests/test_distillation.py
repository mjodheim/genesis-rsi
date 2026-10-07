from __future__ import annotations

import json
from pathlib import Path

import pytest

from genesis.learning import distillation


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATHS = [
    ROOT / "experiment/autonomy_a6b/task_001_fallback_result.json",
    ROOT / "experiment/autonomy_a6b/task_004_fallback_result.json",
    ROOT / "experiment/autonomy_a6b/task_006_fallback_result.json",
    ROOT / "experiment/autonomy_a6b/task_011_fallback_result.json",
]


def specialist() -> dict:
    return distillation.distill_from_paths(
        SOURCE_PATHS,
        specialist_id="g8-a6b-repair-specialist",
    )


def test_distills_only_validated_expensive_sources() -> None:
    item = specialist()

    assert item["template_count"] == 4
    assert item["source_external_model_calls"] == 4
    assert item["runtime_external_model_calls"] == 0
    assert item["host_issue_specific_recipe"] is False
    assert {row["task_id"] for row in item["distilled_from"]} == {1, 4, 6, 11}
    assert item["source_cost_usd"] > 0
    assert distillation.validate_specialist(item) == item


def test_specialist_reuses_python_inclusive_range_without_model_call(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "math_ops.py"
    target.write_text(
        "def product_to(limit):\n"
        "    out = 1\n"
        "    for value in range(1, limit):\n"
        "        out *= value\n"
        "    return out\n",
        encoding="utf-8",
    )

    result = distillation.generate(root, specialist(), max_candidates=16)

    assert result["external_model_calls"] == 0
    assert result["candidate_count"] >= 1
    assert any(
        "range(1, limit + 1)" in c["mutations"][0]["content_utf8"]
        for c in result["candidates"]
    )


def test_specialist_reuses_rust_retry_range_without_model_call(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "retry.rs"
    target.write_text(
        "const MAX_RETRIES: usize = 5;\n"
        "fn run() {\n"
        "    for attempt in 1..MAX_RETRIES {\n"
        "        println!(\"{}\", attempt);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    result = distillation.generate(root, specialist(), max_candidates=16)

    assert any(
        "for attempt in 0..MAX_RETRIES {" in c["mutations"][0]["content_utf8"]
        for c in result["candidates"]
    )


def test_specialist_reuses_typescript_zero_index_without_model_call(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    target = root / "view.ts"
    target.write_text(
        "const firstStage = STAGES[1];\n"
        "export { firstStage };\n",
        encoding="utf-8",
    )

    result = distillation.generate(root, specialist(), max_candidates=16)

    assert any(
        "const firstStage = STAGES[0];" in c["mutations"][0]["content_utf8"]
        for c in result["candidates"]
    )


def test_distillation_rejects_tampered_source_report() -> None:
    raw = json.loads(SOURCE_PATHS[0].read_text(encoding="utf-8"))
    raw["fallback_passed"] = False

    with pytest.raises(distillation.DistillationError, match="digest"):
        distillation.validate_source_record(raw)


def test_distillation_rejects_failing_but_rehashed_source_report() -> None:
    raw = json.loads(SOURCE_PATHS[0].read_text(encoding="utf-8"))
    raw["fallback_passed"] = False
    raw.pop("report_digest")
    from genesis.trust_root import digest_of

    raw["report_digest"] = digest_of(raw)

    with pytest.raises(distillation.DistillationError, match="passing"):
        distillation.validate_source_record(raw)
