#!/usr/bin/env python3
"""Synthèse factuelle de results/circuit2_campaign_full.json.

Lecture seule de l'entrée ; sortie écrite en mode 'x' sous results/.
Aucun calcul de performance, aucun accès à HELD_OUT, aucun réseau.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
DEFAULT_INPUT = RESULTS_DIR / "circuit2_campaign_full.json"
DEFAULT_OUTPUT = RESULTS_DIR / "circuit2_campaign_summary.json"
NON_DEDUCTIBLE = "non_deductible"
GENERATION_KEYS = ("generations", "records", "history")


def _get(mapping, key):
    if isinstance(mapping, dict):
        return mapping.get(key)
    return None


def _changed(digests):
    return len({d for d in digests if d is not None}) >= 2


def summarize_run(run):
    if not isinstance(run, dict):
        raise ValueError("run invalide : objet JSON attendu")
    records = None
    for key in GENERATION_KEYS:
        if isinstance(run.get(key), list):
            records = run[key]
            break
    if records is None:
        raise ValueError("run sans liste de générations")
    last = _get(records[-1], "transmission") if records else None
    library = [_get(r, "library_digest") for r in records]
    library.append(_get(last, "library_digest"))
    procedure = [_get(r, "procedure_digest") for r in records]
    procedure.append(_get(last, "procedure_digest"))
    adoption = []
    deductible = True
    for index, record in enumerate(records):
        own = _get(record, "digest")
        transmitted = _get(_get(record, "transmission"), "digest")
        if own is None or transmitted is None:
            deductible = False
        elif own != transmitted:
            adoption.append(index)
    return {
        "library_digests": library,
        "library_changed": _changed(library),
        "procedure_digests": procedure,
        "procedure_changed": _changed(procedure),
        "adoption": adoption if deductible else NON_DEDUCTIBLE,
        "generations_run": run.get("generations_run"),
        "stop_reason": run.get("stop_reason"),
    }


def _seed_runs(value):
    if isinstance(value, dict) and isinstance(value.get("seeds"), (dict, list)):
        value = value["seeds"]
    if isinstance(value, dict):
        return [(str(k), v) for k, v in value.items()]
    if isinstance(value, list):
        return [
            (str(v.get("seed", i)) if isinstance(v, dict) else str(i), v)
            for i, v in enumerate(value)
        ]
    raise ValueError("bras invalide")


def _arms_of(data):
    if isinstance(data, list):
        arms = {}
        for run in data:
            if not isinstance(run, dict) or "arm" not in run:
                raise ValueError("run sans champ 'arm'")
            arms.setdefault(str(run["arm"]), []).append(run)
        return arms
    if isinstance(data, dict):
        arms = data.get("arms", data)
        if isinstance(arms, dict):
            return {str(k): v for k, v in arms.items() if isinstance(v, (dict, list))}
    raise ValueError("structure de campagne non reconnue")


def summarize(data):
    arms_out = {}
    for arm, value in _arms_of(data).items():
        seeds = {seed: summarize_run(run) for seed, run in _seed_runs(value)}
        listed = [s["adoption"] for s in seeds.values()]
        arms_out[arm] = {
            "seeds": seeds,
            "summary": {
                "n_seeds": len(seeds),
                "seeds_library_changed": sum(
                    1 for s in seeds.values() if s["library_changed"]
                ),
                "seeds_adoption": sum(
                    1 for a in listed if isinstance(a, list) and a
                ),
                "seeds_adoption_non_deductible": sum(
                    1 for a in listed if a == NON_DEDUCTIBLE
                ),
            },
        }
    return {"arms": arms_out}


def resolve_output(output, results_dir=RESULTS_DIR):
    base = Path(os.path.abspath(results_dir))
    candidate = Path(output)
    if ".." in candidate.parts:
        raise ValueError("'..' refusé dans le chemin de sortie")
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    candidate = Path(os.path.abspath(candidate))
    if candidate == base or base not in candidate.parents:
        raise ValueError("sortie hors de results/")
    current = base
    if current.is_symlink():
        raise ValueError("lien symbolique refusé")
    for part in candidate.relative_to(base).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("lien symbolique refusé")
    return candidate


def write_summary(summary, output, results_dir=RESULTS_DIR):
    target = resolve_output(output, results_dir)
    with open(target, "x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    try:
        with open(args.input, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        target = write_summary(summarize(data), args.output)
    except (OSError, ValueError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    print(f"synthèse écrite : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
