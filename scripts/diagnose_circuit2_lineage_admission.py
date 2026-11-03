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


def _resolve(name):
    for module in (cp, lineage, engine, liveness):
        if hasattr(module, name):
            return getattr(module, name)
    raise DiagnosticError(f"symbole introuvable : {name}")


def _key(vector):
    if isinstance(vector, int):
        return int(vector)
    return tuple(int(bit) for bit in vector)


def _universe(sample):
    width = len(cp.TRAITS)
    if isinstance(sample, int):
        return list(range(1 << width))
    make = list if isinstance(sample, list) else tuple
    return [make(bits) for bits in itertools.product((0, 1), repeat=width)]


def admission():
    traits_of = _resolve("traits_of")
    cap = _resolve("SUPPORT_CAP")
    max_steps = _resolve("MAX_STEPS")
    seed = cp.seed_procedure()
    reachable = {}
    calls = 0
    for composed in (False, True):
        for size in range(max_steps + 1):
            arity = 2 + min(2, 4 * size // 65)
            nands = 1 + min(7, 8 * size // 65)
            for support in range(SUPPORT_RANGE + 1):
                vector = traits_of(min(support, cap), arity, nands, composed)
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
            "support_cap": cap,
            "taille": [0, max_steps],
        },
        "vecteurs_total": len(universe),
    }


def _plain(score):
    return list(score) if isinstance(score, (list, tuple)) else score


def _beats(score, reference):
    try:
        return tuple(score) > tuple(reference)
    except TypeError:
        return False


def replay():
    """Rejoue la génération 1 en capturant les scores via une enveloppe en mémoire."""
    calls = []
    original = engine.improved_by

    def wrapper(*args, **kwargs):
        result = original(*args, **kwargs)
        procedure = args[4] if len(args) > 4 else kwargs["procedure"]
        info = result[2] if len(result) > 2 else None
        calls.append(
            {
                "digest": cp.to_record(procedure)["procedure_digest"],
                "exhausted": info.get("exhausted") if isinstance(info, dict) else None,
                "score": _plain(result[1]),
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
    report = {
        "attendu": {**EXPECTED, "library_digest_prefixe": LIBRARY_PREFIX},
        "ecarts": sorted(gaps),
        "fidelity_ok": not gaps,
        "observe": observed,
        "parametres": dict(REPLAY),
    }
    if gaps:
        return report
    if not calls:
        raise DiagnosticError("aucun appel à improved_by capturé")
    parent, candidates = calls[0], calls[1:]
    better = [c["digest"] for c in candidates if not c["exhausted"] and _beats(c["score"], parent["score"])]
    report.update(
        {
            "adopted": record.get("adopted"),
            "adoption_stricte_explique_absence": record.get("adopted") is False and not better,
            "candidats": candidates,
            "candidats_strictement_meilleurs": better,
            "parent": parent,
            "scores_tous_egaux": all(c["score"] == parent["score"] for c in candidates),
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
