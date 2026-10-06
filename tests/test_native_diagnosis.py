from __future__ import annotations

from pathlib import Path
import sys

import pytest

from genesis import native_diagnosis


def _python_project(root: Path, source: str) -> None:
    (root / "pyproject.toml").write_text(
        "[project]\nname='fixture'\nversion='0.0.0'\n",
        encoding="utf-8",
    )
    package = root / "fixture"
    package.mkdir()
    (package / "__init__.py").write_text(source, encoding="utf-8")


def test_plan_uses_native_python_tool_without_model(tmp_path: Path) -> None:
    _python_project(tmp_path, "VALUE = 1\n")

    probes = native_diagnosis.plan(tmp_path)

    assert probes
    assert probes[0].language == "python"
    assert probes[0].argv[:3] == ("python3", "-m", "compileall")


def test_clean_python_project_passes_bounded_diagnosis(tmp_path: Path) -> None:
    _python_project(tmp_path, "VALUE = 1\n")

    report = native_diagnosis.run(tmp_path, timeout_seconds=10)

    assert report["schema"] == native_diagnosis.DIAGNOSIS_REPORT_SCHEMA
    assert report["external_model_calls"] == 0
    assert report["retry_count"] == 0
    assert report["source_tree_execution"] is False
    assert report["claim"] == "A1_NATIVE_DIAGNOSIS_ONLY"
    assert report["failure_observed"] is False
    assert report["executed_probe_count"] == 1
    assert report["results"][0]["diagnostic_classes"] == ["clean"]
    assert len(report["report_digest"]) == 64


def test_python_syntax_failure_is_observed_and_classified(tmp_path: Path) -> None:
    _python_project(tmp_path, "def broken(:\n    pass\n")

    report = native_diagnosis.run(tmp_path, timeout_seconds=10)

    assert report["failure_observed"] is True
    assert "python_syntax_error" in report["failure_classes"]
    result = report["results"][0]
    assert result["passed"] is False
    assert result["exit_code"] != 0
    assert "SyntaxError" in result["stderr_tail"] or "SyntaxError" in result["stdout_tail"]


def test_diagnosis_never_executes_in_source_tree(tmp_path: Path) -> None:
    _python_project(tmp_path, "VALUE = 1\n")
    before = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))

    report = native_diagnosis.run(tmp_path, timeout_seconds=10)

    after = sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob("*"))
    assert before == after
    assert not list(tmp_path.rglob("__pycache__"))
    assert report["source_tree_execution"] is False


def test_probe_budget_is_hard_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _python_project(tmp_path, "VALUE = 1\n")
    fake = (
        native_diagnosis.Probe("python", (sys.executable, "-c", "raise SystemExit(2)")),
        native_diagnosis.Probe("python", (sys.executable, "-c", "raise SystemExit(3)")),
    )
    monkeypatch.setattr(native_diagnosis, "plan", lambda root, max_probes=8: fake[:max_probes])

    report = native_diagnosis.run(tmp_path, max_probes=1, timeout_seconds=10)

    assert report["planned_probe_count"] == 1
    assert report["executed_probe_count"] == 1
    assert report["retry_count"] == 0


def test_stop_after_first_failure_never_retries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _python_project(tmp_path, "VALUE = 1\n")
    fake = (
        native_diagnosis.Probe("python", (sys.executable, "-c", "raise SystemExit(2)")),
        native_diagnosis.Probe("python", (sys.executable, "-c", "raise SystemExit(0)")),
    )
    monkeypatch.setattr(native_diagnosis, "plan", lambda root, max_probes=8: fake[:max_probes])

    report = native_diagnosis.run(
        tmp_path,
        timeout_seconds=10,
        stop_after_first_failure=True,
    )

    assert report["planned_probe_count"] == 2
    assert report["executed_probe_count"] == 1
    assert report["retry_count"] == 0
