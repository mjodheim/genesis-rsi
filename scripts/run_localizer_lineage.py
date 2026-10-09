"""Prepare, plan, evolve and verify a lineage of model-written fault localizers.

    prepare   check out the buggy revision of development cases, keep their sources and the
              stack traces Defects4J ships for their triggering tests, and derive the edit
              sites from the developer fixes (kept apart from what a module can read)
    plan      freeze the cases, their roles and the protocol
    evolve    let the model rewrite the localizer from its training misses; a successor
              replaces its parent only on a clear paired gain on the selection cases
    verify    score the whole chain once on the validation cases, untouched until then

Held-out cases of the repair bench are never involved. OPENROUTER_API_KEY is read from the
environment by ``evolve`` only.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox  # noqa: E402
from genesis import localizer_lineage as lineage  # noqa: E402
from genesis.repair_lineage import BudgetExhausted, Envelope, Ledger, ModelUnavailable  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SPLIT = ROOT / "experiment/bench/REPAIR_BENCH_SPLIT_V1.json"
HOME = ROOT / "experiment/localizer"
SEED = ROOT / "genesis/localizer_seed.py"
MACHINERY = ("genesis/localizer_lineage.py", "genesis/localizer_seed.py", "genesis/repair_lineage.py",
             "genesis/defects4j_sandbox.py", "scripts/run_localizer_lineage.py")
PYTHON_IMAGE = "python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
UNKNOWN_COST_USD = 0.05


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


def machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in MACHINERY}


# -- prepare ------------------------------------------------------------------------------------


def _copy_java(source: Path, target: Path) -> int:
    count = 0
    for directory, folders, files in os.walk(source, followlinks=False):
        folders[:] = [name for name in folders if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if name.endswith(".java") and path.is_file() and not path.is_symlink():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                count += 1
    return count


def prepare_case(case: str, workspace: Path, patches: Path) -> dict:
    project, number = case.rsplit("-", 1)
    target, truth_path = workspace / "cases" / case, workspace / "truth" / f"{case}.json"
    if (target / "case.json").is_file() and truth_path.is_file():
        return {"case": case, "status": "ready"}
    patch = patches / f"{case}.patch"
    trigger = workspace / "trigger" / project / number
    if not patch.is_file() or not trigger.is_file():
        return {"case": case, "status": "excluded", "reason": "no developer patch or no trigger report"}
    sandbox = Defects4JSandbox(workspace / "work")
    directory = f"w-{case}"
    checkout = workspace / "work" / directory
    try:
        if not sandbox.checkout(project, int(number), "b", directory).ok:
            return {"case": case, "status": "excluded", "reason": "checkout failed"}
        source = sandbox.export(directory, "dir.src.classes").output.strip()
        tests = sandbox.export(directory, "dir.src.tests").output.strip()
        if not source or not tests or not (checkout / source).is_dir():
            return {"case": case, "status": "excluded", "reason": "source directories not reported"}
        sites = lineage.edit_sites(patch.read_text(encoding="utf-8", errors="replace"), source)
        if not sites or any(not (checkout / site["path"]).is_file() for site in sites):
            return {"case": case, "status": "excluded", "reason": "no edit site in an existing production file"}
        report = trigger.read_text(encoding="utf-8", errors="replace")[:400_000]
        failing = lineage.re.findall(r"^--- (\S+)\s*$", report, flags=lineage.re.MULTILINE)
        if not failing:
            return {"case": case, "status": "excluded", "reason": "trigger report names no test"}
        shutil.rmtree(target, ignore_errors=True)
        _copy_java(checkout / source, target / "tree" / source)
        if (checkout / tests).is_dir():
            _copy_java(checkout / tests, target / "tree" / tests)
        body = {"source_directory": source, "test_directory": tests, "failing_tests": failing, "report": report}
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(json.dumps({"case": case, "sites": sites}, sort_keys=True), encoding="utf-8")
        (target / "case.json").write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
        return {"case": case, "status": "ready"}
    finally:
        shutil.rmtree(checkout, ignore_errors=True)


def prepare(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    for name in ("work", "cases", "truth", "trigger"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    if not any((workspace / "trigger").iterdir()):
        copied = Defects4JSandbox(workspace).execute(["sh", "-c", (
            "for p in /defects4j/framework/projects/*/trigger_tests; do n=$(basename $(dirname $p)); "
            "mkdir -p /work/trigger/$n && cp $p/* /work/trigger/$n/; done")])
        if not copied.ok:
            raise SystemExit("could not read the trigger reports from the image")
    cases = sorted(json.loads(SPLIT.read_text(encoding="utf-8"))["development"])
    if arguments.limit:
        cases = cases[:arguments.limit]
    log = workspace / "prepare.jsonl"
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool, log.open("a", encoding="utf-8") as stream:
        for record in pool.map(lambda case: prepare_case(case, workspace, Path(arguments.patches)), cases):
            stream.write(json.dumps(record, sort_keys=True) + "\n")
            stream.flush()
    print(json.dumps({"cases": len(cases), "ready": sum((workspace / "cases" / case / "case.json").is_file()
                                                        for case in cases)}))


# -- plan ---------------------------------------------------------------------------------------


def load_truth(workspace: Path, cases) -> dict:
    return {case: json.loads((workspace / "truth" / f"{case}.json").read_text(encoding="utf-8"))["sites"]
            for case in cases}


def case_digest(workspace: Path, case: str) -> str:
    return digest_of({
        "case": (workspace / "cases" / case / "case.json").read_text(encoding="utf-8"),
        "truth": (workspace / "truth" / f"{case}.json").read_text(encoding="utf-8"),
    })


def plan(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    development = sorted(json.loads(SPLIT.read_text(encoding="utf-8"))["development"])
    ready = [case for case in development if (workspace / "cases" / case / "case.json").is_file()
             and (workspace / "truth" / f"{case}.json").is_file()]
    roles: dict[str, list[str]] = {"training": [], "selection": [], "validation": []}
    for case in ready:
        roles[lineage.role_of(case)].append(case)
    envelope = Envelope(model=arguments.model, max_tokens=20_000)
    body = {
        "schema": "genesis-localizer-lineage-plan-v1", "lineage": arguments.name,
        "split_digest": json.loads(SPLIT.read_text(encoding="utf-8"))["split_digest"],
        "development_cases": len(development), "prepared_cases": len(ready),
        "excluded_cases": sorted(set(development) - set(ready)),
        "roles": roles, "role_rule": f"sha256({lineage.SPLIT_DOMAIN!r} + case) mod 10: 0-2 training, 3-6 selection, 7-9 validation",
        "case_digests": {case: case_digest(workspace, case) for case in ready},
        "seed_source_sha256": lineage.source_digest(SEED.read_text(encoding="utf-8")),
        "measure": {"max_locations": lineage.MAX_LOCATIONS, "window_lines": lineage.WINDOW,
                    "case_seconds": lineage.CASE_SECONDS, "primary": "localized: every edit site covered"},
        "protocol": {
            "generations": arguments.generations, "attempts_per_generation": arguments.attempts,
            "patience_generations": arguments.patience, "selection_margin": arguments.margin,
            "selection_alpha": arguments.alpha, "memory_of_earlier_attempts": not arguments.no_memory,
            "rule": ("each attempt is written from the champion's training misses; the attempt with the most "
                     "training cases localized, if more than the champion, is scored on the selection cases "
                     "and replaces the champion when gained - lost >= margin and the one-sided exact sign "
                     "test <= alpha; validation cases are scored once by verify after the lineage is frozen"),
        },
        "envelope": {"model": envelope.model, "max_output_tokens": envelope.max_tokens,
                     "max_price_per_million_tokens": dict(envelope.max_price)},
        "spending_ceiling_usd": arguments.ceiling, "python_image": PYTHON_IMAGE,
        "held_out_cases_involved": 0, "machinery": machinery(),
    }
    record = seal(HOME / arguments.name / "PLAN.json", body, "plan_digest")
    print(json.dumps({key: len(value) for key, value in roles.items()} | {"plan_digest": record["plan_digest"]}))


# -- evolve -------------------------------------------------------------------------------------


def checked_plan(name: str, workspace: Path) -> dict:
    record = sealed(HOME / name / "PLAN.json", "plan_digest")
    if record["machinery"] != machinery():
        raise SystemExit("the machinery changed since the plan was frozen")
    for case, expected in record["case_digests"].items():
        if case_digest(workspace, case) != expected:
            raise SystemExit(f"{case}: prepared case differs from the planned one")
    return record


def slim(evaluation: dict) -> dict:
    """An evaluation without the returned locations: enough to recount, small enough to keep."""
    return {**{key: value for key, value in evaluation.items() if key != "cases"},
            "cases": {name: {key: value for key, value in row.items() if key != "locations"}
                      for name, row in evaluation["cases"].items()}}


def evolve(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    home = HOME / arguments.name
    protocol, roles = record["protocol"], record["roles"]
    scored = roles["training"] + roles["selection"]
    truth = load_truth(workspace, scored)
    envelope = Envelope(model=record["envelope"]["model"], max_tokens=record["envelope"]["max_output_tokens"],
                        max_price=tuple(sorted(record["envelope"]["max_price_per_million_tokens"].items())))
    scratch = workspace / "runs"
    scratch.mkdir(exist_ok=True)

    def measure(source: str, cases) -> dict:
        outputs = lineage.run_module(source, cases, image=record["python_image"],
                                     cases_directory=workspace / "cases", scratch=scratch)
        return lineage.evaluate(outputs, truth, cases)

    state_path = home / "STATE.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        seed_source = SEED.read_text(encoding="utf-8")
        (home / "modules").mkdir(parents=True, exist_ok=True)
        (home / "modules" / "g0.py.txt").write_text(seed_source, encoding="utf-8")
        state = {"champion": "g0", "generation": 0, "idle_generations": 0, "spent_usd": 0.0,
                 "attempts": [], "chain": ["g0"], "calls": [], "finished": None,
                 "evaluations": {"g0": {"training": measure(seed_source, roles["training"]),
                                        "selection": measure(seed_source, roles["selection"])}}}
    ledger = Ledger(record["spending_ceiling_usd"], state["spent_usd"])

    def save() -> None:
        state["spent_usd"] = ledger.spent
        state_path.write_text(json.dumps(state, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    save()
    while state["finished"] is None:
        if state["generation"] >= protocol["generations"]:
            state["finished"] = "generation limit"
            break
        if state["idle_generations"] >= protocol["patience_generations"]:
            state["finished"] = "no promotion for the allowed number of generations"
            break
        generation = state["generation"] + 1
        champion = state["champion"]
        champion_source = (home / "modules" / f"{champion}.py.txt").read_text(encoding="utf-8")
        champion_training = state["evaluations"][champion]["training"]
        archive = (lineage.archive_report(state["attempts"]) if protocol["memory_of_earlier_attempts"]
                   else "Not provided in this lineage.")
        best = None
        try:
            for index in range(1, protocol["attempts_per_generation"] + 1):
                name = f"g{generation}a{index}"
                report = lineage.training_report(champion_training, truth, workspace / "cases",
                                                 offset=(generation * 7 + index * 3))
                written = lineage.write_successor(champion_source, report, archive, envelope, ledger)
                for call in written["calls"]:
                    if call["cost_usd"] is None:
                        ledger.reserve(UNKNOWN_COST_USD)
                    state["calls"].append({**call, "attempt": name})
                attempt = {"name": name, "generation": generation, "index": index, "parent": champion,
                           "notes": written["notes"], "training_cases": len(roles["training"])}
                if written["source"] is None:
                    attempt.update(outcome="no usable module", training_localized=None)
                else:
                    (home / "modules" / f"{name}.py.txt").write_text(written["source"], encoding="utf-8")
                    training = measure(written["source"], roles["training"])
                    attempt.update(source_sha256=lineage.source_digest(written["source"]),
                                   training_localized=training["localized"], training=slim(training),
                                   outcome="not better on training")
                    if training["localized"] > champion_training["localized"] and (
                            best is None or training["localized"] > best[1]["localized"]):
                        best = (attempt, training, written["source"])
                state["attempts"].append(attempt)
                save()
                print(json.dumps({"attempt": name, "training": attempt["training_localized"],
                                  "champion_training": champion_training["localized"],
                                  "spent_usd": round(ledger.spent, 4)}), flush=True)
        except (BudgetExhausted, ModelUnavailable) as error:
            state["finished"] = f"stopped: {type(error).__name__}: {error}"
            break
        promoted = False
        if best is not None:
            attempt, training, source = best
            selection = measure(source, roles["selection"])
            comparison = lineage.compare(selection, state["evaluations"][champion]["selection"])
            attempt["selection"] = comparison
            promoted = lineage.promotes(comparison, protocol["selection_margin"], protocol["selection_alpha"])
            attempt["outcome"] = "promoted" if promoted else "rejected on unseen cases"
            if promoted:
                state["evaluations"][attempt["name"]] = {"training": training, "selection": selection}
                state["champion"] = attempt["name"]
                state["chain"].append(attempt["name"])
            print(json.dumps({"generation": generation, "candidate": attempt["name"], "promoted": promoted,
                              "selection": {key: comparison[key] for key in
                                            ("parent", "child", "gained", "lost", "one_sided_sign_test")}}), flush=True)
        state["generation"] = generation
        state["idle_generations"] = 0 if promoted else state["idle_generations"] + 1
        save()
    save()
    body = {"schema": "genesis-localizer-lineage-v1", "lineage": arguments.name, "plan_digest": record["plan_digest"],
            "chain": state["chain"], "finished": state["finished"], "generations_run": state["generation"],
            "attempts": state["attempts"], "calls": state["calls"], "spent_usd": ledger.spent,
            "known_cost_usd": sum(call["cost_usd"] or 0 for call in state["calls"]),
            "unknown_cost_calls": sum(call["cost_usd"] is None for call in state["calls"]),
            "champion_scores": {name: {role: {key: evaluation[role][key] for key in
                                              ("localized", "any_site", "all_files", "case_count", "errors")}
                                       for role in ("training", "selection")}
                                for name, evaluation in state["evaluations"].items()},
            "module_sha256": {path.name: lineage.source_digest(path.read_text(encoding="utf-8"))
                              for path in sorted((home / "modules").glob("*.py.txt"))}}
    seal(home / "LINEAGE.json", body, "lineage_digest")
    print(json.dumps({"chain": state["chain"], "finished": state["finished"], "spent_usd": round(ledger.spent, 4)}))


# -- verify -------------------------------------------------------------------------------------


def verify(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    home = HOME / arguments.name
    frozen = sealed(home / "LINEAGE.json", "lineage_digest")
    if (home / "VALIDATION.json").exists():
        raise SystemExit("the validation cases were already scored for this lineage")
    cases = record["roles"]["validation"]
    truth = load_truth(workspace, cases)
    scratch = workspace / "runs"
    scratch.mkdir(exist_ok=True)
    evaluations = {}
    for name in frozen["chain"]:
        source = (home / "modules" / f"{name}.py.txt").read_text(encoding="utf-8")
        if lineage.source_digest(source) != frozen["module_sha256"][f"{name}.py.txt"]:
            raise SystemExit(f"{name}: module differs from the frozen lineage")
        outputs = lineage.run_module(source, cases, image=record["python_image"],
                                     cases_directory=workspace / "cases", scratch=scratch)
        evaluations[name] = lineage.evaluate(outputs, truth, cases)
    chain = frozen["chain"]
    steps = [{"parent": chain[index - 1], "child": chain[index],
              **lineage.compare(evaluations[chain[index]], evaluations[chain[index - 1]])}
             for index in range(1, len(chain))]
    body = {"schema": "genesis-localizer-validation-v1", "lineage": arguments.name,
            "lineage_digest": frozen["lineage_digest"], "validation_cases": len(cases),
            "scores": {name: {key: evaluation[key] for key in ("localized", "any_site", "all_files", "errors")}
                       for name, evaluation in evaluations.items()},
            "steps": steps,
            "seed_to_final": (lineage.compare(evaluations[chain[-1]], evaluations[chain[0]])
                              if len(chain) > 1 else None),
            "evaluations": {name: slim(evaluation) for name, evaluation in evaluations.items()}}
    seal(home / "VALIDATION.json", body, "validation_digest")
    print(json.dumps({"scores": body["scores"], "seed_to_final": body["seed_to_final"] and {
        key: body["seed_to_final"][key] for key in ("parent", "child", "gained", "lost", "one_sided_sign_test")}}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("prepare", prepare), ("plan", plan), ("evolve", evolve), ("verify", verify)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--workspace", required=True)
        if name == "prepare":
            command.add_argument("--patches", required=True)
            command.add_argument("--workers", type=int, default=3)
            command.add_argument("--limit", type=int, default=0)
        else:
            command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--model", default="anthropic/claude-haiku-5.5")
            command.add_argument("--generations", type=int, default=8)
            command.add_argument("--attempts", type=int, default=3)
            command.add_argument("--patience", type=int, default=3)
            command.add_argument("--margin", type=int, default=5)
            command.add_argument("--alpha", type=float, default=0.05)
            command.add_argument("--ceiling", type=float, default=2.0)
            command.add_argument("--no-memory", action="store_true")
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
