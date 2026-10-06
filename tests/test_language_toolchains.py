from __future__ import annotations

from pathlib import Path

import pytest

from genesis import language_toolchains as tools


@pytest.mark.parametrize(
    ("filename", "language"),
    [
        ("pyproject.toml", "python"),
        ("Cargo.toml", "rust"),
        ("pom.xml", "java"),
        ("demo.csproj", "csharp"),
        ("go.mod", "go"),
        ("tsconfig.json", "typescript"),
    ],
)
def test_detect_language_from_project_marker(tmp_path: Path, filename: str, language: str) -> None:
    (tmp_path / filename).write_text("", encoding="utf-8")
    assert language in tools.detect_languages(tmp_path)


def test_detects_nested_source_but_ignores_generated_directories(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "main.rs").write_text("fn main() {}\n", encoding="utf-8")

    generated = tmp_path / "node_modules" / "dep"
    generated.mkdir(parents=True)
    (generated / "index.ts").write_text("export {};\n", encoding="utf-8")

    assert tools.detect_languages(tmp_path) == ("rust",)


def test_capability_report_never_claims_external_model_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "go.mod").write_text("module example.test\n", encoding="utf-8")
    monkeypatch.setattr(tools.shutil, "which", lambda name: f"/tool/{name}")

    report = tools.capability_report(tmp_path)

    assert report["schema"] == tools.TOOLCHAIN_REPORT_SCHEMA
    assert report["languages"] == ["go"]
    assert report["external_model_calls"] == 0
    assert report["packs"][0]["core_ready"] is True
    assert report["packs"][0]["verify_commands"] == [["go", "test", "./..."]]


def test_unknown_pack_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported language pack"):
        tools.pack("brainfuck")
