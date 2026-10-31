"""Sceau d'identité du lanceur CIRCUIT2 (hors réseau, sans modèle).

Le sceau lie le SHA-256 du lanceur et celui de ce vérificateur au digest du plan
canonique ; le lanceur refuse de s'exécuter si le sceau est absent ou ne correspond pas.
Le sceau est écrit en mode 'x' : aucun écrasement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for _path in (HERE, ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import freeze_circuit2_plan as freeze  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SCHEMA = "circuit2-launcher-seal-v1"
SEAL_PATH = ROOT / "experiment/engine/CIRCUIT2/LAUNCHER_SEAL.json"
LAUNCHER_REL = "scripts/run_circuit2_campaign.py"
VERIFIER_REL = "scripts/seal_circuit2_launcher.py"
FIELDS = ("schema", "launcher_path", "launcher_sha256", "verifier_sha256", "plan_digest", "digest")


class SealError(Exception):
    """Sceau d'identité absent, illisible, altéré ou non conforme."""


def file_sha256(path):
    """SHA-256 hexadécimal du contenu du fichier."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_seal(plan_digest, root=ROOT):
    """Sceau pour le lanceur et le vérificateur situés sous root."""
    root = Path(root)
    body = {
        "schema": SCHEMA,
        "launcher_path": LAUNCHER_REL,
        "launcher_sha256": file_sha256(root / LAUNCHER_REL),
        "verifier_sha256": file_sha256(root / VERIFIER_REL),
        "plan_digest": plan_digest,
    }
    return {**body, "digest": digest_of(body)}


def verify_launcher(plan_digest, seal_path=SEAL_PATH, launcher_file=ROOT / LAUNCHER_REL, verifier_file=Path(__file__).resolve()):
    """Lève SealError si le sceau est absent, illisible, mal formé, altéré, ou ne correspond pas."""
    try:
        seal = json.loads(Path(seal_path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SealError(f"sceau absent : {seal_path}") from exc
    except (OSError, ValueError) as exc:
        raise SealError(f"sceau illisible ({seal_path}) : {exc}") from exc
    if not isinstance(seal, dict) or set(seal) != set(FIELDS) or not all(isinstance(seal[key], str) for key in FIELDS):
        raise SealError("sceau mal formé")
    body = {key: value for key, value in seal.items() if key != "digest"}
    try:
        recomputed = digest_of(body)
    except Exception as exc:
        raise SealError(f"digest du sceau incalculable : {exc}") from exc
    if recomputed != seal["digest"]:
        raise SealError("digest du sceau altéré")
    if seal["schema"] != SCHEMA:
        raise SealError(f"schema inattendu : {seal['schema']!r}")
    if seal["plan_digest"] != plan_digest:
        raise SealError("le sceau ne correspond pas au digest du plan")
    for key, path, name in (("launcher_sha256", launcher_file, "lanceur"), ("verifier_sha256", verifier_file, "vérificateur")):
        try:
            actual = file_sha256(path)
        except OSError as exc:
            raise SealError(f"{name} illisible ({path}) : {exc}") from exc
        if actual != seal[key]:
            raise SealError(f"le sha256 du {name} diffère de celui du sceau")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(SEAL_PATH))
    args = parser.parse_args(argv)
    try:
        if Path(args.out).exists():
            raise FileExistsError(f"sceau déjà existant : {args.out}")
        plan = json.loads(Path(freeze.PLAN_PATH).read_text(encoding="utf-8"))
        if not isinstance(plan, dict):
            raise SealError("le plan canonique n'est pas un objet JSON")
        freeze.verify_plan(plan)
        seal = build_seal(plan["digest"])
        with open(args.out, "x", encoding="utf-8") as handle:
            handle.write(json.dumps(seal, indent=2) + "\n")
    except Exception as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
