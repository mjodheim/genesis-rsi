"""Génération mécanique de la note de résultat négatif CIRCUIT2.

Lit le JSON d'adjudication complète, le plan préenregistré gelé et le fichier
de provenance, tous en lecture seule. Aucune valeur mesurée n'est écrite à la
main : tout comptage et toute valeur proviennent de ces fichiers.
"""

from __future__ import annotations

import ast
import argparse
import json
from pathlib import Path

DEFAULT_INPUT = Path("results/circuit2_adjudication_full.json")
DEFAULT_OUTPUT = Path("docs/CIRCUIT2_RESULTAT_NUL_2026-11-04_CORRIGE.md")
DEFAULT_PLAN = Path("experiment/engine/CIRCUIT2/PROCEDURE_PREREG_PLAN.json")
DEFAULT_PROVENANCE = Path("results/circuit2_provenance.json")
ABSENT = "absent du fichier"
NO_ARM = "(bras non renseigné)"
ROW_KEYS = ("rows", "results", "records", "runs")
META_KEYS = ("scale", "task_budget", "plan_digest", "machinery_commit")
FP_TOKENS = ("fingerprint", "digest", "hash", "sha")

# Raison d'arrêt anticipé : valeur lue dans STOP_REASON de
# scripts/run_circuit2_campaign.py, extraite par analyse syntaxique à
# l'exécution (le module n'est pas importé, rien n'est recopié à la main).
STOP_REASON_SOURCE = Path(__file__).resolve().parent / "run_circuit2_campaign.py"


