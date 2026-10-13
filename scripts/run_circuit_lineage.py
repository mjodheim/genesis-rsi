#!/usr/bin/env python3
"""Lineages of a circuit-synthesis engine that learns its own components. No model, no clock.

    plan    freeze the experiment: arms, budgets, seeds, families, questions and stopping rules
    run     run every arm of a frozen plan, keep everything in a SQLite file, seal the summary

Arms, each for every seed (a seed draws the four fifths of the learning tasks an engine learns from):

    lineage        the seed improvement procedure, step after step, until a step keeps nothing
    frozen         the first engine, never improved; also judged with 10 and 100 times the budget (the
                   held-out tasks do not depend on the seed, so once)
    together       one step that adds at once as many components as the lineage kept: no accumulation
    random         the lineage with the components to try drawn at random among those found
    procedures     the lineage under each variant of the improvement procedure, learning from family
                   set A and, separately, from family set B: is a procedure that improves engines
                   better on A also better on B?

Engines are judged on held-out families that no step ever reads.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import itertools
import json
from pathlib import Path
import random
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import circuit_engine as engine_module  # noqa: E402
from genesis import circuit_tasks  # noqa: E402
from genesis.circuit_engine import Engine, SEED_PROCEDURE, attempt, improved, measure, together  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/engine"
MACHINERY = ("genesis/circuit_engine.py", "genesis/circuit_tasks.py", "scripts/run_circuit_lineage.py")
SET_A, SET_B = ("and", "or", "parity", "mux"), ("equal", "adder", "majority")
VARIANTS = {"ranking": ("support", "saving", "random"), "drop_unused": (True, False), "heaviest": (1, 4), "arity": (2, 3)}
SCHEMA = """
create table if not exists runs (run text primary key, arm text, seed integer, parameters text, seconds real);
create table if not exists generations (run text, generation integer, engine text, step text, learn_solved integer,
    learn_evaluations integer, primary key (run, generation));
create table if not exists results (run text, generation integer, split text, family text, task text, budget integer,
    solved integer, evaluations integer, cost integer);
