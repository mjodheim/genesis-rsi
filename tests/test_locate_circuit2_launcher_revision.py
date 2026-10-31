"""Tests du localisateur de révision du lanceur Circuit 2 (hors réseau)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "locate_circuit2_launcher_revision.py"
)
LAUNCHER = "scripts/run_circuit2_campaign.py"
MANIFEST = "experiment/engine/CIRCUIT2/EXECUTABLES.json"
VERSIONS = [b"print('v1')\n", b"print('v2')\n", b"print('v3')\n"]

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git indisponible")


def load_module():
    spec = importlib.util.spec_from_file_location("locate_circuit2_launcher_revision", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_manifest(root: Path, digest: str) -> None:
    path = root / MANIFEST
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"files": {LAUNCHER: digest}}), encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    git(root, "config", "commit.gpgsign", "false")
    (root / "scripts").mkdir()
    revisions = []
    for index, content in enumerate(VERSIONS):
        (root / LAUNCHER).write_bytes(content)
        git(root, "add", LAUNCHER)
        git(root, "commit", "-q", "-m", f"version {index + 1}")
        revisions.append(git(root, "rev-parse", "HEAD"))
    return root, revisions


def run_tool(capsys, root: Path, *extra: str):
    code = load_module().main(["--repo", str(root), *extra])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_identifie_la_bonne_revision(repo, capsys):
    root, revisions = repo
    write_manifest(root, sha(VERSIONS[1]))
    code, out, _ = run_tool(capsys, root)
    report = json.loads(out)
    assert code == 0
    assert report["expected_sha256"] == sha(VERSIONS[1])
    assert [e["revision"] for e in report["revisions"]] == revisions[::-1]
    assert [e["correspond"] for e in report["revisions"]] == ["non", "oui", "non"]
    assert report["revisions_correspondantes"] == [revisions[1]]
    assert report["message"] == ""
    assert report["working_tree_sha256"] == sha(VERSIONS[2])
    assert report["working_tree_correspond"] == "non"


def test_rapporte_introuvable(repo, capsys):
    root, _ = repo
    write_manifest(root, sha(b"version inconnue\n"))
    code, out, _ = run_tool(capsys, root)
    report = json.loads(out)
    assert code == 0
    assert report["revisions_correspondantes"] == []
    assert report["message"] == "version gelée introuvable"
    assert all(e["correspond"] == "non" for e in report["revisions"])


def test_refuse_une_sortie_hors_results_docs(repo, capsys, tmp_path):
    root, _ = repo
    write_manifest(root, sha(VERSIONS[0]))
    candidates = [
        str(tmp_path / "ailleurs" / "rapport.json"),
        "../rapport.json",
        "scripts/rapport.json",
        "results/../rapport.json",
    ]
    for candidate in candidates:
        code, out, err = run_tool(capsys, root, "--output", candidate)
        assert code == 2
        assert out == ""
        assert "sortie refusée" in err
    assert not (tmp_path / "ailleurs").exists()
    assert not (tmp_path / "rapport.json").exists()
    assert not (root / "rapport.json").exists()
    assert not (root / "scripts" / "rapport.json").exists()


def test_ecrit_sous_results_sans_ecraser(repo, capsys):
    root, _ = repo
    write_manifest(root, sha(VERSIONS[0]))
    manifest_avant = (root / MANIFEST).read_bytes()
    launcher_avant = (root / LAUNCHER).read_bytes()
    code, out, _ = run_tool(capsys, root, "--output", "results/rapport.json")
    target = root / "results" / "rapport.json"
    assert code == 0
    assert target.read_text(encoding="utf-8") == out
    assert out.endswith("\n")
    contenu = target.read_bytes()
    code, _, err = run_tool(capsys, root, "--output", "results/rapport.json")
    assert code == 2
    assert "déjà présent" in err
    assert target.read_bytes() == contenu
    assert (root / MANIFEST).read_bytes() == manifest_avant
    assert (root / LAUNCHER).read_bytes() == launcher_avant

@pytest.mark.parametrize("name", ["results", "docs"])
@pytest.mark.parametrize("output_name", ["results", "docs"])
def test_refuse_une_racine_liee_hors_depot(
    repo, capsys, tmp_path, name, output_name
):
    root, _ = repo
    write_manifest(root, sha(VERSIONS[0]))
    exterior = tmp_path / "exterieur"
    exterior.mkdir()
    link = root / name
    try:
        link.symlink_to(exterior, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"liens symboliques indisponibles : {exc}")

    code, out, err = run_tool(
        capsys, root, "--output", f"{output_name}/rapport.json"
    )
    assert code == 2
    assert out == ""
    assert "sortie refusée" in err
    assert list(exterior.iterdir()) == []
    assert link.is_symlink()
    assert link.readlink() == exterior
    assert not (root / output_name / "rapport.json").exists()

def test_refuse_results_lie_a_docs(repo, capsys):
    root, _ = repo
    write_manifest(root, sha(VERSIONS[0]))
    docs = root / "docs"
    docs.mkdir()
    link = root / "results"
    try:
        link.symlink_to(docs, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"liens symboliques indisponibles : {exc}")

    code, out, err = run_tool(capsys, root, "--output", "results/rapport.json")
    assert code == 2
    assert out == ""
    assert "sortie refusée" in err
    assert list(docs.iterdir()) == []
    assert link.is_symlink()
    assert link.readlink() == docs
