"""Tests hors réseau de scripts/export_circuit2_launcher_revision.py."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parent.parent / "scripts" / "export_circuit2_launcher_revision.py"
)
LANCEUR = "scripts/run_circuit2_campaign.py"
CONTENU = b"#!/usr/bin/env python3\r\nprint('faux lanceur')\r\n\x00\xff fin\n"
SHA = hashlib.sha256(CONTENU).hexdigest()

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git indisponible")


def _git(repo: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(repo), "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return res.stdout.strip()


@pytest.fixture
def depot(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "depot"
    (repo / "scripts").mkdir(parents=True)
    _git(repo, "init", "-q")
    (repo / LANCEUR).write_bytes(CONTENU)
    (repo / "README.md").write_text("suivi\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-q", "-m", "initial")
    return repo, _git(repo, "rev-parse", "HEAD")


def _lancer(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), "--repo", str(repo), *args],
        capture_output=True,
        text=True,
    )


def test_extraction_exacte(depot):
    repo, rev = depot
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", "results/lanceur.py")
    assert res.returncode == 0, res.stderr
    assert (repo / "results" / "lanceur.py").read_bytes() == CONTENU
    assert rev in res.stdout
    assert SHA in res.stdout
    assert "results/lanceur.py" in res.stdout


def test_sha_different_refuse(depot):
    repo, rev = depot
    faux = "0" * 64
    res = _lancer(repo, "--revision", rev, "--expected-sha256", faux, "--out", "results/lanceur.py")
    assert res.returncode == 2
    assert not (repo / "results" / "lanceur.py").exists()


@pytest.mark.parametrize("variante", ["abregee", "inexistante"])
def test_revision_invalide_refusee(depot, variante):
    repo, rev = depot
    revision = rev[:7] if variante == "abregee" else "0" * 40
    res = _lancer(repo, "--revision", revision, "--expected-sha256", SHA, "--out", "results/lanceur.py")
    assert res.returncode == 1
    assert not (repo / "results").exists()


@pytest.mark.parametrize("sortie", ["../evil.py", "autre/evil.py", "results/../evil.py", "results"])
def test_sortie_hors_results_refusee(depot, sortie):
    repo, rev = depot
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", sortie)
    assert res.returncode == 1
    assert not (repo / "results").exists()
    assert not (repo.parent / "evil.py").exists()
    assert not (repo / "autre").exists()


def test_sortie_absolue_refusee(depot, tmp_path):
    repo, rev = depot
    cible = tmp_path / "abs.py"
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", str(cible))
    assert res.returncode == 1
    assert not cible.exists()


def test_lien_symbolique_refuse(depot, tmp_path):
    repo, rev = depot
    externe = tmp_path / "externe"
    externe.mkdir()
    (repo / "results").mkdir()
    (repo / "results" / "lien").symlink_to(externe, target_is_directory=True)
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", "results/lien/lanceur.py")
    assert res.returncode == 1
    assert not (externe / "lanceur.py").exists()


def test_fichier_existant_non_ecrase(depot):
    repo, rev = depot
    (repo / "results").mkdir()
    existant = repo / "results" / "lanceur.py"
    existant.write_bytes(b"ancien")
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", "results/lanceur.py")
    assert res.returncode == 1
    assert existant.read_bytes() == b"ancien"


def test_aucun_fichier_suivi_modifie(depot):
    repo, rev = depot
    avant = _git(repo, "ls-files", "-s")
    res = _lancer(repo, "--revision", rev, "--expected-sha256", SHA, "--out", "results/lanceur.py")
    assert res.returncode == 0, res.stderr
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert _git(repo, "ls-files", "-s") == avant
    assert _git(repo, "rev-parse", "HEAD") == rev
