"""Génération mécanique de la note de résultat négatif CIRCUIT2.

Seul le JSON d'adjudication complète est lu. Aucune valeur mesurée n'est
écrite à la main : tout comptage et toute valeur proviennent du fichier.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_INPUT = Path("results/circuit2_adjudication_full.json")
DEFAULT_OUTPUT = Path("docs/CIRCUIT2_RESULTAT_NUL_2026-11-04.md")
ABSENT = "absent du fichier"
NO_ARM = "(bras non renseigné)"
ROW_KEYS = ("rows", "results", "records", "runs")
META_KEYS = ("scale", "task_budget", "plan_digest", "machinery_commit")
FP_TOKENS = ("fingerprint", "digest", "hash", "sha")


def _check_rows(rows):
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("ligne d'adjudication inattendue : objet JSON attendu")
    return list(rows)


def _group(rows):
    arms = {}
    for row in _check_rows(rows):
        name = row.get("arm")
        arms.setdefault(NO_ARM if name is None else str(name), []).append(row)
    return arms


def _list_in(node):
    if isinstance(node, list):
        return node
    if isinstance(node, dict):
        for key in ROW_KEYS:
            if isinstance(node.get(key), list):
                return node[key]
    return None


def _rows_by_arm(data):
    if isinstance(data, list):
        return _group(data)
    if isinstance(data, dict):
        for key in ROW_KEYS:
            if isinstance(data.get(key), list):
                return _group(data[key])
        arms = data.get("arms")
        if isinstance(arms, list):
            return _group(arms)
        if isinstance(arms, dict):
            out = {}
            for name, node in arms.items():
                rows = _list_in(node)
                if rows is None:
                    raise ValueError(f"bras {name} : lignes introuvables")
                out[str(name)] = _check_rows(rows)
            return out
    raise ValueError("structure du JSON non reconnue : lignes par bras introuvables")


def _find(node, key):
    if isinstance(node, dict):
        if key in node:
            return True, node[key]
        children = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        return False, None
    for child in children:
        found, value = _find(child, key)
        if found:
            return True, value
    return False, None


def _fmt(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fingerprint(row):
    for key in sorted(row):
        low = key.lower()
        if "library" in low and any(t in low for t in FP_TOKENS):
            if row[key] is not None:
                return str(row[key])
    return None


def _arm_lines(name, rows):
    reasons = sorted({str(r["stop_reason"]) for r in rows if r.get("stop_reason") is not None})
    prints = sorted({fp for fp in map(_fingerprint, rows) if fp is not None})
    yields = [r.get("held_out_yield") for r in rows]
    lines = [
        f"### Bras {name}",
        "",
        f"- Nombre de lignes : {len(rows)}",
        f"- held_out_yield (ordre du fichier, null si absent) : {_fmt(yields)}",
        f"- stop_reason (ensemble) : {', '.join(reasons) if reasons else ABSENT}",
    ]
    if prints:
        shown = ", ".join(p[:8] for p in prints)
        lines.append(f"- Empreintes de bibliothèque distinctes : {len(prints)} (préfixes : {shown})")
    else:
        lines.append(f"- Empreintes de bibliothèque distinctes : 0 ({ABSENT})")
    lines.append("")
    return lines


def _verdict(names, yields_by_arm):
    flat = [y for n in names for y in yields_by_arm[n]]
    nonzero = {}
    for n in names:
        values = [y for y in yields_by_arm[n] if _is_number(y) and y != 0]
        if values:
            nonzero[n] = values
    lines = [
        "## (a) Résultat négatif",
        "",
        "Critère préenregistré : >=10 points, >=16 graines sur 20, ablation. "
        "Aucun critère n'a été assoupli.",
        "",
    ]
    if flat and all(_is_number(y) and y == 0 for y in flat):
        lines.append(
            "Aucun gain : tous les rendements held_out_yield calculés sont nuls. "
            "Le critère préenregistré n'est pas atteint."
        )
    elif nonzero:
        lines.append(
            "Des rendements held_out_yield non nuls figurent dans le fichier. Ils sont "
            "décrits ci-dessous sans conclure à une amélioration ; le critère "
            "préenregistré n'est pas évalué par cette note."
        )
        lines.append("")
        for n in names:
            if n in nonzero:
                lines.append(f"- Bras {n} : valeurs non nulles {_fmt(nonzero[n])}")
    else:
        lines.append(
            "Rendements held_out_yield absents ou non numériques : "
            "aucune conclusion n'est tirée."
        )
    lines.append("")
    return lines


LIMITS = [
    "## (b) Limites",
    "",
    "- Identité du code d'adjudication entre 245661e0 et c993a2f4 : non vérifié.",
    "- Statut de `results/circuit2_adjudication_s0-1_g6.json` par rapport à main : "
    "non vérifié (à reconfirmer par `git diff main`).",
    "- État de la CI : non vérifié.",
    "- `results/circuit2_campaign_full.json` : non relu en entier, non vérifié ; "
    "voir `results/circuit2_campaign_full_counts.json`, dont aucune valeur n'est citée ici.",
]


def render(data):
    arms = _rows_by_arm(data)
    names = sorted(arms)
    lines = [
        "# CIRCUIT2 — note de résultat négatif",
        "",
        "Note générée mécaniquement à partir de `results/circuit2_adjudication_full.json`.",
        "",
        "## Paramètres lus dans le fichier",
        "",
    ]
    for key in META_KEYS:
        found, value = _find(data, key)
        lines.append(f"- {key} : {_fmt(value) if found else ABSENT}")
    lines += ["", "## Données par bras", ""]
    for name in names:
        lines += _arm_lines(name, arms[name])
    yields_by_arm = {n: [r.get("held_out_yield") for r in arms[n]] for n in names}
    lines += _verdict(names, yields_by_arm)
    lines += LIMITS
    return "\n".join(lines) + "\n"


def run(input_path=DEFAULT_INPUT, output_path=DEFAULT_OUTPUT):
    src = Path(input_path)
    dst = Path(output_path)
    if not src.is_file():
        raise FileNotFoundError(f"fichier d'entrée absent : {src}")
    if dst.exists():
        raise FileExistsError(f"refus d'écraser le fichier existant : {dst}")
    text = render(json.loads(src.read_text(encoding="utf-8")))
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return dst


def main(argv=None):
    parser = argparse.ArgumentParser(description="Génère la note CIRCUIT2 depuis le JSON d'adjudication.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    print(run(args.input, args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
