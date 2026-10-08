"""Regression checks for the repository-integrity checker itself."""
from __future__ import annotations

import json
from pathlib import Path

import check_repository_integrity as integrity
from check_repository_integrity import check_citations, check_dependencies


def test_repository_scripts_and_experiments_are_local_not_distribution_dependencies() -> None:
    assert check_dependencies() == []


def test_g11_g12_studies_are_registered_as_cli_entry_points() -> None:
    for prefix in ("g11_", "g12_", "select_", "preregister_"):
        assert prefix in integrity.ENTRY_POINT_PREFIXES
    assert integrity.check_orphans() == []


def test_relative_imports_from_init_keep_full_package_namespace() -> None:
    module = integrity.ROOT / "genesis/insights/__init__.py"
    imports = integrity.imported_names(module)
    assert "genesis.insights.security" in imports
    assert "genesis.insights.performance" in imports
    assert "genesis.insights.registry" in imports


def test_every_module_is_reachable_from_a_legitimate_entry_point() -> None:
    assert "build_" in integrity.ENTRY_POINT_PREFIXES
    assert "author_" in integrity.ENTRY_POINT_PREFIXES
    assert integrity.check_orphans() == []


def test_isolated_capsule_sibling_has_an_explicit_repository_alias() -> None:
    assert integrity.LOCAL_IMPORT_ALIASES == {
        "m098_runtime": "metamorphosis.m098_runtime",
        "m101_executor": "metamorphosis.m101_executor",
        "m101_runtime": "metamorphosis.m101_runtime",
        "m102_executor": "metamorphosis.m102_executor",
        "m102_runtime": "metamorphosis.m102_runtime",
        "m103_runtime": "metamorphosis.m103_runtime",
    }


def test_every_commit_the_record_cites_is_still_reachable() -> None:
    """The live manifest, against the live repository. This is the check doing its job."""
    assert check_citations() == []


def _manifest(tmp_path: Path, commits: dict[str, dict]) -> Path:
    path = tmp_path / "COMMIT_CITATIONS.json"
    path.write_text(
        json.dumps({"schema": "commit-citations-v1", "commits": commits}),
        encoding="utf-8",
    )
    return path


def _one_real_citation() -> tuple[str, dict]:
    recorded = json.loads(integrity.CITATIONS.read_text(encoding="utf-8"))["commits"]
    return next(iter(sorted(recorded.items())))


def test_a_cited_commit_that_stopped_resolving_is_reported(tmp_path, monkeypatch) -> None:
    """The failure this check exists for: the citation still reads, and nothing resolves it."""
    vanished = "0" * 40
    monkeypatch.setattr(
        integrity,
        "CITATIONS",
        _manifest(
            tmp_path,
            {
                vanished: {
                    "subject": "freeze(m094): bind the eligible set",
                    "preserved_by": "provenance/dd79665",
                    "cited_in": ["SCIENTIFIC_HYPOTHESES.md"],
                }
            },
        ),
    )
    lost = [problem for problem in check_citations() if "no longer reachable" in problem]
    assert len(lost) == 1
    assert vanished[:12] in lost[0]
    assert "SCIENTIFIC_HYPOTHESES.md" in lost[0], "the report must name where the citation reads"
    assert "provenance/dd79665" in lost[0], "the report must name the ref that used to preserve it"


def test_a_commit_cited_but_absent_from_the_manifest_is_reported(tmp_path, monkeypatch) -> None:
    """A citation added later is a citation nothing is protecting yet."""
    sha, entry = _one_real_citation()
    keeper = "1" * 39 + "a"
    monkeypatch.setattr(
        integrity,
        "CITATIONS",
        _manifest(tmp_path, {keeper: {"subject": "placeholder", "preserved_by": "main"}}),
    )
    problems = check_citations()
    assert any(sha[:12] in problem and "absent from" in problem for problem in problems), (
        f"{sha[:12]}, cited in {entry.get('cited_in', ['?'])[0]}, was not reported as unrecorded"
    )


def test_a_shallow_clone_is_reported_rather_than_passing(monkeypatch) -> None:
    """Reachability is unanswerable without history, and unanswerable is not the same as fine."""
    monkeypatch.setattr(
        integrity,
        "_git",
        lambda *arguments: "true\n" if arguments[:2] == ("rev-parse", "--is-shallow-repository") else None,
    )
    problems = check_citations()
    assert problems == [
        "this is a shallow clone, so reachability cannot be established; "
        "check out with fetch-depth: 0"
    ]


def test_a_missing_manifest_is_reported(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(integrity, "CITATIONS", tmp_path / "absent.json")
    problems = check_citations()
    assert len(problems) == 1
    assert problems[0].endswith("absent.json is missing")


# ── the guard must not be able to launder a loss ──────────────────────


def test_record_refuses_to_drop_a_citation_it_can_no_longer_reach(tmp_path, monkeypatch, capsys) -> None:
    """`--record` rebuilt the manifest only from what is reachable NOW.

    So a citation that had become unreachable simply produced no entry, vanished from the
    manifest without a word, and the next `--citations` went green. With the docstring inviting
    `--record` after adding a citation, re-recording is the natural response to a red check --
    which makes real loss, misdiagnosis and a green check into one continuous pipeline.
    """

    vanished = "b" * 40
    path = _manifest(
        tmp_path,
        {vanished: {"subject": "a result nobody can verify any more", "preserved_by": "main"}},
    )
    monkeypatch.setattr(integrity, "CITATIONS", path)

    before = path.read_text(encoding="utf-8")
    assert integrity.record_citations() == 1
    assert path.read_text(encoding="utf-8") == before, "the manifest was rewritten anyway"

    printed = capsys.readouterr().out
    assert "would be dropped" in printed
    assert vanished[:12] in printed


def test_a_commit_typed_citation_that_does_not_resolve_is_reported(tmp_path, monkeypatch) -> None:
    """The only part of the check that can see a citation lost before the manifest existed.

    Reachability can only be asked of commits that resolve, so the population it cannot see is
    exactly the population already gone. A value written in a `*_commit` field asserts that it
    is a commit, so failing to resolve is a defect in the record rather than a false positive.
    """

    absent = "c" * 40
    monkeypatch.setattr(
        integrity,
        "commit_typed_citations",
        lambda: {absent: ["experiments/M999/RESULT.json (qualification_commit)"]},
    )
    problems = [p for p in check_citations() if "written as a commit" in p]
    assert len(problems) == 1
    assert absent[:12] in problems[0]
    assert "M999" in problems[0]


def test_a_deliberately_dead_citation_is_excused_only_with_a_recorded_reason() -> None:
    """M013c cites a commit precisely to record that the announcement was defective.

    Five citations do not resolve and four of them should not: a test fixture placeholder, a
    revoked announcement kept as evidence of its own revocation, and two objects that live in
    an external repository. The fifth is a real loss and is recorded as one rather than excused.
    """

    manifest = json.loads(integrity.CITATIONS.read_text(encoding="utf-8"))
    excused = manifest["known_unresolvable"]
    unresolvable = {
        sha for sha in integrity.commit_typed_citations()
        if integrity._git("cat-file", "-e", sha + "^{commit}") is None
    }
    assert set(excused) == unresolvable
    assert all(entry["reason"] and entry["kind"] for entry in excused.values())
    lost = [sha for sha, entry in excused.items() if entry["kind"] == "lost"]
    assert lost == ["b8a8bb064ff456c491369bd1ca25c72ca187b545"], (
        "the M049 qualification commit is a genuine loss and must stay recorded as one"
    )
