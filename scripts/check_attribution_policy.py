"""Enforce explicit Git attribution and protected-source contribution boundaries."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.request import Request, urlopen
from typing import Iterable, Mapping


BLOCKED_IDENTITY_FRAGMENTS = (
    "[bot]",
)
REGISTERED_HUMAN_IDENTITIES = {
    ("Anthony Mets", "110968830+mjodheim@users.noreply.github.com"),
    # Historical owner-authored scientific commits must retain their frozen hashes.
    # This is the same registered human, not a second contributor or wildcard.
    ("Anthony Mets", "contact@mjodheim.be"),
}
# Registered non-human technical actors, distinct from legal human authorship.
REGISTERED_AI_IDENTITIES = {
    ("Mira", "mira.mjodheim.be@gmail.com"),
    ("Mira", "mira-ai@noreply.github.com"),
    ("Leona (AI)", "leona-ai@noreply.github.com"),
}
REGISTERED_PULL_REQUEST_AUTHORS = {"mjodheim", "Mira-Mjodheim"}
AI_PR_DISCLOSURE = "Provenance: Mira (AI execution)"
LEONA_PR_DISCLOSURE = "Provenance: Leona (AI execution)"
# Owner-submitted AI documentation is limited to reader-facing navigation.
# Frozen experiment artifacts, governance and scientific evaluators remain prohibited.
# Scientific status and reader-facing source of record require human-reviewed
# changes; do not grant an unrestricted AI whole-file exception.
AI_OWNER_DOCUMENTATION_PATHS = frozenset()
# Explicitly owner-reviewed, narrow initial scope: AI may change known
# implementation files and matching ordinary tests, never evaluation oracles.
# Expand only through a separate, independently reviewed governance PR.
AI_ALLOWED_PATHS = frozenset({
    "genesis/learning/capability_gaps.py",
    "genesis/learning/failure_model.py",
    "genesis/learning/self_extension.py",
    "genesis/learning/distillation.py",
    "tests/test_capability_gaps.py",
    "tests/test_failure_model.py",
    "tests/test_failure_driven_self_extension.py",
    "tests/test_distillation.py",
})

COAUTHOR_PATTERN = re.compile(r"^co-authored-by:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
IDENTITY_PATTERN = re.compile(r"^(.+?)\s*<([^<>]+)>$")
TOOL_CREDIT_PATTERN = re.compile(
    r"\b(?:"
    r"(?:generated|assisted|written|created)\s+(?:by|with)"
    r"|development\s+(?:assistant|agent|tool)"
    r"|(?:assistant|agent|tool)\s+(?:credit|attribution)"
    r")\b",
    re.IGNORECASE,
)


def _blocked(value: str) -> str | None:
    lowered = value.casefold()
    return next(
        (fragment for fragment in BLOCKED_IDENTITY_FRAGMENTS if fragment in lowered),
        None,
    )


def audit_commit_records(
    records: Iterable[Mapping[str, str]],
    *,
    verified_platform_commits: frozenset[str] = frozenset(),
) -> list[str]:
    problems: list[str] = []
    for record in records:
        commit = record["commit"]
        for field in ("author_name", "author_email", "committer_name", "committer_email"):
            value = record[field]
            marker = _blocked(value)
            if marker:
                problems.append(f"{commit}: {field} contains blocked attribution {marker!r}")
        for role in ("author", "committer"):
            identity = (record[f"{role}_name"], record[f"{role}_email"])
            if (role == "committer" and identity == ("GitHub", "noreply@github.com")
                    and commit in verified_platform_commits):
                continue
            if identity not in REGISTERED_HUMAN_IDENTITIES and identity not in REGISTERED_AI_IDENTITIES:
                problems.append(f"{commit}: {role} is not a registered human identity")
        for trailer in COAUTHOR_PATTERN.findall(record.get("body", "")):
            marker = _blocked(trailer)
            if marker:
                problems.append(
                    f"{commit}: co-author trailer contains blocked attribution {marker!r}"
                )
            match = IDENTITY_PATTERN.fullmatch(trailer.strip())
            identity = match.groups() if match else None
            if identity not in REGISTERED_HUMAN_IDENTITIES:
                problems.append(
                    f"{commit}: co-author is not a registered human identity"
                )
        body = record.get("body", "")
        if TOOL_CREDIT_PATTERN.search(body):
            problems.append(f"{commit}: commit message contains tool-credit language")
    return problems


def audit_pull_request_payload(payload: Mapping[str, object]) -> list[str]:
    pull_request = payload.get("pull_request")
    if not isinstance(pull_request, Mapping):
        return []
    fields = {
        "title": str(pull_request.get("title") or ""),
        "body": str(pull_request.get("body") or ""),
        "head_ref": str(
            (pull_request.get("head") or {}).get("ref", "")
            if isinstance(pull_request.get("head"), Mapping)
            else ""
        ),
        "author": str(
            (pull_request.get("user") or {}).get("login", "")
            if isinstance(pull_request.get("user"), Mapping)
            else ""
        ),
    }
    problems = []
    if fields["author"] not in REGISTERED_PULL_REQUEST_AUTHORS:
        problems.append("pull request author is not a registered human identity")
    if fields["author"] == "Mira-Mjodheim" and AI_PR_DISCLOSURE not in fields["body"]:
        problems.append("Mira pull request lacks explicit AI provenance declaration")
    for field, value in fields.items():
        marker = _blocked(value)
        if marker:
            problems.append(f"pull request {field} contains blocked attribution {marker!r}")
        if TOOL_CREDIT_PATTERN.search(value):
            problems.append(f"pull request {field} contains tool-credit language")
    return problems


def commit_records(base: str, head: str) -> list[dict[str, str]]:
    separator = "\x1f"
    record_separator = "\x1e"
    completed = subprocess.run(
        [
            "git",
            "log",
            f"--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%B%x1e",
            f"{base}..{head}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    records = []
    for raw in completed.stdout.split(record_separator):
        raw = raw.strip()
        if not raw:
            continue
        fields = raw.split(separator, 5)
        if len(fields) != 6:
            raise ValueError("unexpected git log attribution record")
        records.append(
            dict(
                zip(
                    (
                        "commit",
                        "author_name",
                        "author_email",
                        "committer_name",
                        "committer_email",
                        "body",
                    ),
                    fields,
                    strict=True,
                )
            )
        )
    return records


def audit_ai_paths(
    paths: Iterable[str],
    *,
    allowed_paths: frozenset[str] = AI_ALLOWED_PATHS,
) -> list[str]:
    """Keep non-human contributions outside governance, trust roots and frozen records."""
    return [f"AI contribution cannot modify protected path: {path}" for path in paths
            if path not in allowed_paths]


def changed_paths(base: str, head: str) -> list[str]:
    """Include deleted paths and both sides of a rename; never let scope checks miss them."""
    result = subprocess.run(["git", "diff", "--name-only", "-z", "--no-renames",
                             f"{base}...{head}"], check=True, capture_output=True)
    return [part.decode("utf-8") for part in result.stdout.split(bytes([0])) if part]


def commit_changed_paths(commit: str) -> list[str]:
    """Discover each commit's own changes, including deletions and rename sides.

    First-parent differences avoid attributing imported base changes to the
    technical update merge; a verified platform merge is also separately checked.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid commit SHA")
    result = subprocess.run([
        "git", "diff-tree", "--root", "-r", "-m", "--first-parent",
        "--no-commit-id", "--name-only", "-z", "--no-renames", commit,
    ], check=True, capture_output=True)
    return [part.decode("utf-8") for part in result.stdout.split(bytes([0])) if part]


