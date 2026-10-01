"""Structural repository guardrails.

Four real defects motivated this script. The first three were invisible to sealed
evaluation workflows because those workflows executed only selected test files:

1. `metamorphosis/core.py` imported `torch`, which made the documented `pytest -q`
   command fail on every machine without PyTorch;
2. roughly 2,400 lines formed a completely disconnected import subgraph without any
   signal exposing it;
3. `pyproject.toml` declared `torch` and `scipy`, although neither was imported;
4. sixteen commits cited by SHA in the registers — among them M042's frozen protocol,
   the M050-M052 development results and M094's own freeze commit — were reachable
   from no ref at all, so routine branch cleanup or garbage collection would have made
   those citations unresolvable while leaving the record looking intact.

Each check is independent and may be run on its own.

    python scripts/check_repository_integrity.py            # all checks
    python scripts/check_repository_integrity.py --orphans  # one check
"""

from __future__ import annotations

import argparse
import ast
from collections import deque
import json
from pathlib import Path
import re
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ("genesis", "metamorphosis", "mira_core")

# Every commit the tracked record cites by SHA, and the ref that keeps it reachable.
CITATIONS = ROOT / "docs" / "COMMIT_CITATIONS.json"

# File kinds that carry citations. Binary and vendored trees are not scanned.
CITED_IN = ("*.md", "*.json", "*.yaml", "*.yml", "*.py", "*.toml")

# A run of hex long enough to abbreviate a commit, isolated from surrounding alphanumerics so
# that a 64-character artifact digest is not mistaken for one.
HEX_TOKEN = re.compile(r"(?<![0-9a-zA-Z])([0-9a-f]{7,40})(?![0-9a-zA-Z])")

# Modules under `scripts/` that are legitimate entry points. They do not need to be
# imported by another module to be considered live.
ENTRY_POINT_PREFIXES = ("run_", "audit_", "author_", "build_", "train_", "check_")

# Tools invoked from the command line and never imported by source code. Declaring them
# without importing them is legitimate.
# Declared in pyproject but never imported by the project, because they are invoked as
# commands or loaded as pytest plugins rather than used as libraries.
COMMAND_LINE_TOOLS = {"pytest", "pytest-xdist"}

# A third-party import name does not always match its distribution name.
DISTRIBUTION_ALIASES = {
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "cv2": "opencv-python",
    "PIL": "pillow",
}

# Standalone capsule entry points deliberately import a sibling by its copied filename.  In the
# repository that sibling remains namespaced under ``metamorphosis``; at runtime both files are
# copied into an otherwise empty directory and Python is launched with ``-I``.  Keep the mapping
# explicit so the integrity graph can model that boundary without treating the sibling as PyPI or
# requiring frozen capsule source to gain repository-only import logic.
LOCAL_IMPORT_ALIASES = {
    "m098_runtime": "metamorphosis.m098_runtime",
    "m101_executor": "metamorphosis.m101_executor",
    "m101_runtime": "metamorphosis.m101_runtime",
    "m102_executor": "metamorphosis.m102_executor",
    "m102_runtime": "metamorphosis.m102_runtime",
    "m103_runtime": "metamorphosis.m103_runtime",
}


def source_files() -> list[Path]:
    directories = tuple(ROOT / package for package in PACKAGES) + (ROOT / "scripts", ROOT / "tests")
    return sorted(
        path
        for directory in directories
        if directory.is_dir()
        for path in directory.rglob("*.py")
    )


def module_name(path: Path) -> str:
    relative = path.relative_to(ROOT)
    if relative.parts[0] in PACKAGES:
        parts = relative.with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)
    return relative.stem


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def imported_names(path: Path) -> set[str]:
    """Return imported module names, resolving relative imports."""
    found: set[str] = set()
    relative = path.relative_to(ROOT)
    package = module_name(path).rsplit(".", 1)[0] if relative.parts[0] in PACKAGES else ""
    for node in ast.walk(parse(path)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and package:
                base = f"{package}.{node.module}" if node.module else package
            elif node.module:
                base = node.module
            else:
                continue
            found.add(base)
            # `from metamorphosis import m095_arms` imports a *module*, not a name inside one.
            # Recording only the package made every module imported that way look unreachable,
            # which is the idiom most of this codebase actually uses.
            found.update(f"{base}.{alias.name}" for alias in node.names)
    return found


def check_imports() -> list[str]:
    """Every module must import cleanly with declared dependencies installed."""
    import importlib

    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "scripts"))
    failures: list[str] = []
    for local_name, qualified_name in LOCAL_IMPORT_ALIASES.items():
        try:
            sys.modules[local_name] = importlib.import_module(qualified_name)
        except Exception as error:  # noqa: BLE001 - preserve the complete diagnostic
            failures.append(f"{qualified_name}: {type(error).__name__}: {error}")
    for path in source_files():
        if path.parts[-2] == "tests":
            continue  # pytest owns collection and fixture setup for tests
        name = module_name(path)
        try:
            importlib.import_module(name)
        except Exception as error:  # noqa: BLE001 - preserve the complete diagnostic
            failures.append(f"{path.relative_to(ROOT)}: {type(error).__name__}: {error}")
    return failures


