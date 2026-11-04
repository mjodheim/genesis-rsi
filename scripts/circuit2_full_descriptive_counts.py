#!/usr/bin/env python3
"""Comptages descriptifs de la campagne circuit2 complète (lecture seule).

Hors réseau, sans modèle. Ne lit que results/circuit2_campaign_full.json
(aucun accès à HELD_OUT) et écrit results/circuit2_campaign_full_counts.json
sans jamais écraser un fichier existant.

Un résultat constant est un résultat négatif conservé : ces comptages sont
purement descriptifs et ne modifient aucun critère gelé.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ARMS = ("inherited_lineage", "frozen_engine", "fixed_procedure", "random_procedure")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = ROOT / "results" / "circuit2_campaign_full.json"
DEFAULT_OUTPUT = ROOT / "results" / "circuit2_campaign_full_counts.json"


def _ordered_generations(entry: dict) -> list:
    generations = sorted(entry["generations"], key=lambda g: g["index"])
    if not generations:
        raise ValueError(f"graine {entry.get('seed')!r} sans génération")
    return generations


def _score(generation: dict) -> tuple:
    return tuple(generation["score"])


def count_arm(entries: list) -> dict:
    last_differs = 0
    changes = 0
    histogram: dict = {}
    distinct_scores: set = set()
    for entry in entries:
        generations = _ordered_generations(entry)
        scores = [_score(g) for g in generations]
        if scores[-1] != scores[0]:
            last_differs += 1
        if any(a != b for a, b in zip(scores, scores[1:])):
            changes += 1
        digests = {g["transmission"]["digest"] for g in generations}
        key = str(len(digests))
        histogram[key] = histogram.get(key, 0) + 1
        distinct_scores.update(scores)
    return {
        "n_seeds": len(entries),
        "seeds_last_differs_from_gen0": last_differs,
        "seeds_score_changes_at_least_once": changes,
        "distinct_transmission_digests_per_seed_histogram": histogram,
        "distinct_scores": [list(s) for s in sorted(distinct_scores)],
    }


def compute_counts(data: dict) -> dict:
    arms = data["arms"]
    missing = [a for a in ARMS if a not in arms]
    if missing:
        raise KeyError(f"bras absents : {missing}")
    return {"arms": {arm: count_arm(arms[arm]) for arm in ARMS}}


def run(input_path: Path, output_path: Path) -> dict:
    input_path = Path(input_path)
    output_path = Path(output_path)
    if not input_path.is_file():
        raise FileNotFoundError(f"fichier d'entrée absent : {input_path}")
    if output_path.exists():
        raise FileExistsError(f"refus d'écraser : {output_path}")
    with input_path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    result = compute_counts(data)
    text = json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    with output_path.open("x", encoding="utf-8") as fh:
        fh.write(text)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    try:
        run(args.input, args.output)
    except (FileNotFoundError, FileExistsError, KeyError, ValueError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
