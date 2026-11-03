"""Diagnostic de vivacité de la lignée CIRCUIT2 (tâches LEARN seules).

Mesure, pour chaque couple (budget, graine), la dépense et la taille de la bibliothèque
au fil des générations. Aucune famille HELD_OUT ou CONTROL n'est lue.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import circuit_meta_lineage, circuit_tasks, trust_root  # noqa: E402

SCHEMA = "circuit2-lineage-liveness-v1"
BUDGETS = ((16, 1096), (64, 20000), (256, 80000))
SEEDS = (0, 1, 2)
GENERATIONS = 6
RESULTS_DIR = ROOT / "results"
DEFAULT_NAME = "circuit2_lineage_liveness.json"


class LivenessError(RuntimeError):
    """Entrée refusée : famille interdite, chemin non autorisé ou paramètre invalide."""


def _freeze_module():
    try:
        from scripts import freeze_circuit2_plan as module
        return module
    except ImportError:
        pass
    path = ROOT / "scripts" / "freeze_circuit2_plan.py"
    spec = importlib.util.spec_from_file_location("freeze_circuit2_plan", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("freeze_circuit2_plan", module)
    spec.loader.exec_module(module)
    return module


def _check_families(tasks):
    allowed = set(circuit_tasks.LEARN)
    refused = set(circuit_tasks.HELD_OUT) | set(getattr(circuit_tasks, "CONTROL", ()))
    for task in tasks:
        family = task.family
        if family in refused or family not in allowed:
            raise LivenessError(f"famille {family!r} refusée : seules les familles LEARN sont lues")


def _generation(state):
    # Repli documenté : "own" si la génération a son propre score ; sinon "parent"
    # (repli sur parent_score, score hérité du parent) ; None si les deux sont absents.
    # Le repli est tracé pour ne pas confondre les deux sources.
    score, parent = state["score"], state["parent_score"]
    if score is not None:
        solved = score[0]
        solved_source = "own"
    elif parent is not None:
        solved = parent[0]
        solved_source = "parent"
    else:
        solved = None
        solved_source = None
    spent = dict(state["spent"])
    return {
        "index": state["index"],
        "solved": solved,
        "solved_source": solved_source,
        "spend": spent,
        "spend_total": sum(spent.values()),
        "n_evaluated": len(state["evaluated"]),
        "adopted": bool(state["adopted"]),
        "exhausted": bool(state["exhausted"]),
        "library_size": len(state["library"]),
        "library_digest": trust_root.digest_of(state["library"]),
        "procedure_digest": state["procedure"]["procedure_digest"],
    }


def run(budgets=BUDGETS, seeds=SEEDS, generations=GENERATIONS, tasks=None):
    if tasks is None:
        tasks = _freeze_module().learn_tasks()
    tasks = list(tasks)
    _check_families(tasks)
    runs = []
    for task_budget, limit in budgets:
        for seed in seeds:
            states = circuit_meta_lineage.run_lineage(generations, tasks, task_budget, limit, seed)
            records = [_generation(state) for state in states[1:]]
            sizes = [record["library_size"] for record in records]
            runs.append(
                {
                    "task_budget": task_budget,
                    "per_generation_limit": limit,
                    "seed": seed,
                    "generations": records,
                    "synthesis_total": sum(r["spend"]["synthesis"] for r in records),
                    "adoptions_total": sum(1 for r in records if r["adopted"]),
                    "library_sizes": sizes,
                    "grows_after_generation_1": len(sizes) > 1 and max(sizes[1:]) > sizes[0],
                }
            )
    return {
        "schema": SCHEMA,
        "parameters": {
            "budgets": [list(pair) for pair in budgets],
            "seeds": list(seeds),
            "generations": generations,
        },
        "learn_task_count": len(tasks),
        "families": sorted({task.family for task in tasks}),
        # Garantie par construction : _check_families refuse toute famille hors LEARN
        # avant tout appel à run_lineage, donc cette valeur vaut 0 ; ce n'est pas un
        # comptage de lectures effectives.
        "held_out_families_in_input": sum(1 for task in tasks if task.family in circuit_tasks.HELD_OUT),
        "runs": runs,
    }


def _resolve_output(path):
    base = Path(RESULTS_DIR).resolve()
    target = Path(path).resolve()
    if base not in target.parents:
        raise LivenessError(f"chemin de sortie refusé (hors de {base}) : {target}")
    return target


def write_result(result, path):
    target = _resolve_output(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return target


def _parse_seeds(text):
    try:
        return tuple(int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("--seeds attend des entiers séparés par des virgules")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Diagnostic de vivacité de la lignée CIRCUIT2 (LEARN seul).")
    parser.add_argument("--out", default=None)
    parser.add_argument("--generations", type=int, default=GENERATIONS)
    parser.add_argument("--seeds", type=_parse_seeds, default=SEEDS)
    args = parser.parse_args(argv)
    out = Path(args.out) if args.out else Path(RESULTS_DIR) / DEFAULT_NAME
    try:
        target = _resolve_output(out)
        if args.generations < 1:
            raise LivenessError("--generations doit être >= 1")
        if not args.seeds:
            raise LivenessError("--seeds ne doit pas être vide")
        if target.exists():
            raise LivenessError(f"fichier de sortie déjà présent : {target}")
        result = run(seeds=args.seeds, generations=args.generations)
        write_result(result, out)
    except Exception as error:
        print(f"erreur : {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
