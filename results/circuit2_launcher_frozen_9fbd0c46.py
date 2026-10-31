"""Lanceur hors réseau de la campagne CIRCUIT2, conforme au plan gelé.

Exécute les quatre bras sur les seules tâches LEARN du plan vérifié. Ne calcule ni
gain, ni rendement, ni succès : l'adjudication exige l'évaluation tenue à l'écart.

Rattachement au plan canonique : seul un plan dont le digest est identique à celui du
fichier publié (CANONICAL_PLAN_PATH, relu et vérifié) est exécuté ; aucun repli.

Règle d'arrêt effective : le plan impose l'arrêt après une génération épuisée sans adoption.
Chaque couple bras/graine est porté par un ArmRun persistant (fabrique new_run) qui reprend
l'initialisation et le corps de boucle de arms.run_arm ; step() exécute UNE génération.
Le lanceur appelle step() au plus count fois et teste _stops(record) après chaque génération :
si exhausted est vrai et transmission.digest == digest (ni changement de bibliothèque ni de
procédure, donc aucune adoption), il s'arrête immédiatement, sans aucun step supplémentaire ;
sinon il s'arrête à count. Il n'y a plus de rejeu : chaque génération est exécutée une seule
fois, et la dépense publiée est la dépense exécutée. Ni arms.run_arm ni arms.run_all ne sont
appelés par le lanceur.
L'adoption est déduite uniquement de la comparaison des deux digests (digest de
l'enregistrement et digest de sa transmission) ; si l'un des deux manque, l'adoption n'est
pas déductible : rien n'est supposé ni tronqué. Les bras et les graines sont isolés.
Champs ajoutés à chaque exécution : stopped_early (la règle a joué), stop_reason
('exhausted_without_adoption' ou 'generation_limit') et generations_run, égal au nombre
de générations réellement exécutées (nombre de appels à step()).
Champs de score d'une génération : score = bibliothèque transmise (parent_score) et selection_score =
score de la procédure candidate (state["score"]) pour inherited_lineage ; None pour les trois autres bras.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _path in (HERE, HERE.parent):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import freeze_circuit2_plan as freeze  # noqa: E402
import run_circuit2_arms as arms  # noqa: E402

PlanError = freeze.PlanError
CANONICAL_PLAN_PATH = freeze.PLAN_PATH
STOP_REASON = "exhausted_without_adoption"
LIMIT_REASON = "generation_limit"


def _read_plan(path):
    try:
        plan = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PlanError(f"plan illisible ({path}) : {exc}") from exc
    if not isinstance(plan, dict):
        raise PlanError("le plan n'est pas un objet JSON")
    return plan


def _verify(plan):
    try:
        freeze.verify_plan(plan)
    except PlanError:
        raise
    except Exception as exc:
        raise PlanError(f"vérification du plan impossible : {exc}") from exc


def canonical_digest(path=None):
    """Digest du plan publié, relu et vérifié ; fichier absent ou invalide => PlanError."""
    plan = _read_plan(CANONICAL_PLAN_PATH if path is None else path)
    _verify(plan)
    return plan.get("digest")


def check_plan(plan):
    """Vérifie le plan en soi, puis exige l'identité de son digest avec le canonique."""
    if not isinstance(plan, dict):
        raise PlanError("le plan n'est pas un objet JSON")
    _verify(plan)
    expected = canonical_digest()
    if plan.get("digest") != expected:
        raise PlanError("le digest du plan diffère de celui du plan canonique publié")
    return plan


def load_plan(path=None):
    """Lit un plan scellé, le vérifie et exige qu'il soit le plan canonique."""
    return check_plan(_read_plan(CANONICAL_PLAN_PATH if path is None else path))


def _stops(record):
    """Génération épuisée sans adoption, d'après exhausted et les deux digests."""
    if not isinstance(record, dict) or record.get("exhausted") is not True:
        return False
    transmission = record.get("transmission")
    if not isinstance(transmission, dict) or "digest" not in transmission or "digest" not in record:
        return False
    return transmission["digest"] == record["digest"]


