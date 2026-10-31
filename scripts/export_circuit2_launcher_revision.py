#!/usr/bin/env python3
"""Exporte les octets du lanceur Circuit 2 à une révision git donnée.

Outil hors gel : lit uniquement l'objet git local (git cat-file blob), sans
réseau et sans modèle, puis écrit les octets tels quels sous results/ en
création exclusive (mode 'x'). Aucun fichier suivi n'est modifié.

Codes de sortie : 0 succès, 1 refus (arguments, sortie, révision, fichier
existant), 2 écart de SHA-256 (rien n'est écrit).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

LAUNCHER_PATH = "scripts/run_circuit2_campaign.py"
RESULTS_DIR = "results"
REVISION_RE = re.compile(r"[0-9a-f]{40}")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
EXIT_REFUS = 1
EXIT_ECART = 2


class Refus(Exception):
    """Refus explicite : rien n'est écrit."""


def valider_hex(valeur: str, motif: re.Pattern[str], nom: str) -> str:
    normalisee = valeur.lower()
    if not motif.fullmatch(normalisee):
        raise Refus(f"{nom} invalide : format hexadécimal complet exigé")
    return normalisee


def valider_sortie(repo: Path, out: str) -> Path:
    segments = out.split("/")
    if not out or "\\" in out or any(s in ("", ".", "..") for s in segments):
        raise Refus(
            "--out doit être un chemin relatif propre, sans '..' ni segment vide"
        )
    if len(segments) < 2 or segments[0] != RESULTS_DIR:
        raise Refus("--out doit désigner un fichier sous results/")
    courant = repo
    for segment in segments:
        courant = courant / segment
        if courant.is_symlink():
            raise Refus("--out ne doit traverser aucun lien symbolique")
    racine = (repo / RESULTS_DIR).resolve()
    cible = repo.joinpath(*segments)
    if racine not in cible.resolve().parents:
        raise Refus("--out sort de results/")
    if cible.exists():
        raise Refus(f"fichier déjà existant : {out}")
    return cible


def extraire(repo: Path, revision: str) -> bytes:
    try:
        res = subprocess.run(
            ["git", "-C", str(repo), "cat-file", "blob", f"{revision}:{LAUNCHER_PATH}"],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        raise Refus(f"git inaccessible : {exc}") from exc
    if res.returncode != 0:
        raise Refus(
            f"révision ou fichier introuvable : {revision}:{LAUNCHER_PATH}"
        )
    return res.stdout


def ecrire(cible: Path, octets: bytes) -> None:
    cible.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(cible, "xb") as fh:
            fh.write(octets)
    except FileExistsError as exc:
        raise Refus(f"fichier déjà existant : {cible.name}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrait le lanceur Circuit 2 d'une révision git locale vers results/."
    )
    parser.add_argument("--revision", required=True, help="hash complet (40 hex)")
    parser.add_argument("--expected-sha256", required=True, help="SHA-256 attendu (64 hex)")
    parser.add_argument("--out", required=True, help="chemin relatif sous results/")
    parser.add_argument("--repo", default=None, help="racine du dépôt (défaut : dépôt de l'outil)")
    args = parser.parse_args(argv)
    repo = (Path(args.repo) if args.repo else Path(__file__).resolve().parent.parent).resolve()
    try:
        revision = valider_hex(args.revision, REVISION_RE, "--revision")
        attendu = valider_hex(args.expected_sha256, SHA256_RE, "--expected-sha256")
        cible = valider_sortie(repo, args.out)
        octets = extraire(repo, revision)
        calcule = hashlib.sha256(octets).hexdigest()
        if calcule != attendu:
            print(
                f"ÉCART SHA-256 : attendu {attendu}, calculé {calcule} ; rien n'est écrit",
                file=sys.stderr,
            )
            return EXIT_ECART
        ecrire(cible, octets)
    except Refus as exc:
        print(f"REFUS : {exc}", file=sys.stderr)
        return EXIT_REFUS
    print(f"revision: {revision}")
    print(f"sha256: {calcule}")
    print(f"chemin: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
