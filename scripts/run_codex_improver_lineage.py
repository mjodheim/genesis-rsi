#!/usr/bin/env python3
"""A lineage of improvers whose model is reached through the Codex client, under a daily ceiling.

    plan         freeze the lineage; same protocol as run_improver_lineage.py, other model and channel
    generation   as there; stops without sealing when the day's requests are spent, and resumes

A generation needs more requests than one day allows. Everything finished is kept in the
workspace (the self-application, then each task of the comparison) and never run twice; the
generation is sealed once complete.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import improver_codex as codex  # noqa: E402
from genesis import improver_lineage as lineage  # noqa: E402
from genesis.repair_lineage import BudgetExhausted, ModelUnavailable  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/improver"
MACHINERY = ("genesis/improver_runtime.py", "genesis/improver_lineage.py", "genesis/improver_seed.py",
             "genesis/improver_codex.py", "scripts/run_codex_improver_lineage.py")
META_TASKS, SELECTION_TASKS = 1000, 2000


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


def kept(path: Path, compute):
    """What ``compute`` returned the first time, stored at ``path``."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    value = compute()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")
    return value


def plan(arguments) -> None:
    target = HOME / arguments.name / "PLAN.json"
    if target.exists():
        raise SystemExit("this lineage is already planned")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    seed = lineage.SEED.read_text(encoding="utf-8")
    body = {
        "schema": "genesis-improver-lineage-plan-v1", "name": arguments.name,
        "model": codex.MODEL, "reasoning_effort": codex.EFFORT,
        "channel": ("codex exec, read-only, in an empty directory, under a subscription: answer size, temperature and "
                    "system prompt are the client's; requests are bounded per day, not priced"),
        "requests_per_day": arguments.per_day,
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
        "resumption": ("a generation interrupted by the daily ceiling or by the subscription resumes from what is "
                       "stored; a finished self-application or task is never run again; a task whose improver was cut "
                       "off by the interruption is discarded and run again in full"),
        "held_out_rule": ("held-out families are run only once the lineage is frozen, seed against final improver, "
                          "under a separate preregistration"),
        "claim_boundary": ("promotions on development families select improvers and prove nothing by themselves; no "
                           "outcome of a lineage establishes general recursive self-improvement"),
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    seal(target, body, "plan_digest")
    (HOME / arguments.name / "improvers").mkdir(exist_ok=True)
    (HOME / arguments.name / "improvers" / "g0.py").write_text(seed, encoding="utf-8")
    print(json.dumps({"name": arguments.name, "generations": arguments.generations, "per_day": arguments.per_day}))


def generation(arguments) -> None:
    home = HOME / arguments.name
    frozen = sealed(home / "PLAN.json", "plan_digest")
    if frozen["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the plan")
    done = sorted(home.glob("GENERATION_*.json"))
    number = len(done) + 1
    if number > frozen["generations"]:
        raise SystemExit("the planned generations are done")
    current = sealed(done[-1], "generation_digest")["current_after"] if done else "g0"
    source = (home / "improvers" / f"{current}.py").read_text(encoding="utf-8")
    workspace = Path(arguments.workspace).resolve()
    store = workspace / f"g{number}"
    store.mkdir(parents=True, exist_ok=True)

    def model(use: str, **label):
        return codex.CodexModel(workspace / "calls.jsonl", {"use": use, **label}, per_day=frozen["requests_per_day"])

    def room(needed: int) -> None:
        """Do not start what the day cannot finish: an interrupted run is thrown away."""
        if frozen["requests_per_day"] - model("check").used_today() < needed:
            raise BudgetExhausted(f"fewer than {needed} requests left today")

    base = 100 * (10 * frozen["replicate"] + number)
    families = lineage.DEVELOPMENT
    children = [(families[(number + index) % len(families)], META_TASKS + base + index) for index in range(lineage.CHILDREN)]

    def attempts(improver: str, label: str, tasks: list) -> list[dict]:
        def one(item):
            family, task = item
            return kept(store / label / f"{family}-{task}.json",
                        lambda: room(lineage.OBJECT_BUDGET["lm_calls"]) or lineage.attempt(improver, family, task, model(f"g{number}:{label}", family=family, task=task)))
        with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
            return list(pool.map(one, tasks))

    try:
        ran = kept(store / "self_application.json", lambda: room(lineage.META_BUDGET["lm_calls"]) or lineage.run_improver(
            source, lineage.meta_spec(source, children), model(f"g{number}:self-application"), cpus=4))
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
            parent_rows = attempts(source, "parent", tasks)
            child_rows = attempts(candidate, "candidate", tasks)
            rule = frozen["promotion_rule"]
            comparison = lineage.compared(parent_rows, child_rows, tie=rule["tie"])
            won = lineage.promoted(comparison, margin=rule["margin"], level=rule["level"])
            if won:
                (home / "improvers" / f"g{number}.py").write_text(candidate, encoding="utf-8")
            body.update(comparison=comparison, promoted=won, current_after=f"g{number}" if won else current,
                        parent_rows=parent_rows, candidate_rows=child_rows, reason=None)
    except (BudgetExhausted, ModelUnavailable) as error:
        raise SystemExit(f"interrupted, nothing sealed, resume later: {type(error).__name__}: {error}")
    journal = workspace / "calls.jsonl"
    body["model_requests_so_far"] = sum('"state": "sent"' in line for line in journal.read_text(encoding="utf-8").splitlines())
    seal(home / f"GENERATION_{number}.json", body, "generation_digest")
    print(json.dumps({key: body[key] for key in ("generation", "parent", "promoted", "current_after", "reason",
                                                 "comparison", "self_application", "model_requests_so_far")}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("plan", plan), ("generation", generation)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--generations", type=int, default=5)
            command.add_argument("--replicate", type=int, required=True)
            command.add_argument("--selection", type=int, default=4)
            command.add_argument("--margin", type=int, default=4)
            command.add_argument("--per-day", type=int, default=300)
        else:
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=4)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
