#!/usr/bin/env python3
"""Can the improvement step of the circuit engine learn from its own past attempts? No model, no clock.

    plan    freeze hypotheses, arms, budgets, seeds and readings
    run     run a frozen plan, keep everything in a SQLite file, seal the summary

CIRCUIT1 left two measured facts: a lineage runs out of components to propose (24 distinct ones
over 3,057 trials), and more trials harm the engine than help it. Two hypotheses follow.

H1, the space. With components of up to four inputs taken from sub-circuits up to three layers
deep, lineages have more to propose, run longer and reach more held-out tasks than in CIRCUIT1.

H2, learning to improve. A ranker of proposed components, fitted on the trials of lineages that
learnt from OTHER families, makes a lineage gain more than random or support ranking does, and
more when fitted on two other family groups than on one.

    open       H1: seed procedure with the open space, all learning families, the budget of CIRCUIT1
    explore    open space, components to try drawn at random: the trials rankers are fitted on, and
               the random arm of H2
    support    open space, most shared components first
    learned1   ranker fitted on the explore trials of one other family group
    learned2   ranker fitted on those of the two other family groups
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import json
from math import comb
from pathlib import Path
import sqlite3
import subprocess
import sys

import numpy

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import run_circuit_lineage as lineage  # noqa: E402
from genesis import circuit_tasks  # noqa: E402
from genesis.circuit_engine import SEED_PROCEDURE, features  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/engine"
MACHINERY = ("genesis/circuit_engine.py", "genesis/circuit_tasks.py", "scripts/run_circuit_lineage.py", "scripts/run_circuit_meta.py")
GROUPS = (("and", "or", "parity"), ("equal", "mux"), ("adder", "majority"))
OPEN = {**SEED_PROCEDURE, "layers": 3, "arity": 4, "min_support": 1}


def machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in MACHINERY}


def trials_of(outcome: dict) -> list[tuple[list[float], float]]:
    """Features of every component tried in a run and the learning tasks it gained or lost."""
    rows, solved = [], {row[0]: row[3] for row in outcome["generations"]}
    for generation, _, step, _, _ in outcome["generations"]:
        for trial in (json.loads(step) or {}).get("trials", []) if generation else []:
            rows.append((features(trial["arity"], trial["table"], trial["nands"], trial["support"], generation, trial["library"]),
                         float(trial["solved"] - solved[generation - 1])))
    return rows


def fitted(rows: list[tuple[list[float], float]]) -> list[float]:
    """Ridge regression of the gain, clipped to three tasks either way, on the features."""
    if not rows:
        return [0.0] * len(features(2, 0b0110, 4, 2, 1, 1))
    x = numpy.array([row[0] for row in rows])
    y = numpy.clip(numpy.array([row[1] for row in rows]), -3, 3)
    weights = numpy.linalg.solve(x.T @ x + numpy.eye(x.shape[1]), x.T @ y)
    return [round(float(value), 6) for value in weights]


def auc(weights: list[float], rows: list[tuple[list[float], float]]) -> float | None:
    scored = [(sum(w * v for w, v in zip(weights, row[0])), row[1] > 0) for row in rows]
    good, bad = [score for score, gain in scored if gain], [score for score, gain in scored if not gain]
    if not good or not bad:
        return None
    return round(sum((a > b) + 0.5 * (a == b) for a in good for b in bad) / (len(good) * len(bad)), 3)


def sign(first: list, second: list) -> dict:
    """``second`` against ``first``, paired: wins, losses and the exact one-sided sign test."""
    wins, losses = sum(b > a for a, b in zip(first, second)), sum(b < a for a, b in zip(first, second))
    total = wins + losses
    return {"wins": wins, "losses": losses, "mean_difference": round(sum(b - a for a, b in zip(first, second)) / len(first), 3),
            "one_sided_sign_test_p": round(sum(comb(total, k) for k in range(wins, total + 1)) / 2 ** total, 4) if total else 1.0}


def plan(arguments) -> None:
    target = HOME / arguments.name / "PLAN.json"
    if target.exists():
        raise SystemExit("already planned")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    first = json.loads((HOME / "CIRCUIT1/RESULT.json").read_text(encoding="utf-8"))
    lineage.seal(target, {
        "schema": "genesis-circuit-meta-plan-v1", "name": arguments.name, "budget_h1": arguments.budget, "budget_h2": arguments.second_budget,
        "seeds": list(range(arguments.seeds)), "generations_at_most": arguments.generations, "family_groups": [list(group) for group in GROUPS],
        "learning_families": list(circuit_tasks.LEARN), "held_out_families": list(circuit_tasks.HELD_OUT),
        "open_procedure": OPEN, "ranker": "ridge regression (penalty 1) of the clipped gain in learning tasks on thirteen features of a "
                                          "proposed component; fitted only on explore trials of other family groups, all seeds",
        "reference_circuit1": {"result_digest": first["result_digest"],
                               "held_out_by_seed": first["by_budget"][str(arguments.budget)]["lineage"]["held_out"]},
        "hypotheses": {
            "H1": "held-out tasks solved by `open` exceed those of the CIRCUIT1 lineage, same seeds, tasks and budget (paired; the mean "
                  "must be higher), and the number of components proposed per step does not fall with generations. Refuted otherwise",
            "H2a": "learning tasks gained by `learned2` exceed those gained by `explore` (random ranking), paired over family group and "
                   "seed, exact one-sided sign test at 0.05. Refuted otherwise",
            "H2b": "`learned2` gains at least as much as `learned1` on average, and `learned2` at least as much as `support`",
            "diagnostic": "area under the curve of each ranker for 'the trial gains a task' on the explore trials of its target group",
        },
        "reading": ("H2 is the test of the second-order criterion in its simplest form: experience of improving, gathered elsewhere, "
                    "makes improving more productive, and more experience makes it more productive still. The ranker's form and "
                    "features are written by hand; only its weights are learnt"),
        "stopping_rule": "a lineage ends at the first step that keeps no component, or at the generation limit",
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
    seeds, limit = frozen["seeds"], frozen["generations_at_most"]
    budgets = (frozen["budget_h1"], frozen["budget_h2"])
    if arguments.rehearsal:      # a check of the script on budgets too small to mean anything; nothing is shown
        seeds, limit, budgets = seeds[:2], 2, (300, 200)
    job = lambda arm, seed, families, budget, procedure, **more: {  # noqa: E731
        "arm": arm, "seed": seed, "families": list(families), "budget": budget, "procedure": procedure, "generations": limit, **more}
    paired = seeds[:len(frozen["reference_circuit1"]["held_out_by_seed"])]      # H1 is paired with the seeds of CIRCUIT1
    first = [job("open", seed, frozen["learning_families"], budgets[0], OPEN) for seed in paired]
    for index, group in enumerate(GROUPS):
        for seed in seeds:
            first.append(job(f"explore{index}", seed, group, budgets[1], {**OPEN, "ranking": "random"}))
            first.append(job(f"support{index}", seed, group, budgets[1], OPEN))
    workspace = Path(arguments.workspace).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(workspace / f"{arguments.name}.sqlite")
    database.executescript(lineage.SCHEMA)
    outcomes: dict[str, dict] = {}

    def store(outcome: dict) -> None:
        made = outcome["job"]
        name = f"{made['arm']}-b{made['budget']}-s{made['seed']}"
        outcomes[name] = outcome
        database.execute("insert or replace into runs values (?, ?, ?, ?, ?)",
                         (name, made["arm"], made["seed"], json.dumps(made, sort_keys=True), outcome["seconds"]))
        database.execute("delete from generations where run = ?", (name,))
        database.execute("delete from results where run = ?", (name,))
        database.executemany("insert into generations values (?, ?, ?, ?, ?, ?)", [(name, *row) for row in outcome["generations"]])
        database.executemany("insert into results values (?, ?, ?, ?, ?, ?, ?, ?, ?)", [(name, *row) for row in outcome["rows"]])
        database.commit()

    with ProcessPoolExecutor(max_workers=arguments.parallel) as pool:
        for outcome in pool.map(lineage.one, first):
            store(outcome)
        explored = {index: [row for seed in seeds for row in trials_of(outcomes[f"explore{index}-b{budgets[1]}-s{seed}"])]
                    for index in range(len(GROUPS))}
        rankers, second = {}, []
        for index, group in enumerate(GROUPS):
            others = [(index + 1) % len(GROUPS), (index + 2) % len(GROUPS)]
            for label, sources in (("learned1", others[:1]), ("learned2", others)):
                weights = fitted([row for source in sources for row in explored[source]])
                rankers[f"{label}{index}"] = {"weights": weights, "fitted_on_groups": sources,
                                              "trials": sum(len(explored[source]) for source in sources),
                                              "auc_on_target_explore_trials": auc(weights, explored[index])}
                second += [job(f"{label}{index}", seed, group, budgets[1], {**OPEN, "ranking": "learned"}, ranker=weights) for seed in seeds]
        for outcome in pool.map(lineage.one, second):
            store(outcome)

    def numbers(arm: str, budget: int, group: int | None = None) -> dict:
        names = [f"{arm}{'' if group is None else group}-b{budget}-s{seed}" for seed in (paired if group is None else seeds)]
        runs = [outcomes[name] for name in names]
        steps = [[json.loads(row[2]) for row in run["generations"] if row[0]] for run in runs]
        last = lambda run, split: sum(row[5] for row in run["rows"] if row[1] == split and row[0] == max(r[0] for r in run["rows"]))  # noqa: E731
        return {"learning_gain": [run["generations"][-1][3] - run["generations"][0][3] for run in runs],
                "held_out": [last(run, "held_out") for run in runs],
                "trials": [sum(len(step.get("trials", [])) for step in each) for each in steps],
                "components_kept": [sum(1 for step in each if step.get("added")) for each in steps],
                "candidates_by_step": [[step.get("candidates") for step in each] for each in steps]}

    opened = numbers("open", budgets[0])
    arms = {arm: [numbers(arm, budgets[1], index) for index in range(len(GROUPS))] for arm in ("explore", "support", "learned1", "learned2")}
    flat = lambda arm, key: [value for group in arms[arm] for value in group[key]]  # noqa: E731
    mean = lambda values: round(sum(values) / len(values), 3)  # noqa: E731
    reference = frozen["reference_circuit1"]["held_out_by_seed"][:len(paired)]
    summary = {
        "H1": {"open_held_out": opened["held_out"], "circuit1_held_out": reference, "paired": sign(reference, opened["held_out"]),
               "candidates_by_step": opened["candidates_by_step"], "components_kept": opened["components_kept"],
               "learning_gain": opened["learning_gain"]},
        "H2": {"learning_gain_mean": {arm: mean(flat(arm, "learning_gain")) for arm in arms},
               "held_out_mean": {arm: mean(flat(arm, "held_out")) for arm in arms},
               "trials_mean": {arm: mean(flat(arm, "trials")) for arm in arms},
               "gain_per_trial": {arm: round(sum(flat(arm, "learning_gain")) / max(1, sum(flat(arm, "trials"))), 4) for arm in arms},
               "learned2_against_explore": sign(flat("explore", "learning_gain"), flat("learned2", "learning_gain")),
               "learned2_against_support": sign(flat("support", "learning_gain"), flat("learned2", "learning_gain")),
               "learned2_against_learned1": sign(flat("learned1", "learning_gain"), flat("learned2", "learning_gain")),
               "held_out_learned2_against_explore": sign(flat("explore", "held_out"), flat("learned2", "held_out"))},
        "rankers": rankers, "by_arm_and_group": arms,
        "seconds": round(sum(outcome["seconds"] for outcome in outcomes.values()), 1),
    }
    if arguments.rehearsal:
        print("rehearsal complete:", len(outcomes), "runs;", sorted(summary), sorted(summary["H2"]))
        return
    lineage.seal(home / "RESULT.json", {"schema": "genesis-circuit-meta-result-v1", "name": arguments.name,
                                        "plan_digest": frozen["plan_digest"], **summary}, "result_digest")
    print(json.dumps({key: summary[key] for key in ("H1", "H2")}, indent=1))


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
            command.add_argument("--seeds", type=int, default=10, help="H2 uses them all, H1 the first five")
            command.add_argument("--generations", type=int, default=12)
        else:
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=6)
            command.add_argument("--rehearsal", action="store_true", help="tiny budgets, nothing sealed; for checking the script")
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