def verify_github_update_merge(
    record: Mapping[str, str],
    *,
    base_sha: str,
    head_sha: str,
    event: Mapping[str, object],
    github_commit: Mapping[str, object],
    valid_base_commits: frozenset[str] | None = None,
) -> bool:
    """Accept only GitHub-signed branch updates based on an ancestor of the current base."""
    pr = event.get("pull_request")
    if not isinstance(pr, Mapping):
        return False
    head = pr.get("head")
    base = pr.get("base")
    if not isinstance(head, Mapping) or not isinstance(base, Mapping):
        return False
    head_ref, base_ref = head.get("ref"), base.get("ref")
    if not all(isinstance(ref, str) and ref for ref in (head_ref, base_ref)):
        return False
    if head.get("sha") != head_sha or base.get("sha") != base_sha:
        return False
    if (record["committer_name"], record["committer_email"]) != ("GitHub", "noreply@github.com"):
        return False
    if (record["author_name"], record["author_email"]) not in (
            REGISTERED_HUMAN_IDENTITIES | REGISTERED_AI_IDENTITIES):
        return False
    message = "Merge branch '" + base_ref + "' into " + head_ref
    git_meta = github_commit.get("commit")
    if not isinstance(git_meta, Mapping):
        return False
    signature = git_meta.get("verification")
    author = git_meta.get("author")
    committer = git_meta.get("committer")
    if not isinstance(signature, Mapping) or not isinstance(author, Mapping) or not isinstance(committer, Mapping):
        return False
    if not (signature.get("verified") is True and signature.get("reason") == "valid"
            and isinstance(signature.get("signature"), str) and signature["signature"].startswith("-----BEGIN PGP SIGNATURE-----")):
        return False
    if github_commit.get("sha") != record["commit"]:
        return False
    if (author.get("name"), author.get("email")) != (record["author_name"], record["author_email"]):
        return False
    if (committer.get("name"), committer.get("email")) != ("GitHub", "noreply@github.com"):
        return False
    if git_meta.get("message") != message:
        return False
    parents = github_commit.get("parents")
    if not isinstance(parents, list) or len(parents) != 2:
        return False
    if not (isinstance(parents[0], Mapping) and isinstance(parents[1], Mapping)):
        return False
    # Earlier signed GitHub update merges must remain accepted after a new commit
    # or a later base update. The second parent must belong to the current base's
    # trusted ancestry; the first must be distinct and non-null.
    accepted = valid_base_commits if valid_base_commits is not None else frozenset({base_sha})
    second = parents[1].get("sha")
    first = parents[0].get("sha")
    return isinstance(second, str) and second in accepted and isinstance(first, str) and first != second


