"""Current main policy must remain intact while signed update commits are verified."""
from __future__ import annotations

from copy import deepcopy
import pytest

from check_attribution_policy import (
    audit_commit_records, audit_mira_paths, REGISTERED_IDENTITIES,
    verify_github_update_merge,
)


def case():
    base, head, first = "2" * 40, "3" * 40, "1" * 40
    row = {
        "commit": head,
        "author_name": "Mira", "author_email": "mira-ai@noreply.github.com",
        "committer_name": "GitHub", "committer_email": "noreply@github.com",
        "body": "Merge branch 'main' into mira/research",
    }
    event = {"pull_request": {
        "head": {"sha": head, "ref": "mira/research"},
        "base": {"sha": base, "ref": "main"},
    }}
    metadata = {
        "sha": head,
        "commit": {
            "author": {"name": row["author_name"], "email": row["author_email"]},
            "committer": {"name": "GitHub", "email": "noreply@github.com"},
            "message": "Merge branch 'main' into mira/research",
            "verification": {"verified": True, "reason": "valid",
                             "signature": "-----BEGIN PGP SIGNATURE-----\ntest"},
        },
        "parents": [{"sha": first}, {"sha": base}],
    }
    return row, event, metadata, base, head


def verify(row, event, metadata, base, head, *, trusted=None):
    return verify_github_update_merge(
        row, event=event, github_commit=metadata,
        base_sha=base, head_sha=head,
        valid_base_commits=frozenset({base} if trusted is None else trusted),
    )


def test_signature_only_exempts_exact_platform_committer():
    row, event, metadata, base, head = case()
    assert audit_commit_records([row]) == [head + ": committer is not Anthony or Mira"]
    assert verify(row, event, metadata, base, head)
    assert audit_commit_records(
        [row], verified_platform_commits=frozenset({head})
    ) == []


def test_historical_signed_message_survives_main_rename():
    row, event, metadata, base, head = case()
    event["pull_request"]["base"]["ref"] = "trunk"
    assert verify(row, event, metadata, base, head)
    assert not verify(row, event, metadata, base, head, trusted={"a" * 40})


@pytest.mark.parametrize("path,bad", [
    (("commit", "verification", "verified"), False),
    (("commit", "verification", "reason"), "unsigned"),
    (("commit", "verification", "signature"), None),
    (("commit", "message"), "A different operation"),
    (("commit", "message"), "Merge branch 'main' into elsewhere"),
    (("commit", "message"), "Merge branch '../foo' into mira/research"),
    (("commit", "committer", "email"), "fake@github.com"),
    (("commit", "author", "name"), "Someone else"),
    (("sha",), "f" * 40),
    (("parents",), [{"sha": "1" * 40}]),
    (("parents",), [{"sha": "1" * 40}, {"sha": "f" * 40}]),
])
def test_forged_metadata_rejected(path, bad):
    row, event, metadata, base, head = case()
    fake = deepcopy(metadata)
    current = fake
    for field in path[:-1]:
        current = current[field]
    current[path[-1]] = bad
    assert not verify(row, event, fake, base, head)


def test_mira_rights_remain_as_decided_on_october_fourteenth():
    assert ("Mira", "mira-ai@noreply.github.com") in REGISTERED_IDENTITIES
    assert audit_mira_paths(["genesis/core/self_model.py", "docs/ROADMAP.md"]) == []
    assert audit_mira_paths(["scripts/check_attribution_policy.py", ".github/workflows/ci.yml"]) == [
        "Mira cannot modify merge gate: scripts/check_attribution_policy.py",
        "Mira cannot modify merge gate: .github/workflows/ci.yml",
    ]
