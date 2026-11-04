"""Traits des candidats du rejeu CIRCUIT2 à budget 16 (graine 0, 1 génération).

Pour chaque candidat du premier appel de engine.improved_by, le script affiche
les traits (support, arity, nands, composed) recalculés, puis (priorité, admis)
donnés par circuit_procedure.run avec la procédure de départ. Il décrit ce qui
est observé dans ce rejeu, sans en tirer de conclusion. Sortie : JSON trié sur
stdout uniquement, aucun fichier écrit.
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
        composed = drapeaux.get(component.key, False)
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


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    sys.stdout.write(json.dumps(collect(), indent=2, sort_keys=True, default=str) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
