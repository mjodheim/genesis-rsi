"""Diagnostic en lecture seule de l'admission des candidats de la lignée CIRCUIT2.

Aucun module gelé n'est modifié : circuit_engine.improved_by est enveloppé en mémoire,
puis restauré dans un bloc finally. Sortie : JSON trié sur stdout, ou --out vers un
nouveau fichier sous results/ (mode 'x').
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import circuit_engine as engine  # noqa: E402
from genesis import circuit_meta_lineage as lineage  # noqa: E402
from genesis import circuit_procedure as cp  # noqa: E402

try:
    import circuit2_lineage_liveness as liveness  # noqa: E402
except ImportError:
    from scripts import circuit2_lineage_liveness as liveness  # noqa: E402

SCHEMA = "circuit2-lineage-admission-diagnostic-v1"
RESULTS_DIR = ROOT / "results"
PROTECTED = "circuit2_lineage_liveness.json"
REPLAY = {"budget": 256, "generations": 1, "limit": 80000, "seed": 100}
EXPECTED = {
    "n_evaluated": 5,
    "solved": 5,
    "evaluations": 21529,
    "procedure": 813,
    "synthesis": 12,
}
LIBRARY_PREFIX = "2fd1cbc5"
SUPPORT_RANGE = 8


class DiagnosticError(Exception):
    """Refus d'écriture ou symbole introuvable."""


def _key(vector):
    if isinstance(vector, int):
        return int(vector)
    return tuple(int(bit) for bit in vector)


def _universe(sample):
    width = len(cp.TRAITS)
    if isinstance(sample, bool) or not isinstance(sample, (int, list, tuple)):
        raise DiagnosticError(f"type de vecteur inattendu : {type(sample).__name__}")
    if isinstance(sample, int):
        return list(range(1 << width))
    if len(sample) != width or any(not isinstance(bit, int) or bit not in (0, 1) for bit in sample):
        raise DiagnosticError("vecteur inattendu : longueur différente de len(cp.TRAITS) ou valeur hors {0, 1}")
    make = list if isinstance(sample, list) else tuple
    return [make(bits) for bits in itertools.product((0, 1), repeat=width)]


def admission():
    if SUPPORT_RANGE > lineage.SUPPORT_CAP:
        raise DiagnosticError(
            f"SUPPORT_RANGE={SUPPORT_RANGE} dépasse lineage.SUPPORT_CAP={lineage.SUPPORT_CAP}"
        )
    seed = cp.seed_procedure()
    reachable = {}
    calls = 0
    for composed in (False, True):
        for size in range(cp.MAX_STEPS + 1):
            for support in range(SUPPORT_RANGE + 1):
                vector = lineage._traits(size, support, composed)
                reachable.setdefault(_key(vector), vector)
                calls += 1
    universe = _universe(next(iter(reachable.values())))
    admitted = sum(1 for vector in universe if cp.run(seed, vector)[1])
    reachable_admitted = sum(1 for vector in reachable.values() if cp.run(seed, vector)[1])
    return {
        "admis": admitted,
        "atteignables_admis": reachable_admitted,
        "atteignables_distincts": len(reachable),
        "borne_enumeration": {
            "appels": calls,
            "composed": [False, True],
            "support": [0, SUPPORT_RANGE],
            "support_cap": lineage.SUPPORT_CAP,
            "taille": [0, cp.MAX_STEPS],
        },
        "vecteurs_total": len(universe),
    }


def _beats(score, reference):
    try:
        return tuple(score) > tuple(reference)
    except TypeError:
        return False


def analyse(calls, adopted):
    """Analyse pure des appels capturés (parent d'abord, puis candidats de la shortlist).

    Règle reprise de circuit_meta_lineage.step : un candidat est adopté si _score(got) > chosen_score
    (tuple strictement supérieur), et un candidat dont trial['exhausted'] est vrai n'est jamais
    comparé. Un TypeError de comparaison (scores incomparables) vaut « pas meilleur ».
    """
    parent, candidates = calls[0], calls[1:]
    better = [c["digest"] for c in candidates if not c["exhausted"] and _beats(c["score"], parent["score"])]
    return {
        "adoption_stricte_explique_absence": adopted is False and not better,
        "candidats": candidates,
        "candidats_strictement_meilleurs": better,
        "parent": parent,
        "scores_tous_egaux": bool(candidates) and all(c["score"] == parent["score"] for c in candidates),
    }