def _frozen_stop_reason():
    try:
        tree = ast.parse(STOP_REASON_SOURCE.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        raise ValueError(f"STOP_REASON illisible dans {STOP_REASON_SOURCE.name} : {exc}") from exc
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if any(isinstance(t, ast.Name) and t.id == "STOP_REASON" for t in targets):
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
            break
    raise ValueError(f"STOP_REASON : constante chaîne introuvable dans {STOP_REASON_SOURCE.name}")


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


def _sorted_values(values):
    return sorted(values, key=_fmt)


def _plan_arm_names(plan):
    arms = plan.get("arms")
    if isinstance(arms, dict):
        return sorted(str(key) for key in arms)
    if not isinstance(arms, list):
        raise ValueError("plan : bras introuvables")
    names = []
    for item in arms:
        label = item
        if isinstance(item, dict):
            label = next((item[k] for k in ("name", "arm", "id") if k in item), None)
        if label is None:
            raise ValueError("plan : nom de bras introuvable")
        names.append(str(label))
    return sorted(names)


def validate_against_plan(data, plan):
    if not isinstance(plan, dict):
        raise ValueError("plan : objet JSON attendu")
    errors = []
    found, digest = _find(data, "plan_digest")
    if "digest" not in plan:
        errors.append("plan : champ digest absent")
    elif not found or digest != plan["digest"]:
        errors.append("plan_digest de l'adjudication différent du digest du plan")
    seeds = plan.get("seeds")
    if not isinstance(seeds, list):
        errors.append("plan : seeds absent ou non liste")
    else:
        found, data_seeds = _find(data, "seeds")
        if not found or not isinstance(data_seeds, list) or _sorted_values(data_seeds) != _sorted_values(seeds):
            errors.append("seeds de l'adjudication différentes de celles du plan")
    arms = _rows_by_arm(data)
    if sorted(arms) != _plan_arm_names(plan):
        errors.append("ensemble des bras de l'adjudication différent des bras du plan")
    elif isinstance(seeds, list):
        expected = _sorted_values(seeds)
        for name in sorted(arms):
            if _sorted_values([row.get("seed") for row in arms[name]]) != expected:
                errors.append(f"bras {name} : graines des lignes différentes de celles du plan")
    budgets = plan.get("budgets")
    if not isinstance(budgets, dict):
        errors.append("plan : budgets absent")
    else:
        for key in ("task_budget", "generations", "per_generation_limit"):
            if key == "generations":
                found = isinstance(data, dict) and key in data
                value = data[key] if found else None
            else:
                found, value = _find(data, key)
            if key not in budgets:
                errors.append(f"plan : budgets.{key} absent")
            elif type(budgets[key]) is not int:
                errors.append(f"plan : budgets.{key} doit être un entier")
            elif key == "generations" and not found:
                continue
            elif not found or type(value) is not int or value != budgets[key]:
                errors.append(f"{key} de l'adjudication différent de budgets du plan")
        if type(budgets.get("generations")) is int:
            planned = budgets["generations"]
            for name, rows in arms.items():
                for index, row in enumerate(rows):
                    value = row.get("generations")
                    where = f"bras {name}, ligne {index} : "
                    if type(value) is not int or not 1 <= value <= planned:
                        errors.append(
                            where + "generations absent, non entier ou hors de "
                            "1..budgets.generations du plan"
                        )
                    elif value < planned:
                        try:
                            expected_reason = _frozen_stop_reason()
                        except ValueError as exc:
                            errors.append(where + str(exc))
                            continue
                        if row.get("stop_reason") != expected_reason:
                            errors.append(
                                where + "arrêt anticipé (generations < budgets.generations) "
                                f"exige stop_reason == {expected_reason!r}"
                            )
    criterion = plan.get("criterion")
    if not isinstance(criterion, dict) or "thresholds" not in criterion or "text" not in criterion:
        errors.append("plan : criterion.thresholds et criterion.text requis")
    if errors:
        raise ValueError("adjudication incohérente avec le plan : " + " ; ".join(errors))


def _verdict(names, yields_by_arm, plan):
    flat = [y for n in names for y in yields_by_arm[n]]
    nonzero = {}
    for n in names:
        values = [y for y in yields_by_arm[n] if _is_number(y) and y != 0]
        if values:
            nonzero[n] = values
    lines = [
        "## (a) Résultat négatif",
        "",
        "Critère préenregistré, lu dans le plan gelé — seuils : "
        f"{_fmt(plan['criterion']['thresholds'])}.",
        "",
        f"Texte du critère : {plan['criterion']['text']}",
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
    "- Identité du code entre les commits cités dans la section provenance : non vérifié.",
    "- État de la CI : non vérifié.",
    "- `results/circuit2_campaign_full.json` : non relu en entier ; comptes non comparés, non vérifié.",
    "- Recalcul du digest du plan : non vérifié (égalité des champs seulement).",
]


PROVENANCE_FILES = (
    "circuit2_campaign_full.json",
    "circuit2_adjudication_s0-1_g6.json",
)
ADJUDICATION_FULL = "circuit2_adjudication_full.json"
NOT_VERIFIED = "non vérifié"
SUFFIXES = {
    "circuit2_campaign_full.json": " ; comptes non comparés (fichier non lu en entier), non vérifié",
    "circuit2_adjudication_s0-1_g6.json": " ; pilote (nom et commit connus seulement par la provenance), contenu non relu ici",
}


def _prov_entry(node, filename):
    if isinstance(node, dict):
        if any(isinstance(v, str) and v.endswith(filename) for v in node.values()):
            return node
        for key, value in node.items():
            if isinstance(key, str) and key.endswith(filename) and isinstance(value, dict):
                return value
        children = list(node.values())
    elif isinstance(node, list):
        children = node
    else:
        return None
    for child in children:
        entry = _prov_entry(child, filename)
        if entry is not None:
            return entry
    return None


def _pick(entry, token):
    for key in sorted(entry, key=lambda k: ("resolved" not in k.lower(), k)):
        if token in key.lower() and entry[key] is not None:
            return _fmt(entry[key])
    return NOT_VERIFIED


def _commits(entry):
    values = entry.get("valeurs")
    if not isinstance(values, list):
        return NOT_VERIFIED
    commits = sorted(
        {
            v["commit_resolu"]
            for v in values
            if isinstance(v, dict)
            and isinstance(v.get("commit_resolu"), str)
            and v["commit_resolu"]
        }
    )
    if not commits:
        return NOT_VERIFIED
    if len(commits) == 1:
        return _fmt(commits[0])
    return "valeurs multiples : " + _fmt(commits)


def _provenance_lines(data, plan, provenance):
    lines = [
        "## Provenance",
        "",
        "Source unique : `results/circuit2_provenance.json`. Tout ce que ce fichier "
        "n'établit pas est marqué « non vérifié ».",
        "",
    ]
    for filename in PROVENANCE_FILES:
        entry = _prov_entry(provenance, filename)
        if entry is None:
            status = f"absent de la provenance, {NOT_VERIFIED}"
        else:
            status = f"commit résolu {_commits(entry)}, verdict {_pick(entry, 'verdict')}"
        lines.append(f"- `results/{filename}` : {status}{SUFFIXES[filename]}")
    found, adjudicated = _find(data, "machinery_commit")
    entry = _prov_entry(provenance, ADJUDICATION_FULL)
    status = NOT_VERIFIED
    if entry is not None:
        status = f"commit résolu {_commits(entry)}, verdict {_pick(entry, 'verdict')}"
    lines.append(
        f"- `results/{ADJUDICATION_FULL}` : machinery_commit lu dans le fichier "
        f"{_fmt(adjudicated) if found else ABSENT} ; statut dans la provenance : {status}"
    )
    found, planned = _find(plan, "machinery_commit")
    lines.append(f"- machinery_commit du plan (lu dans le plan) : {_fmt(planned) if found else ABSENT}")
    lines.append(
        f"- Digest du plan : {_fmt(plan['digest'])}, égal au plan_digest de l'adjudication ; "
        "recalcul du digest : non vérifié"
    )
    lines.append("")
    return lines


def render(data, plan, provenance):
    validate_against_plan(data, plan)
    arms = _rows_by_arm(data)
    names = sorted(arms)
    lines = [
        "# CIRCUIT2 — note de résultat négatif",
        "",
        "Note générée mécaniquement à partir de `results/circuit2_adjudication_full.json`, "
        "du plan gelé et de `results/circuit2_provenance.json` (lecture seule).",
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
    lines += _verdict(names, yields_by_arm, plan)
    lines += _provenance_lines(data, plan, provenance)
    lines += LIMITS
    return "\n".join(lines) + "\n"


def run(
    input_path=DEFAULT_INPUT,
    output_path=DEFAULT_OUTPUT,
    plan_path=DEFAULT_PLAN,
    provenance_path=DEFAULT_PROVENANCE,
):
    src = Path(input_path)
    dst = Path(output_path)
    plan_src = Path(plan_path)
    prov_src = Path(provenance_path)
    if not src.is_file():
        raise FileNotFoundError(f"fichier d'entrée absent : {src}")
    for extra in (plan_src, prov_src):
        if not extra.is_file():
            raise FileNotFoundError(f"fichier d'entrée absent : {extra}")
    if dst.exists():
        raise FileExistsError(f"refus d'écraser le fichier existant : {dst}")
    text = render(
        json.loads(src.read_text(encoding="utf-8")),
        json.loads(plan_src.read_text(encoding="utf-8")),
        json.loads(prov_src.read_text(encoding="utf-8")),
    )
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return dst


def main(argv=None):
    parser = argparse.ArgumentParser(description="Génère la note CIRCUIT2 depuis le JSON d'adjudication.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--provenance", default=str(DEFAULT_PROVENANCE))
    args = parser.parse_args(argv)
    print(run(args.input, args.output, args.plan, args.provenance))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
