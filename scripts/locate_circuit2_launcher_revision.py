#!/usr/bin/env python3
"""Localise la révision git du lanceur Circuit 2 dont le SHA-256 est attendu.

Outil de diagnostic en lecture seule : il lit le hachage attendu dans le
manifeste, parcourt l'historique git du lanceur, hache chaque révision et
produit un rapport JSON canonique. Il ne modifie aucun fichier existant et
ne restaure rien.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = "experiment/engine/CIRCUIT2/EXECUTABLES.json"
DEFAULT_LAUNCHER = "scripts/run_circuit2_campaign.py"
ALLOWED_OUTPUT_DIRS = ("results", "docs")
NOT_FOUND_MESSAGE = "version gelée introuvable"


class DiagnosticError(Exception):
    """Erreur d'usage ou d'entrée, signalée sans trace d'appel."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run_git(repo: Path, args: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=False,
        shell=False,
        env=env,
    )


def read_expected_hash(repo: Path, manifest: str, launcher: str) -> str:
    manifest_path = repo / manifest
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DiagnosticError(f"manifeste illisible : {manifest_path} ({exc})") from exc
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict) or launcher not in files:
        raise DiagnosticError(f"entrée absente de 'files' : {launcher}")
    entry = files[launcher]
    if isinstance(entry, dict):
        entry = entry.get("sha256")
    if not isinstance(entry, str) or not entry.strip():
        raise DiagnosticError(f"hachage attendu invalide pour {launcher}")
    return entry.strip().lower()


def list_revisions(repo: Path, launcher: str, all_refs: bool) -> list[str]:
    revisions: list[str] = []
    for follow in (False, True):
        args = ["log", "--format=%H"]
        if all_refs:
            args.append("--all")
        if follow:
            args.append("--follow")
        args += ["--", launcher]
        result = run_git(repo, args)
        if result.returncode != 0:
            message = result.stderr.decode("utf-8", "replace").strip()
            raise DiagnosticError(f"git log a échoué : {message}")
        for line in result.stdout.decode("ascii", "replace").split():
            if line not in revisions:
                revisions.append(line)
    return revisions


def hash_revision(repo: Path, revision: str, launcher: str) -> str | None:
    result = run_git(repo, ["show", f"{revision}:{launcher}"])
    if result.returncode != 0:
        return None
    return sha256_hex(result.stdout)


def hash_working_tree(repo: Path, launcher: str) -> str | None:
    try:
        return sha256_hex((repo / launcher).read_bytes())
    except OSError:
        return None


def build_report(
    repo: Path, manifest: str, launcher: str, all_refs: bool
) -> dict[str, Any]:
    expected = read_expected_hash(repo, manifest, launcher)
    entries: list[dict[str, Any]] = []
    for revision in list_revisions(repo, launcher, all_refs):
        digest = hash_revision(repo, revision, launcher)
        entries.append(
            {
                "revision": revision,
                "sha256": digest,
                "correspond": "oui" if digest == expected else "non",
            }
        )
    matching = [e["revision"] for e in entries if e["correspond"] == "oui"]
    working = hash_working_tree(repo, launcher)
    return {
        "launcher": launcher,
        "expected_sha256": expected,
        "working_tree_sha256": working,
        "working_tree_correspond": "oui" if working == expected else "non",
        "revisions": entries,
        "revisions_correspondantes": matching,
        "message": "" if matching else NOT_FOUND_MESSAGE,
    }


def canonical_json(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def resolve_output(repo: Path, output: str) -> Path:
    repo_real = repo.resolve()
    allowed = []
    for name in ALLOWED_OUTPUT_DIRS:
        root = repo / name
        real_root = repo_real / name
        if root.is_symlink() or (root.exists() and root.resolve() != real_root):
            raise DiagnosticError(f"sortie refusée : racine non sûre : {root}")
        allowed.append(real_root)

    candidate = Path(output)
    if not candidate.is_absolute():
        candidate = repo / candidate
    target = candidate.resolve()
    for root in allowed:
        try:
            relative = target.relative_to(root)
        except ValueError:
            continue
        if relative.parts:
            break
    else:
        raise DiagnosticError(
            "sortie refusée : le chemin doit être sous results/ ou docs/"
        )
    if (
        candidate.exists()
        or candidate.is_symlink()
        or target.exists()
        or target.is_symlink()
    ):
        raise DiagnosticError(f"sortie refusée : fichier déjà présent : {target}")
    return target


def write_new_file(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except FileExistsError as exc:
        raise DiagnosticError(f"sortie refusée : fichier déjà présent : {target}") from exc


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--launcher", default=DEFAULT_LAUNCHER)
    parser.add_argument("--all-refs", action="store_true")
    parser.add_argument("--output", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        repo = Path(args.repo).resolve()
        target = resolve_output(repo, args.output) if args.output else None
        report = build_report(repo, args.manifest, args.launcher, args.all_refs)
        text = canonical_json(report)
        if target is not None:
            write_new_file(target, text)
    except DiagnosticError as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