class ArmRun:
    """Exécution persistante d'un couple bras/graine ; step() exécute une seule génération."""

    def __init__(self, arm, seed, tasks, limit, budget):
        if arm not in arms.ARMS:
            raise ValueError(f"bras inconnu : {arm!r}")
        self.arm, self.seed, self.limit, self.budget = arm, seed, limit, budget
        self.tasks = arms._learn(tasks)
        self.engine = arms.ce.Engine()
        self.state = arms.lineage.initial_state() if arm == "inherited_lineage" else None
        self.procedure = None
        if arm == "fixed_procedure":
            self.procedure = arms.cp.seed_procedure()
        elif arm == "random_procedure":
            self.procedure = arms._draw_random(seed)
        self.index = 0
        self.parent = None

    def step(self):
        index = self.index
        lib_d, proc_d = arms._view(self.engine, self.procedure, self.state)
        meter = arms.ce.Meter(self.limit)
        if self.arm == "inherited_lineage":
            self.state = arms.lineage.step(self.state, self.tasks, self.budget, meter, random.Random(f"meta|{self.seed}|{index}"))
            spend = self.state["spent"]
            exhausted = self.state["exhausted"]
            score = None if self.state["parent_score"] is None else list(self.state["parent_score"])
            selection = None if self.state["score"] is None else list(self.state["score"])
        else:
            self.engine, spend, exhausted, solutions = arms._generation(self.arm, self.engine, self.procedure, self.tasks, self.budget, meter, index)
            score = arms._score(solutions)
            selection = None
        spend = {post: spend[post] for post in sorted(spend)}
        arms._check(spend, meter, self.limit)
        out_lib, out_proc = arms._view(self.engine, self.procedure, self.state)
        digest = arms._node(lib_d, proc_d)
        transmission_digest = arms._node(out_lib, out_proc)
        record = {
            "index": index,
            "parent": self.parent,
            "digest": digest,
            "library_digest": lib_d,
            "procedure_digest": proc_d,
            "spent": meter.spent,
            "limit": self.limit,
            "spend": spend,
            "score": score,
            "selection_score": selection,
            "exhausted": bool(exhausted),
            "transmission": {"digest": transmission_digest, "library_digest": out_lib, "procedure_digest": out_proc},
        }
        self.parent = transmission_digest
        self.index = index + 1
        return record


def new_run(arm, seed, tasks, limit, budget):
    """Fabrique d'un ArmRun persistant (point d'injection pour les tests)."""
    return ArmRun(arm, seed, tasks, limit, budget)


def run_until_stop(arm, seed, learn, count, limit, budget):
    """Un seul run persistant ; step() au plus count fois, arrêt immédiat dès que _stops joue."""
    run = new_run(arm, seed, learn, limit, budget)
    records = []
    reason = LIMIT_REASON
    for _ in range(count):
        record = run.step()
        records.append(record)
        if _stops(record):
            reason = STOP_REASON
            break
    return {
        "arm": arm,
        "seed": seed,
        "task_budget": budget,
        "per_generation_limit": limit,
        "generations": records,
        "stopped_early": reason == STOP_REASON,
        "stop_reason": reason,
        "generations_run": len(records),
    }


def run_campaign(plan, seeds=None, generations=None):
    """Exécute les bras sur LEARN seul ; ne calcule aucun gain ni succès."""
    check_plan(plan)
    budgets = plan["budgets"]
    plan_seeds = list(plan["seeds"])
    chosen = plan_seeds if seeds is None else list(seeds)
    if not chosen or len(set(chosen)) != len(chosen) or not set(chosen) <= set(plan_seeds):
        raise ValueError(f"graines hors du plan ou invalides : {chosen}")
    max_generations = budgets["generations"]
    count = max_generations if generations is None else generations
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= max_generations:
        raise ValueError(f"générations invalides : {count} (maximum du plan : {max_generations})")
    learn = freeze.learn_tasks()
    limit, budget = budgets["per_generation_limit"], budgets["task_budget"]
    bounded = {arm: [run_until_stop(arm, seed, learn, count, limit, budget) for seed in chosen] for arm in arms.ARMS}
    full = set(chosen) == set(plan_seeds) and count == max_generations
    return {
        "plan_digest": plan["digest"],
        "machinery_commit": plan["machinery_commit"],
        "seeds": chosen,
        "generations": count,
        "scale": "full" if full else "reduced",
        "arms": bounded,
    }


def _parse_seeds(text):
    try:
        return [int(part) for part in text.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"graines invalides : {text!r}") from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default=str(CANONICAL_PLAN_PATH))
    parser.add_argument("--seeds", type=_parse_seeds, default=None, help="sous-ensemble des graines du plan, séparées par des virgules")
    parser.add_argument("--generations", type=int, default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    try:
        if args.out is not None and Path(args.out).exists():
            raise FileExistsError(f"sortie déjà existante : {args.out}")
        plan = load_plan(args.plan)
        result = run_campaign(plan, args.seeds, args.generations)
        text = json.dumps(result, indent=2) + "\n"
        if args.out is None:
            sys.stdout.write(text)
        else:
            with open(args.out, "x", encoding="utf-8") as handle:
                handle.write(text)
    except (PlanError, ValueError, OSError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
