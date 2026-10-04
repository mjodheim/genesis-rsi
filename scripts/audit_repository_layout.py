"""Live repository inventory and structural hygiene checks.

This module is intentionally descriptive rather than destructive.  It gives maintainers one
repeatable answer to "what is in this repository now?" and makes a small set of repository
lifecycle rules executable without treating scientific evidence as cleanup debt.

Run it directly for a human-readable inventory::

    python scripts/audit_repository_layout.py

Use ``--json`` for machine-readable output and ``--check`` to make hygiene violations fail the
process.  The test suite calls :func:`hygiene_problems`, so the same rules are enforced in normal CI.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DIRECTORIES = (
    ".github/workflows",
    "archives/workflows",
    "docs",
    "experiments",
    "metamorphosis",
    "mira_core",
    "results",
    "scripts",
    "tests",
)

# Permanent workflows are normal repository infrastructure.  Most milestone workflows should be
# archived after use, but a small set is itself part of a frozen protocol: its exact historical
# path under .github/workflows is committed by scientific hashes/tests.  Those files must remain
# byte-exact at that path even when the milestone is no longer operational.
PERMANENT_WORKFLOWS = frozenset({
    "ci.yml", "attribution-policy.yml", "v24-l5-freeze-build.yml",
    # This replays retained evidence; it never launches a new scientific attempt.
    "rsi-v27-v29-evidence.yml",
    "rsi-v31-archive-evidence.yml",
    "rsi-v32-memory-evidence.yml",
    "rsi-v33-active-memory-evidence.yml",
    "rsi-v34-continuing-evidence.yml",
    "rsi-v42-evidence.yml",
})
ACTIVE_MILESTONE_WORKFLOWS: frozenset[str] = frozenset({
    "m141-v42-freeze.yml",
    "m142-v42-fresh-prefix.yml",
})
FROZEN_PATH_WORKFLOWS = frozenset(
    {
        "m064-canonical.yml",
        "m065-canonical.yml",
        "m066-canonical.yml",
        "m092-adoption-qualification-rehearsal.yml",
        "m092-canonical-search.yml",
        "m092-canonical-transport-rehearsal.yml",
        "m092-independent-reproduction.yml",
        "m092-reproduction-transport-rehearsal.yml",
        "m092-runtime-envelope.yml",
    }
)
MILESTONE_WORKFLOW = re.compile(r"m\d{3}.*\.ya?ml", re.IGNORECASE)

FORBIDDEN_TRACKED_PARTS = frozenset(
    {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".hypothesis"}
)
FORBIDDEN_TRACKED_NAMES = frozenset({".DS_Store", "Thumbs.db", ".coverage"})
FORBIDDEN_ROOT_GENERATED = frozenset({"manifest.json", "artifacts_manifest.json"})


def _git_tracked_files() -> list[Path] | None:
    """Return tracked paths when git is available, otherwise ``None``."""
    try:
        completed = subprocess.run(
            ("git", "ls-files", "-z"),
            cwd=ROOT,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return sorted(
        ROOT / value.decode("utf-8", errors="surrogateescape")
        for value in completed.stdout.split(b"\0")
        if value
    )


def tracked_files() -> list[Path]:
    """Tracked files, with a filesystem fallback for source archives without ``.git``."""
    from_git = _git_tracked_files()
    if from_git is not None:
        return [path for path in from_git if path.is_file()]

    ignored = {".git", ".venv", "venv", "env"} | set(FORBIDDEN_TRACKED_PARTS)
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(ROOT).parts)
    )


def _relative(paths: Iterable[Path]) -> list[str]:
    return [path.relative_to(ROOT).as_posix() for path in paths]


def inventory() -> dict[str, object]:
    """Return a deterministic structural inventory of the current tracked tree."""
    files = tracked_files()
    by_top_level: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "bytes": 0})
    by_extension: dict[str, int] = defaultdict(int)
    digest_groups: dict[str, list[Path]] = defaultdict(list)
    total_bytes = 0

    for path in files:
        relative = path.relative_to(ROOT)
        size = path.stat().st_size
        total_bytes += size
        bucket = relative.parts[0] if len(relative.parts) > 1 else "<root>"
        by_top_level[bucket]["files"] += 1
        by_top_level[bucket]["bytes"] += size
        by_extension[path.suffix.lower() or "<none>"] += 1

        # Duplicate reporting is informational and limited to non-trivial files.  Repeated tiny
        # fixtures and __init__ files are common and do not represent meaningful repository debt.
        if size >= 4096:
            digest_groups[hashlib.sha256(path.read_bytes()).hexdigest()].append(path)

    duplicates = [
        {"bytes": group[0].stat().st_size, "files": _relative(group)}
        for group in digest_groups.values()
        if len(group) > 1
    ]
    duplicates.sort(key=lambda item: (-int(item["bytes"]), item["files"]))

    largest = sorted(files, key=lambda path: path.stat().st_size, reverse=True)[:15]
    workflow_dir = ROOT / ".github" / "workflows"
    archive_dir = ROOT / "archives" / "workflows"
    workflow_files = sorted(path.name for path in workflow_dir.glob("*.y*ml") if path.is_file())

    return {
        "tracked_files": len(files),
        "tracked_bytes": total_bytes,
        "top_level": dict(sorted(by_top_level.items())),
        "extensions": dict(sorted(by_extension.items(), key=lambda item: (-item[1], item[0]))),
        "workflow_files": workflow_files,
        "operational_workflows": sorted(
            name
            for name in workflow_files
            if name in PERMANENT_WORKFLOWS or name in ACTIVE_MILESTONE_WORKFLOWS
        ),
        "frozen_path_workflows": sorted(
            name for name in workflow_files if name in FROZEN_PATH_WORKFLOWS
        ),
        "archived_workflows": len(list(archive_dir.glob("*.y*ml"))),
        "largest_files": [
            {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size}
            for path in largest
        ],
        "duplicate_groups_over_4k": duplicates,
    }


def hygiene_problems() -> list[str]:
    """Return structural defects that should make normal repository validation fail."""
    problems: list[str] = []
    files = tracked_files()
    relative_files = {path.relative_to(ROOT).as_posix() for path in files}

    for directory in REQUIRED_DIRECTORIES:
        if not (ROOT / directory).is_dir():
            problems.append(f"required repository directory is missing: {directory}")

    # Do not permit a half-migrated package layout.  The two package roots are intentionally kept
    # stable while current/preserved research tooling still refers to their physical paths.
    for package in ("mira_core", "metamorphosis"):
        if (ROOT / "src" / package).exists() and (ROOT / package).exists():
            problems.append(f"package exists in both root and src layouts: {package}")

    workflow_dir = ROOT / ".github" / "workflows"
    archived_dir = ROOT / "archives" / "workflows"

    # A path-bound workflow is evidence: absence or relocation is itself a reproducibility defect.
    for name in sorted(FROZEN_PATH_WORKFLOWS):
        if not (workflow_dir / name).is_file():
            problems.append(f"frozen path-bound workflow is missing: {name}")
        if (archived_dir / name).exists():
            problems.append(f"frozen path-bound workflow is duplicated in archive: {name}")

    for path in workflow_dir.glob("*.y*ml"):
        if not MILESTONE_WORKFLOW.fullmatch(path.name):
            continue
        if path.name in FROZEN_PATH_WORKFLOWS:
            continue
        if path.name not in ACTIVE_MILESTONE_WORKFLOWS:
            problems.append(
                f"milestone workflow is executable but not explicitly active: {path.name}; "
                "archive it or list it in ACTIVE_MILESTONE_WORKFLOWS"
            )
        if (archived_dir / path.name).exists():
            problems.append(f"workflow exists both active and archived: {path.name}")

    active_non_milestone = {
        path.name
        for path in workflow_dir.glob("*.y*ml")
        if not MILESTONE_WORKFLOW.fullmatch(path.name)
    }
    unexpected = sorted(active_non_milestone - PERMANENT_WORKFLOWS)
    problems.extend(f"unexpected permanent workflow: {name}" for name in unexpected)

    for path in files:
        relative = path.relative_to(ROOT)
        if any(part in FORBIDDEN_TRACKED_PARTS for part in relative.parts):
            problems.append(f"generated cache is tracked: {relative.as_posix()}")
        if path.name in FORBIDDEN_TRACKED_NAMES or path.suffix.lower() in {".pyc", ".pyo"}:
            problems.append(f"generated local file is tracked: {relative.as_posix()}")

    for name in FORBIDDEN_ROOT_GENERATED:
        if name in relative_files:
            problems.append(f"generated runtime artifact is tracked at repository root: {name}")

    return sorted(set(problems))


def _human_bytes(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if amount < 1024 or unit == "GiB":
            return f"{amount:.1f} {unit}" if unit != "B" else f"{int(amount)} B"
        amount /= 1024
    raise AssertionError("unreachable")


def print_human(report: dict[str, object], problems: list[str]) -> None:
    print(f"Tracked files : {report['tracked_files']}")
    print(f"Tracked size  : {_human_bytes(int(report['tracked_bytes']))}")
    print(f"Operational CI: {len(report['operational_workflows'])} workflow(s)")
    print(f"Frozen paths  : {len(report['frozen_path_workflows'])} workflow(s)")
    print(f"Archived CI   : {report['archived_workflows']} workflow(s)")
    print("\nTop-level inventory:")
    for name, values in report["top_level"].items():
        print(f"  {name:24} {values['files']:5} files  {_human_bytes(values['bytes']):>10}")
    print("\nLargest tracked files:")
    for item in report["largest_files"]:
        print(f"  {_human_bytes(item['bytes']):>10}  {item['path']}")
    duplicates = report["duplicate_groups_over_4k"]
    print(f"\nDuplicate content groups (>4 KiB): {len(duplicates)}")
    if problems:
        print("\nHygiene problems:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("\nRepository hygiene: OK")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the inventory as JSON")
    parser.add_argument("--check", action="store_true", help="exit non-zero on hygiene defects")
    arguments = parser.parse_args()

    report = inventory()
    problems = hygiene_problems()
    if arguments.json:
        print(json.dumps({**report, "hygiene_problems": problems}, indent=2, ensure_ascii=False))
    else:
        print_human(report, problems)
    return 1 if arguments.check and problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