def replay():
    """Rejoue la génération 1 en capturant les scores via une enveloppe en mémoire.

    Lecture de circuit_meta_lineage.step : le premier appel à engine.improved_by est l'étape (a),
    dont le résultat « after » donne parent_score = _score(after) = engine.measure(after) ; les appels
    suivants sont les candidats de la shortlist. Le score est donc recalculé par
    engine.measure(result[1]) : result[1] contient les solutions, pas le score.
    """
    calls = []
    original = engine.improved_by

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        if len(args) > 4:
            procedure = args[4]
        elif "procedure" in kwargs:
            procedure = kwargs["procedure"]
        else:
            raise DiagnosticError("procédure absente de l'appel à improved_by")
        info = result[2] if len(result) > 2 else None
        if not (isinstance(info, dict) and "exhausted" in info):
            raise DiagnosticError("info sans clé 'exhausted' dans le résultat de improved_by")
        calls.append(
            {
                "digest": cp.to_record(procedure)["procedure_digest"],
                "exhausted": bool(info["exhausted"]),
                "score": list(engine.measure(result[1])),
            }
        )
        return result

    engine.improved_by = wrapper
    try:
        output = liveness.run(
            budgets=((REPLAY["budget"], REPLAY["limit"]),),
            seeds=(REPLAY["seed"],),
            generations=REPLAY["generations"],
        )
    finally:
        engine.improved_by = original
    record = output["runs"][0]["generations"][0]
    spend = record.get("spend") or {}
    observed = {
        "n_evaluated": record.get("n_evaluated"),
        "solved": record.get("solved"),
        "evaluations": spend.get("evaluations"),
        "procedure": spend.get("procedure"),
        "synthesis": spend.get("synthesis"),
        "library_digest": record.get("library_digest"),
    }
    gaps = [name for name, value in EXPECTED.items() if observed[name] != value]
    digest = observed["library_digest"]
    if not (isinstance(digest, str) and digest.startswith(LIBRARY_PREFIX)):
        gaps.append("library_digest")
    seed_digest = cp.to_record(cp.seed_procedure())["procedure_digest"]
    if not calls or calls[0]["digest"] != seed_digest:
        gaps.append("digest_parent")
    if len(calls) - 1 != observed["n_evaluated"]:
        gaps.append("appels_candidats")
    report = {
        "attendu": {**EXPECTED, "library_digest_prefixe": LIBRARY_PREFIX},
        "ecarts": sorted(gaps),
        "fidelity_ok": not gaps,
        "observe": observed,
        "parametres": dict(REPLAY),
    }
    if gaps:
        return report
    report.update(
        {
            "adopted": record.get("adopted"),
            **analyse(calls, record.get("adopted")),
        }
    )
    return report


def build_report():
    return {"admission": admission(), "rejeu": replay(), "schema": SCHEMA}


def _target(raw):
    path = Path(raw).resolve()
    root = RESULTS_DIR.resolve()
    if root not in path.parents:
        raise DiagnosticError("la sortie doit être sous results/")
    if path == root / PROTECTED:
        raise DiagnosticError(f"écrasement refusé : {PROTECTED}")
    if path.exists():
        raise DiagnosticError(f"fichier existant : {path.name}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", help="nouveau fichier JSON sous results/")
    args = parser.parse_args(argv)
    try:
        target = _target(args.out) if args.out else None
        text = json.dumps(build_report(), indent=2, sort_keys=True) + "\n"
        if target is None:
            sys.stdout.write(text)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "x", encoding="utf-8") as handle:
                handle.write(text)
    except (DiagnosticError, FileExistsError) as error:
        sys.stderr.write(f"refus : {error}\n")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
