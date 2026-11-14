"""Run the independent diagnostic without asserting historical SHA outcomes."""
from __future__ import annotations

import socket

import pytest

import diagnose_citation_membership as diagnostic

def test_diagnose_citation_membership(
    monkeypatch, capsys, request, record_property
) -> None:
    def offline(*args, **kwargs):
        raise AssertionError("Network access is forbidden in this diagnostic")

    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(socket, "getaddrinfo", offline)
    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket.socket, "connect_ex", offline)

    try:
        assert diagnostic.main() == 0
    finally:
        captured = capsys.readouterr()
        output = captured.out + captured.err
        request.node.add_report_section("call", "citation diagnostic", output)
        record_property("citation_membership_diagnostic", output)
        with capsys.disabled():
            print(output, end="")

@pytest.mark.parametrize(
    ("template", "expected"),
    [
        ('"git_commit": "{sha}"', [True]),
        ('"commit": "{sha}"', [False]),
        ('"description": "{sha}"', [False]),
        ('"git_commit": "{sha}", "description": "{sha}"', [True, False]),
        ('"description": "{sha}", "git_commit": "{sha}"', [False, True]),
        (
            '"description": "{sha}", "git_commit": "{sha}", '
            '"description": "{sha}"',
            [False, True, False],
        ),
    ],
    ids=[
        "citation-reconnue",
        "commit-nu-non-reconnu",
        "sha-hors-champ",
        "meme-sha-apres-citation",
        "meme-sha-avant-citation",
        "meme-sha-avant-et-apres-citation",
    ],
)
@pytest.mark.parametrize("in_collection", [False, True])
@pytest.mark.parametrize(
    "git_result",
    ["", None],
    ids=["git-succes-sortie-vide", "git-resultat-indetermine"],
)
def test_occurrence_membership_offline(
    monkeypatch, tmp_path, capsys, template, expected, in_collection, git_result
) -> None:
    def offline(*args, **kwargs):
        raise AssertionError("Network access is forbidden in this diagnostic")

    monkeypatch.setattr(socket, "create_connection", offline)
    monkeypatch.setattr(socket, "getaddrinfo", offline)
    monkeypatch.setattr(socket.socket, "connect", offline)
    monkeypatch.setattr(socket.socket, "connect_ex", offline)

    sha = diagnostic.TARGETS[0]
    line = template.format(sha=sha)
    relative = "citations.json"
    (tmp_path / relative).write_text(line + "\n", encoding="utf-8")

    def fake_git(*args):
        if args == ("ls-files", "-z"):
            return relative + "\0"
        if (
            len(args) == 3
            and args[:2] == ("cat-file", "-e")
            and args[2] in {target + "^{commit}" for target in diagnostic.TARGETS}
        ):
            return git_result
        raise AssertionError(f"Unexpected Git call: {args!r}")

    monkeypatch.setattr(diagnostic.integrity, "ROOT", tmp_path)
    monkeypatch.setattr(diagnostic.integrity, "_git", fake_git)
    collected = {sha: [relative]} if in_collection else {}
    monkeypatch.setattr(
        diagnostic.integrity, "commit_typed_citations", lambda: collected
    )

    assert diagnostic.main() == 0
    output = capsys.readouterr().out
    prefix = "occurrence_reconnue_par_COMMIT_FIELD = "
    recognized = [
        entry.removeprefix(prefix)
        for entry in output.splitlines()
        if entry.startswith(prefix)
    ]
    assert recognized == [repr(value) for value in expected]
    assert output.count("OCCURRENCE SANS CHAMP RECONNU") == expected.count(False)
    assert f"occurrences_fichiers_suivis[{sha}] = {len(expected)}" in output
    target_output = output.split(f"\nSHA {sha}\n", 1)[1].split("\nSHA ", 1)[0]
    assert f"appartenance_collecte = {in_collection!r}" in target_output
    assert f"collecte = {collected.get(sha)!r}" in target_output
    assert (
        f"_git('cat-file', '-e', {sha + '^{commit}'!r}) = {git_result!r}"
        in target_output
    )
    assert "None ne distingue pas un objet absent d'une erreur Git." in output
    assert "La chaîne vide '' est distincte de None." in output
