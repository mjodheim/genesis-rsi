#!/usr/bin/env python3
"""Vérificateur indépendant de l'identité des exécutables CIRCUIT2.

Lit EXECUTABLES.json, recalcule les sha256 des exécutables listés dans
scripts/freeze_circuit2_executables.py (compute_manifest, global_digest) et
refuse toute divergence avant que run_circuit2_campaign ne soit importé.

Format du manifeste écrit par le gel : un objet « files » (chemin relatif -> sha256)
et un champ « digest » (défaut : experiment/engine/CIRCUIT2/EXECUTABLES.json).

Limite : ce vérificateur ne figure pas dans le manifeste gelé ; il ne prouve
donc pas sa propre identité. Seul un sceau externe le ferait.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
RACINE_DEFAUT = SCRIPTS_DIR.parent
NOM_MANIFESTE = "EXECUTABLES.json"
CHEMIN_MANIFESTE_DEFAUT = Path("experiment") / "engine" / "CIRCUIT2" / NOM_MANIFESTE
NOM_GEL = "freeze_circuit2_executables"
NOM_LANCEUR = "run_circuit2_campaign"


class ExecutableIdentityError(Exception):
    """Identité des exécutables non vérifiée ou divergente."""


def _charger_gel():
    if NOM_GEL in sys.modules:
        return sys.modules[NOM_GEL]
    chemin = SCRIPTS_DIR / (NOM_GEL + ".py")
    spec = importlib.util.spec_from_file_location(NOM_GEL, chemin)
    if spec is None or spec.loader is None:
        raise ExecutableIdentityError(f"Module de gel introuvable : {chemin}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[NOM_GEL] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(NOM_GEL, None)
        raise ExecutableIdentityError(f"Module de gel inutilisable : {exc}") from exc
    return module


def _fichiers(objet, origine):
    if isinstance(objet, dict) and isinstance(objet.get("files"), dict):
        objet = objet["files"]
    if not isinstance(objet, dict):
        raise ExecutableIdentityError(f"Format inattendu ({origine}).")
    return {str(k): str(v) for k, v in objet.items()}


def _lire_manifeste(chemin):
    if not chemin.is_file():
        raise ExecutableIdentityError(f"Manifeste absent : {chemin}")
    try:
        donnees = json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ExecutableIdentityError(f"Manifeste illisible : {chemin} ({exc})") from exc
    if not isinstance(donnees, dict):
        raise ExecutableIdentityError(f"Manifeste illisible : {chemin} (objet attendu)")
    return donnees


def verify_manifest(manifest_path=None, root=None):
    """Renvoie [] si tout est identique ; lève ExecutableIdentityError sinon."""
    racine = Path(root) if root is not None else RACINE_DEFAUT
    chemin = Path(manifest_path) if manifest_path is not None else racine / CHEMIN_MANIFESTE_DEFAUT
    donnees = _lire_manifeste(chemin)
    publies = _fichiers(donnees, "manifeste")
    gel = _charger_gel()
    if gel.global_digest(publies) != donnees.get("digest"):
        raise ExecutableIdentityError("Digest global du manifeste incohérent avec ses fichiers.")
    attendus = {str(n) for n in gel.EXECUTABLES}
    chemins = tuple(sorted(attendus))
    en_trop = sorted(set(publies) - attendus)
    en_moins = sorted(attendus - set(publies))
    if en_trop:
        raise ExecutableIdentityError("Fichier(s) en trop dans le manifeste : " + ", ".join(en_trop))
    if en_moins:
        raise ExecutableIdentityError("Fichier(s) manquant(s) dans le manifeste : " + ", ".join(en_moins))
    absents = sorted(n for n in attendus if not (racine / n).is_file())
    if absents:
        raise ExecutableIdentityError("Fichier(s) exécutable(s) absent(s) : " + ", ".join(absents))
    try:
        calcules = _fichiers(gel.compute_manifest(racine, chemins), "recalcul")
    except OSError as exc:
        raise ExecutableIdentityError(f"Lecture impossible des exécutables : {exc}") from exc
    if set(calcules) != attendus:
        raise ExecutableIdentityError("Le recalcul ne couvre pas exactement EXECUTABLES.")
    divergents = sorted(n for n in attendus if calcules[n] != publies[n])
    if divergents:
        raise ExecutableIdentityError("Empreinte sha256 différente pour : " + ", ".join(divergents))
    return []


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        verify_manifest()
    except ExecutableIdentityError as exc:
        print(f"Refus : {exc}", file=sys.stderr)
        return 2
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    lanceur = importlib.import_module(NOM_LANCEUR)
    resultat = lanceur.main(args)
    return int(resultat) if resultat is not None else 0


if __name__ == "__main__":
    sys.exit(main())
