#!/usr/bin/env python3
"""Vérification de provenance des artefacts du circuit 2 (lecture seule).

Pour chaque fichier JSON sous results/ passé en argument, cherche
récursivement la clé « machinery_commit » et détermine, avec git uniquement,
si le commit référencé est un ancêtre de HEAD.

Contraintes : hors réseau, sans modèle, aucun accès à HELD_OUT, git appelé
par liste d'arguments (sans shell). Aucun verdict n'est inventé : toute
erreur git ou sortie inattendue donne « indetermine » avec le code de retour.

Commandes git exécutées :
  git rev-parse --verify --quiet <valeur>^{commit}
  git merge-base --is-ancestor <commit> HEAD
L'option --quiet sert uniquement à distinguer un objet inconnu (code 1)
d'une erreur fatale (code 128).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

CLE = "machinery_commit"
SORTIE_PAR_DEFAUT = "results/circuit2_provenance.json"
DELAI_GIT_S = 30

RE_OID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")


class CheminRefuse(ValueError):
    """Chemin refusé par la politique de lecture/écriture."""


def _env():
    env = dict(os.environ)
    for nom in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(nom, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _git(args, depot):
    try:
        res = subprocess.run(
            ["git", *args],
            cwd=str(depot),
            env=_env(),
            capture_output=True,
            text=True,
            timeout=DELAI_GIT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, "", type(exc).__name__
    return res.returncode, res.stdout, res.stderr


def valider_chemin(chemin, depot, doit_exister=True):
    """Retourne le chemin absolu validé ou lève CheminRefuse."""
    brut = Path(chemin)
    if ".." in brut.parts:
        raise CheminRefuse(f"'..' interdit : {chemin}")
    if any("HELD_OUT" in part.upper() for part in brut.parts):
        raise CheminRefuse(f"chemin interdit : {chemin}")
    candidat = brut if brut.is_absolute() else depot / brut
    racine = depot / "results"
    try:
        relatif = candidat.relative_to(racine)
    except ValueError:
        raise CheminRefuse(f"hors de results/ : {chemin}") from None
    if not relatif.parts:
        raise CheminRefuse(f"fichier attendu : {chemin}")
    if candidat.suffix != ".json":
        raise CheminRefuse(f"extension .json attendue : {chemin}")
    courant = racine
    if courant.is_symlink():
        raise CheminRefuse("results/ est un lien symbolique")
    for partie in relatif.parts:
        courant = courant / partie
        if courant.is_symlink():
            raise CheminRefuse(f"lien symbolique refusé : {chemin}")
    if doit_exister and not candidat.is_file():
        raise CheminRefuse(f"fichier introuvable : {chemin}")
    return candidat


def trouver_valeurs(objet, cle=CLE):
    """Valeurs de `cle` à toute profondeur (dicts et listes imbriqués)."""
    trouvees = []
    pile = [objet]
    while pile:
        courant = pile.pop()
        if isinstance(courant, dict):
            for k, v in courant.items():
                if k == cle:
                    trouvees.append(v)
                pile.append(v)
        elif isinstance(courant, list):
            pile.extend(courant)
    return trouvees


def _indetermine(valeur, raison, code, resolu=None):
    return {
        "valeur": valeur if isinstance(valeur, str) else repr(valeur),
        "commit_resolu": resolu,
        "verdict": "indetermine",
        "code_retour": code,
        "raison": raison,
    }


def verdict_commit(valeur, depot):
    if not isinstance(valeur, str) or not RE_OID.fullmatch(valeur):
        return _indetermine(valeur, "oid_complet_requis", None)
    code, sortie, _ = _git(
        ["rev-parse", "--verify", "--quiet", valeur + "^{commit}"], depot
    )
    if code is None:
        return _indetermine(valeur, "git_inexecutable", None)
    if code == 1 and not sortie.strip():
        return {
            "valeur": valeur,
            "commit_resolu": None,
            "verdict": "commit_inconnu",
            "code_retour": code,
        }
    resolu = sortie.strip()
    if code != 0 or not RE_OID.fullmatch(resolu):
        return _indetermine(valeur, "rev_parse_inattendu", code)
    if resolu != valeur:
        return _indetermine(valeur, "resolution_differente", code, resolu)
    code, _, _ = _git(["merge-base", "--is-ancestor", resolu, "HEAD"], depot)
    if code == 0:
        verdict = "ancetre_de_head"
    elif code == 1:
        verdict = "non_ancetre"
    else:
        return _indetermine(valeur, "merge_base_inattendu", code, resolu)
    return {
        "valeur": valeur,
        "commit_resolu": resolu,
        "verdict": verdict,
        "code_retour": code,
    }


def verifier_fichier(chemin, depot):
    depot = Path(depot).absolute()
    candidat = valider_chemin(chemin, depot)
    nom = candidat.relative_to(depot).as_posix()
    if candidat.stat().st_size == 0:
        return {
            "fichier": nom,
            "verdict": "indetermine",
            "code_retour": None,
            "raison": "fichier_vide",
            "valeurs": [],
        }
    try:
        with open(candidat, encoding="utf-8") as f:
            donnees = json.load(f)
    except (OSError, ValueError, RecursionError) as exc:
        return {
            "fichier": nom,
            "verdict": "indetermine",
            "code_retour": None,
            "raison": "json_illisible:" + type(exc).__name__,
            "valeurs": [],
        }
    valeurs = [verdict_commit(v, depot) for v in trouver_valeurs(donnees)]
    if not valeurs:
        verdict = "cle_absente"
    else:
        distincts = {v["verdict"] for v in valeurs}
        verdict = distincts.pop() if len(distincts) == 1 else "indetermine"
    resultat = {"fichier": nom, "verdict": verdict, "valeurs": valeurs}
    if verdict == "indetermine":
        premier = valeurs[0]
        homogene = all(v["verdict"] == "indetermine" for v in valeurs)
        resultat["raison"] = premier["raison"] if homogene else "verdicts_heterogenes"
        resultat["code_retour"] = premier["code_retour"] if homogene else None
    return resultat


def resoudre_head(depot):
    code, sortie, _ = _git(["rev-parse", "--verify", "HEAD^{commit}"], depot)
    head = sortie.strip()
    if code != 0 or not RE_OID.fullmatch(head):
        raise RuntimeError(f"HEAD non résolu (code de retour : {code})")
    return head


def ecrire_sortie(chemin, contenu):
    """Écrit en mode 'x' : refuse d'écraser un fichier existant."""
    with open(chemin, "x", encoding="utf-8") as f:
        json.dump(contenu, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def main(argv=None, depot=None):
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("fichiers", nargs="+", help="JSON sous results/")
    parseur.add_argument("--sortie", default=SORTIE_PAR_DEFAUT)
    args = parseur.parse_args(argv)
    racine = Path(depot) if depot else Path(__file__).resolve().parent.parent
    racine = racine.absolute()
    try:
        entrees = [valider_chemin(f, racine) for f in args.fichiers]
        sortie = valider_chemin(args.sortie, racine, doit_exister=False)
        head = resoudre_head(racine)
    except (CheminRefuse, RuntimeError) as exc:
        print(f"refus : {exc}", file=sys.stderr)
        return 2
    verdicts = [verifier_fichier(c, racine) for c in entrees]
    contenu = {
        "head": head,
        "fichiers_lus": [c.relative_to(racine).as_posix() for c in entrees],
        "verdicts": verdicts,
    }
    try:
        ecrire_sortie(sortie, contenu)
    except OSError as exc:
        print(f"écriture refusée : {exc}", file=sys.stderr)
        return 2
    print(json.dumps(contenu, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
