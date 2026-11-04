"""Traits des candidats du rejeu CIRCUIT2 à budget 16 (graine 0, 1 génération).

Pour chaque candidat du premier appel de engine.improved_by, le script affiche
les traits (support, arity, nands, composed) recalculés, puis (priorité, admis)
donnés par circuit_procedure.run avec la procédure de départ. Il décrit ce qui
est observé dans ce rejeu, sans en tirer de conclusion. Sortie : JSON trié sur
stdout ; avec --out, le même JSON est écrit dans un fichier neuf sous results/.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.append(str(_ROOT))

try:
    import circuit2_budget16_diagnostic as diag
except ImportError:
    from scripts import circuit2_budget16_diagnostic as diag

from genesis import circuit_engine as engine
from genesis import circuit_procedure


def _appels(resultat):
    if isinstance(resultat, tuple):
        for partie in resultat:
            if isinstance(partie, list):
                return partie
    return resultat


def collect():
    appels = _appels(diag.run_replay())
    moteur, solutions = appels[0]["args"][0], appels[0]["args"][3]
    paires = list(engine.proposals(moteur, solutions))
    drapeaux = engine.composed_flags(moteur, solutions)
    procedure = circuit_procedure.seed_procedure()
    lignes = []
    for component, support in paires:
        nands = len(component.steps)
        arity = component.arity
        composed = drapeaux[component.key]
        traits_proc = circuit_procedure.traits_of(support, arity, nands, composed)
        priorite, admis, _portes = circuit_procedure.run(procedure, traits_proc)
        admis = bool(admis)
        traits = {
            "support": support,
            "arity": arity,
            "nands": nands,
            "composed": composed,
        }
        lignes.append({"admis": admis, "priorite": priorite, "traits": traits})
    return {
        "candidats": lignes,
        "nombre_candidats": len(lignes),
        "parametres": {"budget": 16, "generations": 1, "graine": 0},
    }


def _valider_sortie(chemin):
    """Valide un chemin relatif sous results/ ; lève ValueError sinon."""
    brut = str(chemin)
    norme = brut.replace("\\", "/")
    if not norme or norme.startswith("/") or Path(brut).is_absolute() or norme[1:2] == ":":
        raise ValueError("chemin absolu refusé : un chemin relatif sous results/ est requis")
    parties = norme.split("/")
    if ".." in parties:
        raise ValueError("chemin refusé : '..' interdit")
    parties = [p for p in parties if p not in ("", ".")]
    if len(parties) < 2 or parties[0] != "results":
        raise ValueError("chemin refusé : il doit désigner un fichier sous results/")
    relatif = Path(*parties)
    racine = (Path.cwd() / "results").resolve()
    if racine not in (Path.cwd() / relatif).resolve().parents:
        raise ValueError("chemin refusé : hors de results/")
    return relatif


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        metavar="CHEMIN",
        default=None,
        help="chemin relatif sous results/ où écrire le JSON (fichier neuf, jamais écrasé)",
    )
    args = parser.parse_args(argv)
    cible = None
    if args.out is not None:
        try:
            cible = _valider_sortie(args.out)
        except ValueError as exc:
            parser.error(str(exc))
    texte = json.dumps(collect(), indent=2, sort_keys=True) + "\n"
    if cible is not None:
        cible.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(cible, "x", encoding="utf-8", newline="\n") as fichier:
                fichier.write(texte)
        except FileExistsError:
            parser.error(f"fichier existant, écrasement refusé : {cible}")
    sys.stdout.write(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