def check_orphans() -> list[str]:
    """No package module may be unreachable from a legitimate entry point."""
    files = {module_name(path): path for path in source_files()}
    roots = [
        name
        for name, path in files.items()
        if path.parts[-2] == "tests" or name.startswith(ENTRY_POINT_PREFIXES)
    ]

    reachable: set[str] = set()
    queue = deque(roots)
    while queue:
        name = queue.popleft()
        if name in reachable or name not in files:
            continue
        reachable.add(name)
        for target in imported_names(files[name]):
            # Handles `metamorphosis.m012b_dfa` and `m014b_eval_support`, as well as
            # `metamorphosis.m012b_dfa.DFA` produced by `from x.y import z`.
            for candidate in (target, target.rsplit(".", 1)[0]):
                candidate = LOCAL_IMPORT_ALIASES.get(candidate, candidate)
                if candidate in files:
                    queue.append(candidate)

    return [
        f"{files[name].relative_to(ROOT)} is not imported by any entry point"
        for name in sorted(set(files) - reachable)
    ]


def check_dependencies() -> list[str]:
    """Declared dependencies and real third-party imports must match."""
    manifest = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = manifest.get("project", {})

    def distributions(requirements: list[str]) -> set[str]:
        cleaned = set()
        for requirement in requirements:
            name = requirement.split(";")[0]
            for separator in ("[", ">", "<", "=", "!", "~", " "):
                name = name.split(separator)[0]
            if name:
                cleaned.add(name.strip().lower())
        return cleaned

    declared = distributions(project.get("dependencies", []))
    for extra in project.get("optional-dependencies", {}).values():
        declared |= distributions(extra)

    # ``scripts`` is an intentional repository-local namespace even though it is not an
    # installable distribution package.  Tests and cross-checkers may use an explicit
    # ``scripts.foo`` import when they need the package-qualified identity; pyproject's pytest
    # path also supports the historical bare ``foo`` entry-point imports.  Neither spelling is a
    # third-party dependency.
    local = (
        set(PACKAGES)
        # Scientific entry points execute these repository-local namespaces
        # from the checkout; they are not third-party distribution dependencies.
        | {"scripts", "tests", "experiment"}
        | set(LOCAL_IMPORT_ALIASES)
        | {module_name(path) for path in source_files()}
    )
    used: set[str] = set()
    for path in source_files():
        for name in imported_names(path):
            top = name.split(".")[0]
            if top in local or top in sys.stdlib_module_names or top == "__future__":
                continue
            used.add(DISTRIBUTION_ALIASES.get(top, top).lower())

    problems = [
        f"`{name}` is imported but absent from pyproject.toml"
        for name in sorted(used - declared)
    ]
    problems += [
        f"`{name}` is declared in pyproject.toml but never imported"
        for name in sorted(declared - used - COMMAND_LINE_TOOLS)
    ]
    return problems


