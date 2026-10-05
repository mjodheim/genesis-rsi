"""Reject non-human Git attribution and tool-credit pull-request metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
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
REGISTERED_PULL_REQUEST_AUTHORS = {"mjodheim"}
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


def audit_commit_records(records: Iterable[Mapping[str, str]]) -> list[str]:
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
            if identity not in REGISTERED_HUMAN_IDENTITIES:
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--event", type=Path, required=True)
    arguments = parser.parse_args()

    payload = json.loads(arguments.event.read_text(encoding="utf-8"))
    problems = audit_commit_records(commit_records(arguments.base, arguments.head))
    problems.extend(audit_pull_request_payload(payload))
    if problems:
        print("FAIL — Attribution policy")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("OK   — Human-only repository attribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
