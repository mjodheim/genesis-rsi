"""Localization cases from projects that took no part in any development of this repository.

Every localizer here was written, selected and validated on bugs of the seventeen Defects4J
projects. Cases of the same projects, however carefully split, share code, tests and habits. A
catalogue in the Defects4J format that covers other projects gives problems that are new in a
stronger sense: no line of their repositories was ever shown to a writer or scored by a judge.

This module holds the rules only: which bugs are eligible, how many per project, and which part
each repository falls in. Parts are assigned by repository, so two modules of one code base never
sit on both sides of a comparison. The ``reserve`` part is not prepared until a plan names it.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Mapping, Sequence

DOMAIN = "genesis-external-localization-v1|"
PARTS = ("first", "second", "reserve")
PER_PROJECT = 12
# A copy of the Defects4J Math bugs under another repository address.
KNOWN_COPIES = frozenset({"Math_4j"})


def repository_key(address: str) -> str:
    """One spelling per repository: scheme and host prefix variants and ``.git`` are dropped."""
    key = address.strip().lower()
    for prefix in ("https://www.", "http://www.", "https://", "http://"):
        if key.startswith(prefix):
            key = key[len(prefix):]
            break
    key = key.rstrip("/")
    return key[:-4] if key.endswith(".git") else key


def _order(text: str) -> str:
    return hashlib.sha256((DOMAIN + text).encode()).hexdigest()


def part_of(repository: str) -> str:
    """The part of every case of a repository, fixed by its address alone."""
    bucket = int(_order(repository_key(repository)), 16) % 10
    return PARTS[0] if bucket < 4 else PARTS[1] if bucket < 7 else PARTS[2]


def kept_bugs(project: str, bugs: Iterable[str], limit: int = PER_PROJECT) -> list[str]:
    """At most ``limit`` bugs of a project, chosen by a hash of their name, in that order."""
    return sorted(bugs, key=lambda bug: _order(f"{project}-{bug}"))[:limit]


def independent(project: str, repository: str, revisions: Iterable[str], *, used_projects: Iterable[str],
                used_repositories: Iterable[str], used_revisions: Iterable[str]) -> str | None:
    """None when a project shares nothing with the development catalogue, else the reason it is left out."""
    if project in set(used_projects):
        return "project of the development catalogue"
    if project in KNOWN_COPIES:
        return "known copy of a project of the development catalogue"
    if repository_key(repository) in {repository_key(item) for item in used_repositories}:
        return "repository of the development catalogue"
    if set(revisions) & set(used_revisions):
        return "shares a revision with the development catalogue"
    return None


def joined(*pieces: str) -> str:
    """A repository-relative directory from a sub-project and a layout entry."""
    return "/".join(piece.strip("/") for piece in pieces if piece.strip("/") not in ("", "."))


def source_directory(patch_paths: Sequence[str], subproject: str, layout_source: str) -> str | None:
    """The production source directory the patch edits, among the spellings a catalogue may use."""
    for candidate in (joined(subproject, layout_source), joined(layout_source)):
        if candidate and any(path.startswith(candidate + "/") for path in patch_paths):
            return candidate
    return None


def layout_of(rows: Iterable[Sequence[str]], revisions: Sequence[str]) -> tuple[str, str] | None:
    """Source and test directories recorded for the first of ``revisions`` the layout knows."""
    known: Mapping[str, tuple[str, str]] = {row[0]: (row[1], row[2]) for row in rows if len(row) >= 3}
    for revision in revisions:
        if revision in known:
            return known[revision]
    return None