def _git(*arguments: str) -> str | None:
    """Run a read-only git command, or return None when git cannot answer."""
    try:
        finished = subprocess.run(
            ("git", *arguments), cwd=ROOT, capture_output=True, text=True, timeout=120
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return finished.stdout if finished.returncode == 0 else None


def _tracked_text_files() -> list[str]:
    names: list[str] = []
    for pattern in CITED_IN:
        listing = _git("ls-files", pattern)
        if listing:
            names.extend(listing.split())
    return names


def _hex_tokens() -> dict[str, set[str]]:
    """Every abbreviated-commit-shaped token in the tracked record, and where it is written."""
    found: dict[str, set[str]] = {}
    for name in _tracked_text_files():
        try:
            text = (ROOT / name).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for match in HEX_TOKEN.finditer(text):
            found.setdefault(match.group(1), set()).add(name)
    return found


#: Keys whose value is a git commit rather than an artifact digest. `*_commitment` is
#: deliberately excluded: those are sha256 bank and suite commitments, not git objects.
COMMIT_FIELD = re.compile(r'"?([a-z_]*_commit)"?\s*:\s*"?([0-9a-f]{40})"?')


def commit_typed_citations() -> dict[str, list[str]]:
    """Every 40-hex value written in a position that declares itself a git commit.

    The reachability check can only see citations that still resolve, so the population it
    cannot see is precisely the population already lost. This one can: a value in a
    `*_commit` field is asserted to be a commit, so failing to resolve is a defect in the
    record rather than a false positive.
    """

    found: dict[str, list[str]] = {}
    for name in _tracked_text_files():
        try:
            text = (ROOT / name).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for key, sha in COMMIT_FIELD.findall(text):
            if key.endswith("_commitment"):
                continue
            found.setdefault(sha, []).append(f"{name} ({key})")
    return found


def record_citations() -> int:
    """Rewrite the citation manifest from the working tree and the refs that exist right now.

    Run this after adding a citation. It is deliberately not a check: deciding that a newly cited
    commit is adequately preserved is a judgement, and this only records the judgement's inputs.
    """
    listed = _git("rev-list", "--all")
    on_main = _git("rev-list", "origin/main") or _git("rev-list", "main")
    if listed is None or on_main is None:
        print("FAIL — git could not enumerate commits")
        return 1
    reachable, mainline = set(listed.split()), set(on_main.split())

    prefixes: dict[str, list[str]] = {}
    for sha in reachable:
        prefixes.setdefault(sha[:7], []).append(sha)

    commits: dict[str, set[str]] = {}
    for token, where in _hex_tokens().items():
        for candidate in prefixes.get(token[:7], ()):
            if candidate.startswith(token):
                commits.setdefault(candidate, set()).update(where)

    records = {}
    for sha in sorted(commits):
        if sha in mainline:
            preserved = "main"
        else:
            tags = (_git("for-each-ref", "--contains", sha, "--format=%(refname:short)",
                         "refs/tags") or "").split()
            preserved = tags[0] if tags else "UNPRESERVED"
        records[sha] = {
            "subject": (_git("log", "-1", "--format=%s", sha) or "").strip(),
            "preserved_by": preserved,
            "cited_in": sorted(commits[sha]),
        }

    # Refuse to forget. The manifest is rebuilt only from commits that are reachable NOW, so a
    # citation that has become unreachable simply produces no entry -- and re-recording after
    # a red check would turn a real loss into a green one. That is a laundering pipeline, and
    # the docstring inviting `--record` after adding a citation makes it the natural next step.
    previous: dict = {}
    if CITATIONS.exists():
        try:
            previous = json.loads(CITATIONS.read_text(encoding="utf-8")).get("commits", {})
        except (OSError, json.JSONDecodeError):
            previous = {}
    dropped = sorted(set(previous) - set(records))
    if dropped:
        print(f"FAIL — {len(dropped)} recorded citation(s) would be dropped, not updated")
        for sha in dropped:
            entry = previous[sha]
            print(f"  {sha[:12]} {entry.get('subject', '?')[:56]}")
            print(f"      was preserved by {entry.get('preserved_by', '?')}")
        print("Nothing was written. Restore the missing refs, or remove these entries")
        print("deliberately and say why.")
        return 1

    CITATIONS.write_text(
        json.dumps(
            {
                "schema": "commit-citations-v1",
                "purpose": (
                    "Every commit the tracked scientific record cites by SHA, and the ref that "
                    "keeps it reachable. Checked by scripts/check_repository_integrity.py "
                    "--citations. A citation that stops resolving makes a recorded result "
                    "unverifiable, so this file exists to make that failure loud instead of silent."
                ),
                "commits": records,
                "known_unresolvable": (
                    json.loads(CITATIONS.read_text(encoding="utf-8"))
                    .get("known_unresolvable", {})
                    if CITATIONS.exists() else {}
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    unpreserved = [sha for sha, entry in records.items() if entry["preserved_by"] == "UNPRESERVED"]
    tagged = sum(1 for entry in records.values() if entry["preserved_by"] != "main")
    print(f"recorded {len(records)} cited commits in {_shown(CITATIONS)}")
    print(f"  reachable from main : {len(records) - tagged}")
    print(f"  preserved by a tag  : {tagged}")
    for sha in unpreserved:
        print(f"  UNPRESERVED — {sha[:12]} {records[sha]['subject'][:60]}")
    return 1 if unpreserved else 0


def _shown(path: Path) -> str:
    """A path as the record would spell it, tolerating one that lies outside the repository."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def check_citations() -> list[str]:
    """Every commit the record cites must still resolve and stay reachable from a ref.

    Sixteen commits named in the registers were once reachable from no ref whatsoever. They
    survived only until git chose to collect them, and deleting a stale branch would have made
    a frozen protocol's own freeze commit unrecoverable — the citation would still be printed
    in the record, and nothing would resolve it. Annotated tags now preserve every one of them.

    This check exists so that losing one is loud. A citation that stops resolving does not
    corrupt a result; it makes the result unverifiable, which is worse, because nothing about
    the record's appearance changes.
    """
    if not CITATIONS.exists():
        return [f"{_shown(CITATIONS)} is missing"]

    try:
        manifest = json.loads(CITATIONS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return [f"{_shown(CITATIONS)} is unreadable: {error}"]

    recorded = manifest.get("commits", {})
    if not recorded:
        return [f"{_shown(CITATIONS)} records no commit"]

    # A shallow clone cannot answer the question. Say so rather than reporting every citation
    # as lost, and rather than passing without evidence.
    shallow = _git("rev-parse", "--is-shallow-repository")
    if shallow is None:
        return ["git is unavailable, so citations cannot be verified"]
    if shallow.strip() == "true":
        return [
            "this is a shallow clone, so reachability cannot be established; "
            "check out with fetch-depth: 0"
        ]

    listed = _git("rev-list", "--all")
    if listed is None:
        return ["git could not enumerate reachable commits"]
    reachable = set(listed.split())

    # Most citations are preserved by tags rather than by a branch. A clone that fetched no tags
    # would report every one of them as lost, which is an instrument failure wearing the costume
    # of a real one. Say which it is.
    wanted = {
        entry.get("preserved_by", "")
        for entry in recorded.values()
        if entry.get("preserved_by", "").startswith(("provenance/", "branch/"))
    }
    problems: list[str] = []
    if wanted:
        present = set((_git("tag", "--list") or "").split())
        if not wanted & present:
            if not present:
                # No tags at all: this clone never fetched them. Nothing can be concluded.
                return [
                    f"none of the {len(wanted)} preserving tags exist in this clone and it has "
                    "no tags at all, so reachability cannot be established; run "
                    "`git fetch --tags` first"
                ]
            # Tags exist, but not these. They were deleted, which is a real loss. Saying
            # "run git fetch --tags" here would hand the operator a remedy that cannot work
            # and suppress the list of what is actually gone, so name it and continue.
            problems.append(
                f"{len(wanted)} preserving tags are missing while {len(present)} other tags "
                "are present: they were deleted rather than never fetched"
            )

    problems += [
        f"{sha[:12]} ({entry.get('subject', '?')[:48]}) is cited in "
        f"{', '.join(entry.get('cited_in', [])[:2]) or 'the record'} but is no longer "
        f"reachable; it was preserved by {entry.get('preserved_by', 'an unrecorded ref')}"
        for sha, entry in sorted(recorded.items())
        if sha not in reachable
    ]

    # Keep the manifest current: a citation added since it was last written is a citation
    # nothing is protecting yet.
    prefixes: dict[str, list[str]] = {}
    for sha in reachable:
        prefixes.setdefault(sha[:7], []).append(sha)

    unrecorded: dict[str, str] = {}
    for token, where in _hex_tokens().items():
        for candidate in prefixes.get(token[:7], ()):
            if candidate.startswith(token) and candidate not in recorded:
                unrecorded.setdefault(candidate, sorted(where)[0])

    # A citation in a position that declares itself a commit must resolve. This is the only
    # part of the check that can see a citation which was lost before the manifest existed.
    excused = manifest.get("known_unresolvable", {})
    for sha, where in sorted(commit_typed_citations().items()):
        if sha in excused:
            continue
        if _git("cat-file", "-e", sha + "^{commit}") is None:
            problems.append(
                f"{sha[:12]} is written as a commit in {where[0]} and does not resolve; "
                "record it under known_unresolvable with a reason if the loss is accepted"
            )

    problems += [
        f"{sha[:12]} is cited in {name} but absent from "
        f"{_shown(CITATIONS)}"
        for sha, name in sorted(unrecorded.items())
    ]
    return problems


CHECKS = {
    "imports": ("Every module imports cleanly", check_imports),
    "orphans": ("No orphan module", check_orphans),
    "dependencies": ("Declared dependencies match imports", check_dependencies),
    "citations": ("Every cited commit stays reachable", check_citations),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag, (help_text, _) in CHECKS.items():
        parser.add_argument(f"--{flag}", action="store_true", help=help_text)
    parser.add_argument(
        "--record",
        action="store_true",
        help="Rewrite docs/COMMIT_CITATIONS.json from the tree and refs as they are now",
    )
    arguments = parser.parse_args()

    if arguments.record:
        return record_citations()

    selected = [flag for flag in CHECKS if getattr(arguments, flag)] or list(CHECKS)

    failed = False
    for flag in selected:
        label, check = CHECKS[flag]
        problems = check()
        if problems:
            failed = True
            print(f"FAIL — {label}")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print(f"OK   — {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
