"""Language/toolchain capability registry for autonomous Genesis software work.

The registry deliberately exposes *tools*, not solutions. Compilers, linters,
formatters and test runners are observable environment capabilities. Nothing in
this module calls an LLM or encodes bug-specific repair recipes.

This is DEVELOPMENT apparatus for the autonomy track: Genesis may use reported
capabilities as sensors/evaluators while learned transformation strategies remain
lineage-owned and subject to the normal trust root.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import Iterable

TOOLCHAIN_REPORT_SCHEMA = "genesis-language-toolchain-report-v1"

_IGNORED_DIRS = {
    ".git",
    ".gradle",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "target",
    "venv",
}


@dataclass(frozen=True)
class LanguagePack:
    name: str
    markers: tuple[str, ...]
    glob_markers: tuple[str, ...]
    core_tools: tuple[str, ...]
    optional_tools: tuple[str, ...]
    diagnostic_commands: tuple[tuple[str, ...], ...]
    verify_commands: tuple[tuple[str, ...], ...]

    def record(self) -> dict[str, object]:
        return {
            "name": self.name,
            "markers": list(self.markers),
            "glob_markers": list(self.glob_markers),
            "core_tools": list(self.core_tools),
            "optional_tools": list(self.optional_tools),
            "diagnostic_commands": [list(command) for command in self.diagnostic_commands],
            "verify_commands": [list(command) for command in self.verify_commands],
        }


PACKS: dict[str, LanguagePack] = {
    "python": LanguagePack(
        name="python",
        markers=("pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"),
        glob_markers=("*.py",),
        core_tools=("python3",),
        optional_tools=("pytest", "ruff", "mypy"),
        diagnostic_commands=(("python3", "-m", "compileall", "-q", "."),),
        verify_commands=(("python3", "-m", "pytest"),),
    ),
    "rust": LanguagePack(
        name="rust",
        markers=("Cargo.toml",),
        glob_markers=("*.rs",),
        core_tools=("cargo", "rustc"),
        optional_tools=("rustfmt", "clippy-driver"),
        diagnostic_commands=(("cargo", "check", "--locked", "--offline"),),
        verify_commands=(("cargo", "test", "--locked", "--offline"),),
    ),
    "java": LanguagePack(
        name="java",
        markers=("pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"),
        glob_markers=("*.java",),
        core_tools=("java",),
        optional_tools=("javac", "mvn", "gradle"),
        diagnostic_commands=(("mvn", "-o", "-q", "-DskipTests", "compile"), ("gradle", "--offline", "classes")),
        verify_commands=(("mvn", "-o", "test"), ("gradle", "--offline", "test")),
    ),
    "csharp": LanguagePack(
        name="csharp",
        markers=("global.json",),
        glob_markers=("*.csproj", "*.sln", "*.cs"),
        core_tools=("dotnet",),
        optional_tools=(),
        diagnostic_commands=(("dotnet", "build", "--no-restore", "--nologo"),),
        verify_commands=(("dotnet", "test", "--no-restore", "--nologo"),),
    ),
    "go": LanguagePack(
        name="go",
        markers=("go.mod", "go.work"),
        glob_markers=("*.go",),
        core_tools=("go",),
        optional_tools=("gofmt",),
        diagnostic_commands=(("go", "test", "-run", "^$", "./..."),),
        verify_commands=(("go", "test", "./..."),),
    ),
    "typescript": LanguagePack(
        name="typescript",
        markers=("tsconfig.json", "package.json"),
        glob_markers=("*.ts", "*.tsx", "*.js", "*.jsx"),
        core_tools=("node",),
        optional_tools=("npm", "npx", "tsc"),
        diagnostic_commands=(("npx", "--no-install", "tsc", "--noEmit"),),
        verify_commands=(("npm", "test", "--", "--runInBand"),),
    ),
}


def pack(language: str) -> LanguagePack:
    try:
        return PACKS[str(language).lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported language pack: {language!r}") from exc


def _visible_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        if any(part in _IGNORED_DIRS for part in relative.parts[:-1]):
            continue
        yield path


def detect_languages(root: str | Path) -> tuple[str, ...]:
    """Detect supported language families from repository metadata/source files."""
    base = Path(root)
    if not base.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {base}")

    root_names = {item.name for item in base.iterdir() if item.is_file()}
    files = tuple(_visible_files(base))
    detected: list[str] = []

    for name, language_pack in PACKS.items():
        if any(marker in root_names for marker in language_pack.markers):
            detected.append(name)
            continue
        if any(
            any(path.match(pattern) for pattern in language_pack.glob_markers)
            for path in files
        ):
            detected.append(name)

    return tuple(sorted(detected))


def _tool_record(name: str) -> dict[str, object]:
    resolved = shutil.which(name)
    return {
        "name": name,
        "available": resolved is not None,
        "path": resolved,
    }


def capability_report(root: str | Path) -> dict[str, object]:
    """Return toolchain facts without executing repository code or external models."""
    languages = detect_languages(root)
    records: list[dict[str, object]] = []
    for language in languages:
        language_pack = pack(language)
        core = [_tool_record(name) for name in language_pack.core_tools]
        optional = [_tool_record(name) for name in language_pack.optional_tools]
        records.append(
            {
                "language": language,
                "core_tools": core,
                "optional_tools": optional,
                "core_ready": all(bool(item["available"]) for item in core),
                "diagnostic_commands": [
                    list(command) for command in language_pack.diagnostic_commands
                ],
                "verify_commands": [
                    list(command) for command in language_pack.verify_commands
                ],
            }
        )

    return {
        "schema": TOOLCHAIN_REPORT_SCHEMA,
        "project_root": str(Path(root).resolve()),
        "languages": list(languages),
        "packs": records,
        "external_model_calls": 0,
        "note": (
            "Toolchains are sensors/evaluators only; learned repair strategy is "
            "not encoded by this registry."
        ),
    }
