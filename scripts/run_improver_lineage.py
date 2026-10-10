#!/usr/bin/env python3
"""A lineage of improvers, each written by its parent applied to itself.

    pilot        improvers on a few development tasks, to check the apparatus; not evidence
    plan         freeze a lineage: seed, budgets, task numbering, promotion rule, spending ceiling
    generation   the current improver improves itself; parent and candidate are then run on the
                 same fresh development tasks and the rule decides

Task numbers are never reused: each generation draws its own for the self-application and for
the comparison. Held-out families are not touched here. OPENROUTER_API_KEY is read from the
environment.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import improver_lineage as lineage  # noqa: E402
from genesis.repair_lineage import BudgetExhausted, Ledger, ModelUnavailable  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/improver"
MACHINERY = ("genesis/improver_runtime.py", "genesis/improver_lineage.py", "genesis/improver_seed.py",
             "genesis/repair_lineage.py", "genesis/openrouter_repair.py", "scripts/run_improver_lineage.py")
UNKNOWN_COST_USD = 0.02
META_TASKS, SELECTION_TASKS, PILOT_TASKS = 1000, 2000, 9000


def machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in MACHINERY}


def seal(path: Path, body: dict, key: str) -> dict:
    record = {**body, key: digest_of(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def sealed(path: Path, key: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get(key) != digest_of({name: value for name, value in record.items() if name != key}):
        raise SystemExit(f"{path.name}: {key} does not match its content")
    return record


class Books:
    """The ledger and the journal of one workspace; every request is written before anything else."""

    def __init__(self, workspace: Path, ceiling: float):
        workspace.mkdir(parents=True, exist_ok=True)
        self.path, spent = workspace / "calls.jsonl", 0.0
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                cost = json.loads(line).get("cost_usd")
                spent += UNKNOWN_COST_USD if cost is None else cost
        self.ledger = Ledger(ceiling, spent)

    def model(self, label: dict) -> lineage.Model:
        def journal(record: dict) -> None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({**label, **record}, sort_keys=True) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return lineage.Model(self.ledger, journal)


def attempts(source: str, tasks: list, books: Books, label: str, parallel: int) -> list[dict]:
    def one(item):
        family, task = item
        return lineage.attempt(source, family, task, books.model({"use": label, "family": family, "task": task}))
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        return list(pool.map(one, tasks))


def pilot(arguments) -> None:
    books = Books(Path(arguments.workspace).resolve(), arguments.ceiling)
    tasks = [(family, PILOT_TASKS + index) for family in lineage.DEVELOPMENT for index in range(arguments.tasks)]
    for path in arguments.improver:
        rows = attempts(Path(path).read_text(encoding="utf-8"), tasks, books, f"pilot:{Path(path).stem}", arguments.parallel)
        by_family = {family: round(sum(row["score"] for row in rows if row["family"] == family) / arguments.tasks, 4)
                     for family in lineage.DEVELOPMENT}
        print(Path(path).stem, round(sum(row["score"] for row in rows) / len(rows), 4), by_family,
              "errors", [row["error"] for row in rows if row["error"]], "calls", sum(row["lm_calls"] for row in rows),
              f"spent {books.ledger.spent:.3f}", flush=True)


def plan(arguments) -> None:
    target = HOME / arguments.name / "PLAN.json"
    if target.exists():
        raise SystemExit("this lineage is already planned")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    seed = lineage.SEED.read_text(encoding="utf-8")
    body = {
        "schema": "genesis-improver-lineage-plan-v1", "name": arguments.name, "model": lineage.MODEL,
        "seed_improver_sha256": digest_of(seed), "image": lineage.IMAGE,
        "object_budget": lineage.OBJECT_BUDGET, "meta_budget": lineage.META_BUDGET,
        "tasks_per_improver_evaluation": lineage.CHILDREN,
        "development_families": list(lineage.DEVELOPMENT), "held_out_families": list(lineage.HELD_OUT),
        "generations": arguments.generations, "replicate": arguments.replicate,
        "self_application": ("generation g: the current improver is run on the task 'improver' with its own source as "
                             f"the initial program and {lineage.CHILDREN} development tasks numbered "
                             f"{META_TASKS} + 100 * (10 * replicate + g) + i, one per family in rotation; what it returns is "
                             "the candidate"),
        "comparison": (f"parent and candidate are each run once on {arguments.selection} tasks per development family, "
                       f"numbered {SELECTION_TASKS} + 100 * (10 * replicate + g) + i, and scored by the host on the five hidden "
                       "instances of each task"),
        "selection_tasks_per_family": arguments.selection,
        "promotion_rule": {"margin": arguments.margin, "level": 0.05, "tie": 0.005,
                           "text": "tasks won minus tasks lost at least the margin, a higher mean score, and an exact "
                                   "one-sided sign test at the level; a candidate identical to its parent is not run"},
        "after_a_rejection": "the parent stays and applies itself again on new tasks",
        "spending_ceiling_usd": arguments.ceiling,
        "held_out_rule": ("held-out families are run only once the lineage is frozen, seed against final improver, "
                          "under a separate preregistration"),
        "claim_boundary": ("promotions on development families select improvers and prove nothing by themselves; no "
                           "outcome of a lineage establishes general recursive self-improvement"),
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    seal(target, body, "plan_digest")
    (HOME / arguments.name / "improvers").mkdir(exist_ok=True)
    (HOME / arguments.name / "improvers" / "g0.py").write_text(seed, encoding="utf-8")
    print(json.dumps({"name": arguments.name, "generations": arguments.generations}))


def generation(arguments) -> None:
    home = HOME / arguments.name
    frozen = sealed(home / "PLAN.json", "plan_digest")
    if frozen["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the plan")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    done = sorted(home.glob("GENERATION_*.json"))
    number = len(done) + 1
    if number > frozen["generations"]:
        raise SystemExit("the planned generations are done")
    current = sealed(done[-1], "generation_digest")["current_after"] if done else "g0"
    source = (home / "improvers" / f"{current}.py").read_text(encoding="utf-8")
    books = Books(Path(arguments.workspace).resolve(), frozen["spending_ceiling_usd"])
    base = 100 * (10 * frozen["replicate"] + number)
    families = lineage.DEVELOPMENT
    children = [(families[(number + index) % len(families)], META_TASKS + base + index) for index in range(lineage.CHILDREN)]
    try:
        ran = lineage.run_improver(source, lineage.meta_spec(source, children),
                                   books.model({"use": f"g{number}:self-application"}), cpus=4)
        candidate = ran["solution"]
        body = {"schema": "genesis-improver-generation-v1", "name": arguments.name, "generation": number,
                "plan_digest": frozen["plan_digest"], "parent": current, "parent_sha256": digest_of(source),
                "self_application": {"tasks": children, "error": ran["error"], "lm_calls": ran["lm_calls"],
                                     "evaluations_used": ran["evaluations_used"], "seconds": ran["seconds"],
                                     "stderr_tail": ran["stderr"][-600:] if ran["error"] else ""},
                "candidate_sha256": digest_of(candidate) if candidate else None}
        if not candidate or candidate == source:
            body.update(comparison=None, promoted=False, current_after=current,
                        reason="no candidate" if not candidate else "the candidate is the parent")
        else:
            (home / "improvers" / f"g{number}.candidate.py").write_text(candidate, encoding="utf-8")
            tasks = [(family, SELECTION_TASKS + base + index) for family in families
                     for index in range(frozen["selection_tasks_per_family"])]
            parent_rows = attempts(source, tasks, books, f"g{number}:parent", arguments.parallel)
            child_rows = attempts(candidate, tasks, books, f"g{number}:candidate", arguments.parallel)
            rule = frozen["promotion_rule"]
            comparison = lineage.compared(parent_rows, child_rows, tie=rule["tie"])
            won = lineage.promoted(comparison, margin=rule["margin"], level=rule["level"])
            if won:
                (home / "improvers" / f"g{number}.py").write_text(candidate, encoding="utf-8")
            body.update(comparison=comparison, promoted=won, current_after=f"g{number}" if won else current,
                        parent_rows=parent_rows, candidate_rows=child_rows, reason=None)
    except (BudgetExhausted, ModelUnavailable) as error:
        raise SystemExit(f"stopped, nothing sealed: {type(error).__name__}: {error}")
    body["spent_usd_so_far"] = round(books.ledger.spent, 4)
    seal(home / f"GENERATION_{number}.json", body, "generation_digest")
    print(json.dumps({key: body[key] for key in ("generation", "parent", "promoted", "current_after", "reason",
                                                 "comparison", "self_application", "spent_usd_so_far")}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("pilot", pilot), ("plan", plan), ("generation", generation)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        if name == "pilot":
            command.add_argument("--improver", nargs="+", required=True)
            command.add_argument("--tasks", type=int, default=2)
            command.add_argument("--ceiling", type=float, default=0.5)
        else:
            command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--generations", type=int, default=6)
            command.add_argument("--replicate", type=int, default=0)
            command.add_argument("--selection", type=int, default=5)
            command.add_argument("--margin", type=int, default=5)
            command.add_argument("--ceiling", type=float, default=6.0)
        if name != "plan":
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=6)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
