"""Freeze the CIRCUIT2 pre-registered plan (script and test only; no PLAN.json here).

The held-out families are named in the plan but never evaluated by this script. The plan is
generated from main, in a separate change, with ``python scripts/freeze_circuit2_plan.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import circuit_engine as engine  # noqa: E402
from genesis import circuit_procedure as cp  # noqa: E402
from genesis import circuit_tasks as tasks  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

PLAN_PATH = ROOT / "experiment" / "engine" / "CIRCUIT2" / "PLAN.json"
SCHEMA = "circuit2-plan-v1"
SEEDS = tuple(range(20))
SEED_LABEL = "circuit2|{seed}"
GENERATIONS = 6
TASK_BUDGET = 16
LIMIT_MULTIPLIER = 8
MEASURE_CEILING = 10**7
MAX_INPUTS = 3
MACHINERY_FILES = (
    "genesis/circuit_engine.py",
    "genesis/circuit_procedure.py",
    "genesis/circuit_meta_lineage.py",
    "genesis/circuit_tasks.py",
    "scripts/freeze_circuit2_plan.py",
)
CRITERION = (
    "succès seulement si la procédure finale gagne au moins 10 points de rendement "
    "contre la procédure fixe et contre l'aléatoire ; si deux transitions successives "
    "de procédure gagnent chacune au moins 5 points à bibliothèque initiale identique ; "
    "si chacune de ces comparaisons gagne dans au moins 16 graines sur 20 ; et si le gain "
    "disparaît sous ablation (procédure initiale restaurée). Sinon échec publié. "
    "Aucun critère n'est modifiable après gel."
)


class PlanError(Exception):
    """The plan cannot be built, sealed or verified."""


def seal(body: dict) -> dict:
    return {**body, "digest": digest_of(body)}


def learn_tasks() -> list:
    return [t for t in tasks.suite(tuple(tasks.LEARN)) if t.inputs <= MAX_INPUTS]


def file_digests(root: Path = ROOT) -> dict:
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in MACHINERY_FILES}


def git_head(root: Path = ROOT) -> str:
    try:
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PlanError(f"cannot read machinery_commit: {exc}") from exc
    return done.stdout.strip()


def measure_base_costs(seeds=SEEDS, task_budget=TASK_BUDGET) -> dict:
    """Cost of one full base evaluation on the LEARN tasks only, offline, for each seed."""
    learn = learn_tasks()
    costs = {}
    for seed in seeds:
        meter = engine.Meter(MEASURE_CEILING)
        machine = engine.Engine()
        spent = {"procedure": 0, "synthesis": 0, "evaluations": 0}
        try:
            outcome = engine._metered_attempt(machine, learn, task_budget, meter, spent)
        except Exception as exc:
            raise PlanError(f"base evaluation does not fit or failed for seed {seed}: {exc}") from exc
        if outcome is None:
            raise PlanError(f"base evaluation does not fit in the measuring meter for seed {seed}: incomplete base evaluation")
        if meter.spent != spent["evaluations"]:
            raise PlanError(f"meter and evaluations post disagree for seed {seed}: {meter.spent} != {spent['evaluations']}")
        costs[str(seed)] = meter.spent
    return costs


def _arms() -> list:
    fixed = cp.to_record(cp.seed_procedure())["procedure_digest"]
    return [
        {"name": "inherited_lineage", "procedure": "inherited and selected across generations"},
        {"name": "frozen_engine", "procedure": "initial procedure kept, no procedure selection"},
        {"name": "fixed_procedure", "procedure": "CIRCUIT1 SEED_PROCEDURE", "procedure_digest": fixed},
        {"name": "random_procedure", "procedure": "circuit_procedure.random_procedure"},
    ]


def _assemble(costs, commit, digests) -> dict:
    if set(costs) != {str(s) for s in SEEDS} or not all(
        isinstance(v, int) and not isinstance(v, bool) and v > 0 for v in costs.values()
    ):
        raise PlanError("a positive measured base-evaluation cost is required for each of the 20 seeds")
    maximum = max(costs.values())
    limit = LIMIT_MULTIPLIER * maximum
    if maximum > limit:
        raise PlanError("the base evaluation does not fit in the per-generation limit")
    return {
        "schema": SCHEMA,
        "seeds": list(SEEDS),
        "seed_labels": [SEED_LABEL.format(seed=s) for s in SEEDS],
        "arms": _arms(),
        "budgets": {
            "generations": GENERATIONS,
            "per_generation_limit": limit,
            "task_budget": TASK_BUDGET,
            "total_per_arm": GENERATIONS * limit,
            "identical_for_all_arms": True,
        },
        "stop_rule": {
            "max_generations": GENERATIONS,
            "stop_when": ["generation limit reached", "generation exhausted without adoption"],
        },
        "metric": {
            "name": "rendement",
            "definition": "number of held-out tasks solved, reported per seed",
            "held_out_families": sorted(tasks.HELD_OUT),
        },
        "selection": {
            "families": sorted(tasks.LEARN),
            "max_inputs": MAX_INPUTS,
            "held_out_reads": 0,
            "instance_seeds": "circuit2|... (distinct from CIRCUIT1)",
        },
        "criterion": {
            "text": CRITERION,
            "thresholds": {
                "final_vs_fixed_points": 10,
                "final_vs_random_points": 10,
                "transition_points": 5,
                "successive_transitions": 2,
                "min_seeds_won": 16,
                "of_seeds": 20,
                "ablation": "initial procedure restored, gain must disappear",
            },
        },
        "budget_justification": {
            "measured_on": "LEARN tasks only, offline, Engine() with a large Meter",
            "measured_base_cost_by_seed": dict(costs),
            "max_measured_base_cost": maximum,
            "limit_multiplier": LIMIT_MULTIPLIER,
            "per_generation_limit": limit,
            "task_budget": TASK_BUDGET,
            "learn_task_count": len(learn_tasks()),
            "rule": "per_generation_limit = limit_multiplier * max_measured_base_cost",
            "superseded": "PER_GENERATION_LIMIT=16 / TASK_BUDGET=32: base evaluation measured at 1560, plan could not be sealed",
        },
        "machinery_commit": commit,
        "machinery_digests": dict(digests),
    }


def build_plan(measure=measure_base_costs, machinery_commit=None, root=ROOT) -> dict:
    commit = machinery_commit or git_head(root)
    return seal(_assemble(measure(), commit, file_digests(root)))


def verify_plan(plan, current_digests=None, root=ROOT) -> None:
    if not isinstance(plan, dict) or "digest" not in plan:
        raise PlanError("plan has no digest")
    body = {k: v for k, v in plan.items() if k != "digest"}
    if digest_of(body) != plan["digest"]:
        raise PlanError("digest does not match the plan content")
    try:
        digests = body["machinery_digests"]
        expected = _assemble(
            body["budget_justification"]["measured_base_cost_by_seed"],
            body["machinery_commit"],
            digests,
        )
    except (KeyError, TypeError) as exc:
        raise PlanError(f"malformed plan: {exc!r}") from exc
    if json.loads(json.dumps(expected)) != body:
        raise PlanError("plan differs from the frozen protocol")
    current = file_digests(root) if current_digests is None else current_digests
    if digests != current:
        raise PlanError("machinery digests differ from the current files")


def freeze(path: Path = PLAN_PATH, measure=measure_base_costs, machinery_commit=None) -> dict:
    path = Path(path)
    if path.exists():
        raise PlanError(f"{path} already exists: a frozen plan is never rewritten")
    plan = build_plan(measure, machinery_commit)
    verify_plan(plan)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    return plan


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=PLAN_PATH)
    args = parser.parse_args(argv)
    started = time.perf_counter()
    try:
        plan = freeze(args.out)
    except PlanError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(f"frozen {args.out} digest={plan['digest']} in {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