"""


def procedures() -> list[dict]:
    names = sorted(VARIANTS)
    return [{**SEED_PROCEDURE, **dict(zip(names, values))} for values in itertools.product(*(VARIANTS[name] for name in names))]


def learning(families, seed: int) -> list:
    tasks = circuit_tasks.suite(families)
    return sorted(random.Random(f"learn|{seed}").sample(tasks, round(0.8 * len(tasks))), key=lambda task: task.name)


def one(job: dict) -> dict:
    """One run: the engine of every generation, its solutions on the learning tasks and its judgment."""
    started, budget, seed = time.monotonic(), job["budget"], job["seed"]
    tasks = learning(job["families"], seed)
    judged = {"held_out": circuit_tasks.suite(circuit_tasks.HELD_OUT), "control": circuit_tasks.suite(circuit_tasks.CONTROL, seed),
              "unseen": [task for task in circuit_tasks.suite(job["families"]) if task not in tasks]}
    engine = Engine()
    solutions = attempt(engine, tasks, budget)
    rows, generations = [], []

    def judge(generation: int, current: Engine, factors=(1,)) -> None:
        for split, items in judged.items():
            for factor in factors:
                for task, solution in zip(items, attempt(current, items, budget * factor)):
                    rows.append((generation, split, task.family, task.name, budget * factor, int(solution.solved),
                                 solution.evaluations, solution.cost))

    def record(generation: int, step: dict | None) -> None:
        solved, evaluations = measure(solutions)
        generations.append((generation, json.dumps(engine.record()), json.dumps(step), solved, evaluations))

    record(0, None)
    judge(0, engine, (1, 10, 100) if job["arm"] == "frozen" and seed == 0 else (1,))
    if job["arm"] == "together":
        engine, solutions = together(engine, tasks, budget, solutions, job["count"])
        record(1, {"added_at_once": job["count"]})
        judge(1, engine)
    elif job["arm"] != "frozen":
        drawn = job["arm"] == "random" or job["procedure"]["ranking"] == "random"
        rng = random.Random(f"random|{seed}") if drawn else None
        procedure = {**job["procedure"], "ranking": "random"} if rng else job["procedure"]
        for generation in range(1, job["generations"] + 1):
            successor, solutions, step = improved(engine, tasks, budget, solutions, generation=generation,
                                                  procedure=procedure, rng=rng, ranker=job.get("ranker"))
            if successor is engine:
                record(generation, step)
                break
            engine = successor
            record(generation, step)
            judge(generation, engine)
    return {"job": job, "generations": generations, "rows": rows, "seconds": round(time.monotonic() - started, 1)}


def seal(path: Path, body: dict, key: str) -> dict:
    record = {**body, key: digest_of(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in MACHINERY}


def plan(arguments) -> None:
    target = HOME / arguments.name / "PLAN.json"
    if target.exists():
        raise SystemExit("already planned")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    seal(target, {
        "schema": "genesis-circuit-lineage-plan-v1", "name": arguments.name, "budget": arguments.budget,
        "second_budget": arguments.second_budget, "seeds": list(range(arguments.seeds)), "generations_at_most": arguments.generations,
        "learning_families": list(circuit_tasks.LEARN), "held_out_families": list(circuit_tasks.HELD_OUT),
        "control_family": list(circuit_tasks.CONTROL), "family_set_a": list(SET_A), "family_set_b": list(SET_B),
        "seed_procedure": SEED_PROCEDURE, "procedure_variants": {name: list(values) for name, values in VARIANTS.items()},
        "unit_of_compute": "one component application in the search; identical budgets per task for every arm",
        "stopping_rule": "a lineage ends at the first step that keeps no component, or at the generation limit",
        "questions": {
            "1 accumulation": "held-out tasks solved by the last engine of `lineage` against `frozen`, same budget, paired by seed; "
                              "and against `frozen` with 10 and 100 times the budget",
            "2 cumulative": "held-out tasks solved by `lineage` against `together` (as many components, one step)",
            "3 ranking": "held-out tasks solved by `lineage` against `random`",
            "4 yield": "tasks gained on the learning set at each step of `lineage`, in order: does a later step gain more than an "
                       "earlier one, and what ends the lineage",
            "5 improving the improver": "for every procedure variant, learning tasks gained by its lineage on family set A and on "
                                        "family set B (mean over seeds). Is the variant that gains most on A better on B than the "
                                        "seed procedure, and what is the rank correlation of the variants between A and B",
        },
        "reading": ("differences are counts of tasks, reported per seed with their mean; five seeds support no significance "
                    "claim beyond an exact sign test at 1/32. Whatever the outcome, the procedure variants are chosen by a fixed "
                    "search written by hand: question 5 measures whether a better improver can be selected and carries over, "
                    "not recursion"),
        "claim_boundary": "one domain, one engine; nothing here establishes general recursive self-improvement",
        "machinery_commit": head, "machinery_digests": machinery(),
    }, "plan_digest")
    print("planned", arguments.name)


def run(arguments) -> None:
    home = HOME / arguments.name
    frozen = json.loads((home / "PLAN.json").read_text(encoding="utf-8"))
    if frozen["plan_digest"] != digest_of({key: value for key, value in frozen.items() if key != "plan_digest"}):
        raise SystemExit("the plan does not match its digest")
    if frozen["machinery_digests"] != machinery() and not arguments.rehearsal:
        raise SystemExit("machinery differs from the plan")
    base = {"generations": frozen["generations_at_most"], "procedure": frozen["seed_procedure"]}
    seeds = frozen["seeds"]
    if arguments.rehearsal:      # a check of the script on budgets too small to mean anything; nothing is shown
        frozen = {**frozen, "budget": 300, "second_budget": 100}
        seeds, base["generations"] = seeds[:2], 2
    first = []
    for budget in (frozen["budget"], frozen["second_budget"]):
        for seed in seeds:
            for arm in ("lineage", "frozen", "random"):
                first.append({**base, "arm": arm, "seed": seed, "budget": budget, "families": frozen["learning_families"]})
    for seed in seeds:
        for index, procedure in enumerate(procedures()):
            for label, families in (("A", frozen["family_set_a"]), ("B", frozen["family_set_b"])):
                first.append({**base, "arm": f"procedure{index}{label}", "seed": seed, "budget": frozen["budget"],
                              "families": families, "procedure": procedure})
    workspace = Path(arguments.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(workspace / f"{arguments.name}.sqlite")
    database.executescript(SCHEMA)

    def store(outcome: dict) -> str:
        job = outcome["job"]
        name = f"{job['arm']}-b{job['budget']}-s{job['seed']}"
        database.execute("insert or replace into runs values (?, ?, ?, ?, ?)",
                         (name, job["arm"], job["seed"], json.dumps(job, sort_keys=True), outcome["seconds"]))
        database.execute("delete from generations where run = ?", (name,))
        database.execute("delete from results where run = ?", (name,))
        database.executemany("insert into generations values (?, ?, ?, ?, ?, ?)", [(name, *row) for row in outcome["generations"]])
        database.executemany("insert into results values (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(name, *row) for row in outcome["rows"]])
        database.commit()
        return name

    with ProcessPoolExecutor(max_workers=arguments.parallel) as pool:
        outcomes = list(pool.map(one, first))
        for outcome in outcomes:
            store(outcome)
        second = []
        for outcome in outcomes:
            job = outcome["job"]
            if job["arm"] == "lineage":
                kept = sum(1 for row in outcome["generations"] if row[0] and json.loads(row[2]).get("added"))
                second.append({**job, "arm": "together", "count": kept})
        for outcome in pool.map(one, second):
            store(outcome)
    summary = summarised(database, frozen)
    if arguments.rehearsal:
        print("rehearsal complete:", len(runs_of(database)), "runs;", sorted(summary), sorted(summary["questions"]))
        return
    seal(home / "RESULT.json", {"schema": "genesis-circuit-lineage-result-v1", "name": arguments.name,
                                "plan_digest": frozen["plan_digest"], **summary}, "result_digest")
    print(json.dumps(summary["questions"], indent=1))


def runs_of(database: sqlite3.Connection) -> list:
    return [row[0] for row in database.execute("select run from runs")]


def summarised(database: sqlite3.Connection, frozen: dict) -> dict:
    def final(run: str, split: str, budget: int) -> int | None:
        row = database.execute(
            "select sum(solved) from results where run = ? and split = ? and budget = ? and generation = "
            "(select max(generation) from results where run = ?)", (run, split, budget, run)).fetchone()
        return row[0]

    def series(run: str) -> list[int]:
        return [row[0] for row in database.execute("select learn_solved from generations where run = ? order by generation", (run,))]

    runs = {row[0]: json.loads(row[1]) for row in database.execute("select run, parameters from runs")}
    seeds = sorted({job["seed"] for job in runs.values()})
    by_budget = {}
    for budget in (frozen["budget"], frozen["second_budget"]):
        table = {}
        for arm in ("lineage", "frozen", "together", "random"):
            names = [f"{arm}-b{budget}-s{seed}" for seed in seeds]
            table[arm] = {"held_out": [final(name, "held_out", budget) for name in names],
                          "unseen": [final(name, "unseen", budget) for name in names],
                          "control": [final(name, "control", budget) for name in names],
                          "learning_set_by_generation": [series(name) for name in names]}
        for factor in (10, 100):
            table[f"frozen_x{factor}"] = {"held_out": final(f"frozen-b{budget}-s0", "held_out", budget * factor)}
        table["components_kept_by_lineage"] = [
            json.loads(row[0]) for seed in seeds for row in database.execute(
                "select engine from generations where run = ? order by generation desc limit 1", (f"lineage-b{budget}-s{seed}",))]
        by_budget[str(budget)] = table
    variants = []
    for index, procedure in enumerate(procedures()):
        gains = {}
        for label in ("A", "B"):
            each = [series(f"procedure{index}{label}-b{frozen['budget']}-s{seed}") for seed in seeds]
            gains[label] = round(sum(item[-1] - item[0] for item in each) / len(each), 3)
            gains[label + "_held_out"] = [final(f"procedure{index}{label}-b{frozen['budget']}-s{seed}", "held_out", frozen["budget"])
                                          for seed in seeds]
        variants.append({"procedure": procedure, "is_seed": procedure == frozen["seed_procedure"], **gains})
    best_on_a = max(variants, key=lambda item: item["A"])
    seed_variant = next(item for item in variants if item["is_seed"])
    main = by_budget[str(frozen["budget"])]
    mean = lambda values: round(sum(values) / len(values), 3)  # noqa: E731
    steps = [[later - earlier for earlier, later in zip(item, item[1:])] for item in main["lineage"]["learning_set_by_generation"]]
    questions = {
        "1 accumulation": {"lineage": mean(main["lineage"]["held_out"]), "frozen": mean(main["frozen"]["held_out"]),
                           "frozen_x10": main["frozen_x10"]["held_out"], "frozen_x100": main["frozen_x100"]["held_out"],
                           "held_out_tasks": len(circuit_tasks.suite(circuit_tasks.HELD_OUT))},
        "2 cumulative": {"lineage": mean(main["lineage"]["held_out"]), "together": mean(main["together"]["held_out"])},
        "3 ranking": {"lineage": mean(main["lineage"]["held_out"]), "random": mean(main["random"]["held_out"])},
        "4 yield": {"tasks_gained_at_each_step_by_seed": steps},
        "5 improving the improver": {
            "seed_procedure": {"A": seed_variant["A"], "B": seed_variant["B"]},
            "best_on_A": {"procedure": best_on_a["procedure"], "A": best_on_a["A"], "B": best_on_a["B"]},
            "rank_correlation_A_B": rank_correlation([item["A"] for item in variants], [item["B"] for item in variants])},
    }
    return {"questions": questions, "by_budget": by_budget, "procedure_variants": variants,
            "seconds": round(sum(row[0] for row in database.execute("select seconds from runs")), 1)}


def rank_correlation(first: list, second: list) -> float:
    """Spearman's coefficient, mean ranks for ties."""
    def ranks(values):
        order = sorted(values)
        return [order.index(value) + (order.count(value) - 1) / 2 for value in values]
    a, b = ranks(first), ranks(second)
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    return round(sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (va * vb) ** 0.5, 3) if va and vb else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("plan", plan), ("run", run)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--budget", type=int, default=30000)
            command.add_argument("--second-budget", type=int, default=5000)
            command.add_argument("--seeds", type=int, default=5)
            command.add_argument("--generations", type=int, default=30)
        else:
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=6)
            command.add_argument("--rehearsal", action="store_true", help="one seed, nothing sealed; for checking the script")
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