def github_commit_metadata(sha: str) -> Mapping[str, object] | None:
    """Inspect signed GitHub metadata via its authenticated API; fail closed."""
    repo = os.getenv("GITHUB_REPOSITORY", "")
    token = os.getenv("GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token:
        return None
    url = f"https://api.github.com/repos/{repo}/commits/{sha}"
    request = Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(request, timeout=10) as response:
            result = json.load(response)
        return result if isinstance(result, Mapping) else None
    except (OSError, ValueError):
        return None


def audit_ai_contribution_scope(
    records: Iterable[Mapping[str, str]],
    *,
    login: str,
    pr_body: str,
    paths: Iterable[str],
    paths_by_commit: Mapping[str, Iterable[str]] | None = None,
    verified_platform_commits: frozenset[str] = frozenset(),
) -> list[str]:
    """Enforce AI provenance and a per-commit protected-source boundary.

    For an owner PR, an unrelated human-authored change cannot hide a
    nonhuman protected-source edit, and a nonhuman edit cannot retroactively
    turn the human edit into an AI contribution.
    """
    rows = list(records)
    ai_by_commit: list[tuple[str, set[tuple[str, str]]]] = []
    all_nonhumans: set[tuple[str, str]] = set()
    for record in rows:
        identities = {
            identity
            for identity in (
                (record["author_name"], record["author_email"]),
                (record["committer_name"], record["committer_email"]),
            )
            if identity in REGISTERED_AI_IDENTITIES
        }
        all_nonhumans.update(identities)
        if identities and record["commit"] not in verified_platform_commits:
            ai_by_commit.append((record["commit"], identities))

    problems = []
    expected_disclosure = {
        "Leona (AI)": LEONA_PR_DISCLOSURE,
        "Mira": AI_PR_DISCLOSURE,
    }
    for name, _ in sorted(all_nonhumans):
        if expected_disclosure[name] not in pr_body:
            problems.append(f"AI contribution lacks provenance disclosure for {name}")

    if login == "Mira-Mjodheim":
        # Entire fork PR remains restricted: human-signed commits cannot
        # smuggle a protected path through Mira's publication account.
        problems.extend(audit_ai_paths(paths))
    elif login == "mjodheim":
        for commit, _ in ai_by_commit:
            # The fallback remains fail-closed for unit test / legacy callers.
            own_paths = paths if paths_by_commit is None else paths_by_commit[commit]
            problems.extend(
                f"{commit}: {error}" for error in
                audit_ai_paths(own_paths, allowed_paths=AI_ALLOWED_PATHS)
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--event", type=Path, required=True)
    arguments = parser.parse_args()

    payload = json.loads(arguments.event.read_text(encoding="utf-8"))
    records = commit_records(arguments.base, arguments.head)
    trusted_base_commits = frozenset(
        subprocess.check_output(["git", "rev-list", arguments.base], text=True).splitlines()
    )
    verified = set()
    for record in records:
        if (record["committer_name"], record["committer_email"]) != ("GitHub", "noreply@github.com"):
            continue
        metadata = github_commit_metadata(record["commit"])
        if metadata and verify_github_update_merge(
                record, base_sha=arguments.base, head_sha=arguments.head,
                event=payload, github_commit=metadata,
                valid_base_commits=trusted_base_commits):
            verified.add(record["commit"])
    problems = audit_commit_records(records, verified_platform_commits=frozenset(verified))
    problems.extend(audit_pull_request_payload(payload))
    pr = payload.get("pull_request") or {}
    author = (pr.get("user") or {}).get("login") if isinstance(pr, dict) else None
    if author in REGISTERED_PULL_REQUEST_AUTHORS:
        pr_body = pr.get("body", "") if isinstance(pr, dict) else ""
        problems.extend(audit_ai_contribution_scope(
            records, login=author, pr_body=pr_body or "",
            paths=changed_paths(arguments.base, arguments.head),
            paths_by_commit={
                record["commit"]: commit_changed_paths(record["commit"])
                for record in records
                if record["commit"] not in verified
                and any(identity in REGISTERED_AI_IDENTITIES for identity in (
                    (record["author_name"], record["author_email"]),
                    (record["committer_name"], record["committer_email"]),
                ))
            },
            verified_platform_commits=frozenset(verified),
        ))
    if problems:
        print("FAIL — Attribution policy")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK   — Registered provenance and protected-source boundaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
