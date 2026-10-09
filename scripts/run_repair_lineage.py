"""Grow a self-revising repair lineage on development cases, then score it once on held-out ones.

    # 1. choose development cases, record the seed genome, the envelope and the rules
    python scripts/run_repair_lineage.py plan --name LINEAGE1 --workspace /srv/genesis/lineage1
    # 2. commit the plan, then let the lineage rewrite itself (resumable)
    python scripts/run_repair_lineage.py evolve --name LINEAGE1 --workspace /srv/genesis/lineage1
    # 3. does the final genome's improver write better successors than the seed's? (development)
    python scripts/run_repair_lineage.py meta --name LINEAGE1 --workspace /srv/genesis/lineage1
    # 4. freeze seed and final genome against the next held-out cases; commit; run once
    python scripts/run_repair_lineage.py freeze --name LINEAGE1 --trial L1 --held-out 40
    python scripts/run_repair_lineage.py heldout --name LINEAGE1 --trial L1 --workspace /srv/genesis/lineage1

Only development cases are used before step 4, and an improver only ever sees results on the
training half of them. A held-out case is consumed the moment ``freeze`` names it. The fixed
revision of a case is never checked out. OPENROUTER_API_KEY is read from the environment.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox, SandboxLimits  # noqa: E402
from genesis.repair_bench import RepairBenchError, collect_evidence, next_held_out, run_arm  # noqa: E402
from genesis.repair_lineage import (  # noqa: E402
    SEED_GENOME, Envelope, Ledger, checked_genome, exact_sign_test, genome_digest, lineage_proposer,
    promotes, training_report, write_successor,
)
from genesis.trust_root import digest_of  # noqa: E402

BENCH = ROOT / "experiment/bench"
SPLIT = BENCH / "REPAIR_BENCH_SPLIT_V1.json"
MACHINERY = (
    "genesis/repair_lineage.py", "genesis/repair_bench.py", "genesis/openrouter_repair.py",
    "genesis/repair_proposers.py", "genesis/defects4j_sandbox.py", "scripts/run_repair_lineage.py",
)
UNKNOWN_COST_USD = 0.02


def machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in MACHINERY}


def sealed(path: Path, key: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    body = {name: value for name, value in record.items() if name != key}
    if record.get(key) != digest_of(body):
        raise SystemExit(f"{path.name}: {key} does not match its content")
    return record


def seal(path: Path, body: dict, key: str) -> dict:
    record = {**body, key: digest_of(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return record


def envelope_of(plan: dict) -> Envelope:
    given = plan["envelope"]
    return Envelope(
        model=given["model"], validations=given["validations_per_case"], requests=given["model_requests_per_case"],
        max_tokens=given["max_output_tokens_per_request"], prompt_characters=given["max_prompt_characters"],
        max_price=tuple(sorted(given["max_price_per_million_tokens"].items())),
    )


class Journal(list):
    """Every model request is written down before anything else can go wrong."""

    def __init__(self, path: Path, label: dict):
        super().__init__()
        self.path, self.label = path, label

    def append(self, record):
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**self.label, "call": record}, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        super().append(record)


def ledger_for(workspace: Path, ceiling: float) -> Ledger:
    spent, journal = 0.0, workspace / "calls.jsonl"
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            cost = json.loads(line)["call"].get("cost_usd")
            spent += UNKNOWN_COST_USD if cost is None else cost
    return Ledger(ceiling, spent)


def sandbox_for(workspace: Path) -> Defects4JSandbox:
    return Defects4JSandbox(workspace, limits=SandboxLimits(timeout_seconds=2400))


def prepare(workspace: Path, case: str) -> dict:
    """Check the buggy revision out and collect its evidence once. Cached in the workspace."""
    cache = workspace / "evidence" / f"{case}.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    project, bug = case.rsplit("-", 1)
    directory, sandbox = f"{case}-b", sandbox_for(workspace)
    try:
        if not (workspace / directory).is_dir() and not sandbox.checkout(project, int(bug), "b", directory).ok:
            raise RepairBenchError("checkout failed")
        outcome = {"case": case, "usable": True, "evidence": collect_evidence(sandbox, directory)}
    except RepairBenchError as error:
        outcome = {"case": case, "usable": False, "reason": str(error)}
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(outcome, sort_keys=True), encoding="utf-8")
    return outcome


def restore(workspace: Path, case: str, source_directory: str) -> None:
    """Undo a candidate left behind by an interrupted validation."""
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "checkout", "--", source_directory],
        cwd=workspace / f"{case}-b", check=True, capture_output=True,
    )


def run_case(workspace: Path, case: str, genome: dict, envelope: Envelope, ledger: Ledger, label: str) -> dict:
    evidence = prepare(workspace, case)["evidence"]
    restore(workspace, case, evidence["source_directory"])
    calls = Journal(workspace / "calls.jsonl", {"case": case, "genome": genome_digest(genome), "label": label})
    started = time.monotonic()
    arm = run_arm(
        sandbox_for(workspace), f"{case}-b", evidence, lineage_proposer(genome, envelope, ledger, calls),
        envelope.validations, max_rounds=genome["search"]["rounds"],
    )
    return {
        "case": case, "solved": arm["solved"], "validated": arm["validated"], "rounds": arm["rounds"],
        "verdicts": arm["verdicts"], "plausible_patch": arm["plausible_patch"],
        "plausible_squashed_sha256": arm["plausible_squashed_sha256"], "calls": list(calls),
        "failing_tests": len(evidence["failing_tests"]),
        "suspects_from_stack_trace": evidence["suspects_from_stack_trace"],
        "seconds": round(time.monotonic() - started, 1),
    }


def evaluate(workspace: Path, genome: dict, cases: list[str], envelope: Envelope, ledger: Ledger, label: str,
             parallel: int) -> dict:
    """One genome on every case. A finished case is kept; an interrupted run resumes."""
    digest = genome_digest(genome)
    folder = workspace / "runs" / f"{label}-{digest[:12]}"
    folder.mkdir(parents=True, exist_ok=True)

    def one(case: str) -> dict:
        target = folder / f"{case}.json"
        if target.exists():
            return json.loads(target.read_text(encoding="utf-8"))
        outcome = run_case(workspace, case, genome, envelope, ledger, label)
        target.write_text(json.dumps(outcome, sort_keys=True), encoding="utf-8")
        print(f"  {label} {case}: {'solved' if outcome['solved'] else 'unsolved'} "
              f"({outcome['validated']} validated, {outcome['seconds']:.0f}s, spent {ledger.spent:.3f})", flush=True)
        return outcome

    with ThreadPoolExecutor(max_workers=parallel) as pool:
        outcomes = list(pool.map(one, cases))
    body = {
        "schema": "genesis-repair-lineage-evaluation-v1", "label": label, "genome_digest": digest,
        "cases": {outcome["case"]: outcome for outcome in outcomes},
        "solved": sum(outcome["solved"] for outcome in outcomes),
        "validated": sum(outcome["validated"] for outcome in outcomes),
        "model_requests": sum(len(outcome["calls"]) for outcome in outcomes),
        "cost_usd": round(sum(call.get("cost_usd") or 0 for outcome in outcomes for call in outcome["calls"]), 6),
        "calls_with_unknown_cost": sum(call.get("cost_usd") is None for outcome in outcomes for call in outcome["calls"]),
    }
    return {**body, "evaluation_digest": digest_of(body)}


def solved_on(evaluation: dict, names: list[str]) -> int:
    return sum(bool(evaluation["cases"][name]["solved"]) for name in names)


def successor(workspace: Path, tag: str, parent: dict, report: str, envelope: Envelope, ledger: Ledger,
              improver: str | None = None) -> dict:
    """Ask for a successor once; the answer is kept so that a resumed run does not ask again."""
    target = workspace / "successors" / f"{tag}.json"
    if target.exists():
        return json.loads(target.read_text(encoding="utf-8"))
    written = write_successor(parent, report, envelope, ledger, improver=improver)
    journal = Journal(workspace / "calls.jsonl", {"label": tag, "genome": genome_digest(parent)})
    for call in written["calls"]:
        journal.append(call)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(written, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return written


# -- commands ---------------------------------------------------------------------------------


def plan(arguments: argparse.Namespace) -> int:
    folder = BENCH / arguments.name
    if (folder / "PLAN.json").exists():
        raise SystemExit("PLAN.json already exists")
    split = sealed(SPLIT, "split_digest")
    arguments.workspace.mkdir(parents=True, exist_ok=True)
    if not Defects4JSandbox(arguments.workspace).probe()["isolated"]:
        raise SystemExit("the Defects4J boundary does not hold; refusing to run")
    wanted = arguments.training + arguments.selection
    order = list(reversed(split["development"]))  # hash order from the end: decided by the split, not by us
    usable, skipped, cursor = [], [], 0
    while len(usable) < wanted:
        batch = order[cursor:cursor + arguments.parallel]
        if not batch:
            raise SystemExit("development cases exhausted")
        cursor += len(batch)
        with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
            for outcome in pool.map(lambda case: prepare(arguments.workspace, case), batch):
                (usable if outcome["usable"] else skipped).append(
                    outcome["case"] if outcome["usable"] else {"case": outcome["case"], "reason": outcome["reason"]})
                print(outcome["case"], "usable" if outcome["usable"] else outcome["reason"], flush=True)
    usable = [case for case in order if case in usable][:wanted]
    seed = checked_genome(SEED_GENOME)
    envelope = Envelope(model=arguments.model)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": "genesis-repair-lineage-plan-v1", "name": arguments.name,
        "split_digest": split["split_digest"],
        "development_case_rule": "development cases in reverse split order; the first usable ones, alternately "
                                 "training and selection",
        "training_cases": usable[0::2][:arguments.training], "selection_cases": usable[1::2][:arguments.selection],
        "skipped_unusable": skipped,
        "seed_genome": seed, "seed_genome_digest": genome_digest(seed),
        "envelope": envelope.record(), "generations": arguments.generations,
        "spending_ceiling_usd": arguments.ceiling,
        "successor_rule": "the current genome's improver text, its own results on the training cases (names "
                          "withheld) and the envelope are given to the same model, which writes one successor",
        "promotion_rule": "a successor replaces its parent when it repairs strictly more development cases and "
                          "no fewer selection cases; the parent's recorded evaluation is not rerun",
        "meta_rule": "from the seed genome and its recorded training report, two successors are written with the "
                     "seed improver text (generation 1 counts as the first) and two with the final genome's "
                     "improver text; each is evaluated on all development cases; the comparison is void if the "
                     "improver text never changed",
        "held_out_rule": "after the lineage ends, seed and final genome are frozen with the next unused held-out "
                         "cases and each case is run once per genome under the same envelope",
        "acceptance": "a case is repaired when one validated candidate passes the full developer test suite",
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "claim_boundary": "development results select genomes and prove nothing; only the held-out comparison "
                          "measures improvement, and neither outcome establishes general recursive self-improvement",
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    seal(folder / "PLAN.json", body, "plan_digest")
    print(f"training {body['training_cases']}\nselection {body['selection_cases']}")
    return 0


def _context(arguments: argparse.Namespace) -> tuple[Path, dict, Envelope, Ledger, list[str]]:
    folder = BENCH / arguments.name
    recorded = sealed(folder / "PLAN.json", "plan_digest")
    if recorded["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the plan")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    ledger = ledger_for(arguments.workspace, recorded["spending_ceiling_usd"])
    return folder, recorded, envelope_of(recorded), ledger, recorded["training_cases"] + recorded["selection_cases"]


def evolve(arguments: argparse.Namespace) -> int:
    folder, recorded, envelope, ledger, cases = _context(arguments)
    if (folder / "LINEAGE.json").exists():
        raise SystemExit("LINEAGE.json already exists; a lineage is grown once")
    training, selection = recorded["training_cases"], recorded["selection_cases"]
    current = recorded["seed_genome"]
    current_eval = evaluate(arguments.workspace, current, cases, envelope, ledger, "gen0", arguments.parallel)
    seal(folder / "GEN0_EVALUATION.json", {k: v for k, v in current_eval.items() if k != "evaluation_digest"},
         "evaluation_digest")
    print(f"gen0 solved {current_eval['solved']}/{len(cases)}", flush=True)
    generations, current_generation = [], 0
    for number in range(1, recorded["generations"] + 1):
        written = successor(arguments.workspace, f"gen{number}", current,
                            training_report(current_eval, training), envelope, ledger)
        entry = {"generation": number, "parent_generation": current_generation,
                 "parent_digest": genome_digest(current), "rationale": written["rationale"],
                 "successor_calls": written["calls"], "genome": written["genome"]}
        if written["genome"] is None:
            entry.update({"decision": "no_valid_successor"})
        elif genome_digest(written["genome"]) == genome_digest(current):
            entry.update({"decision": "identical_to_parent", "genome_digest": genome_digest(current)})
        else:
            child = written["genome"]
            child_eval = evaluate(arguments.workspace, child, cases, envelope, ledger, f"gen{number}", arguments.parallel)
            seal(folder / f"GEN{number}_EVALUATION.json",
                 {k: v for k, v in child_eval.items() if k != "evaluation_digest"}, "evaluation_digest")
            promoted = promotes(child_eval, current_eval, selection)
            entry.update({
                "genome_digest": genome_digest(child), "decision": "promoted" if promoted else "rejected",
                "child": {"solved": child_eval["solved"], "training": solved_on(child_eval, training),
                          "selection": solved_on(child_eval, selection)},
                "parent": {"solved": current_eval["solved"], "training": solved_on(current_eval, training),
                           "selection": solved_on(current_eval, selection)},
            })
            if promoted:
                current, current_eval, current_generation = child, child_eval, number
        generations.append(entry)
        print(f"gen{number}: {entry['decision']} {entry.get('child')} vs parent {entry.get('parent')}", flush=True)
    body = {
        "schema": "genesis-repair-lineage-v1", "name": recorded["name"], "plan_digest": recorded["plan_digest"],
        "generations": generations, "final_generation": current_generation,
        "final_genome": current, "final_genome_digest": genome_digest(current),
        "seed_genome_digest": recorded["seed_genome_digest"],
        "improver_text_changed": current["improver"] != recorded["seed_genome"]["improver"],
        "spent_usd_so_far": round(ledger.spent, 6),
    }
    seal(folder / "LINEAGE.json", body, "lineage_digest")
    return 0


def meta(arguments: argparse.Namespace) -> int:
    folder, recorded, envelope, ledger, cases = _context(arguments)
    lineage = sealed(folder / "LINEAGE.json", "lineage_digest")
    if (folder / "META.json").exists():
        raise SystemExit("META.json already exists")
    if not lineage["improver_text_changed"]:
        seal(folder / "META.json", {"schema": "genesis-repair-lineage-meta-v1", "void": True,
             "reason": "the improver text never changed", "lineage_digest": lineage["lineage_digest"]}, "meta_digest")
        return 0
    seed = recorded["seed_genome"]
    seed_eval = sealed(folder / "GEN0_EVALUATION.json", "evaluation_digest")
    report = training_report(seed_eval, recorded["training_cases"])
    arms = {"seed_improver": seed["improver"], "final_improver": lineage["final_genome"]["improver"]}
    children = []
    for index in (1, 2):
        for arm, text in arms.items():
            tag = f"meta-{arm}-{index}"
            first = lineage["generations"][0]
            if arm == "seed_improver" and index == 1 and (folder / "GEN1_EVALUATION.json").exists():
                # Generation 1 is exactly this: the seed improver's successor of the seed genome.
                written = {"genome": first["genome"], "calls": first["successor_calls"]}
                result = sealed(folder / "GEN1_EVALUATION.json", "evaluation_digest")
                entry = {"arm": arm, "index": index, "genome": written["genome"],
                         "successor_calls": written["calls"], "reused": "generation 1 of the lineage"}
            else:
                written = successor(arguments.workspace, tag, seed, report, envelope, ledger, improver=text)
                entry = {"arm": arm, "index": index, "genome": written["genome"], "successor_calls": written["calls"]}
                result = None
                if written["genome"] is not None:
                    result = evaluate(arguments.workspace, written["genome"], cases, envelope, ledger, tag,
                                      arguments.parallel)
            if result is not None:
                entry.update({"genome_digest": genome_digest(written["genome"]), "solved": result["solved"],
                              "solved_cases": sorted(n for n, c in result["cases"].items() if c["solved"]),
                              "cost_usd": result["cost_usd"]})
            children.append(entry)
            print(tag, entry.get("solved"), flush=True)
    body = {
        "schema": "genesis-repair-lineage-meta-v1", "void": False, "lineage_digest": lineage["lineage_digest"],
        "parent": "seed genome with its recorded training report", "seed_solved": seed_eval["solved"],
        "cases": len(cases), "children": children,
        "mean_solved": {arm: (sum(c.get("solved", 0) for c in children if c["arm"] == arm) / 2) for arm in arms},
        "low_power": "two successors per improver text on development cases; a difference here is suggestive only",
    }
    seal(folder / "META.json", body, "meta_digest")
    print(json.dumps(body["mean_solved"]))
    return 0


def _consumed() -> list[str]:
    spent: list[str] = []
    for path in sorted(BENCH.glob("TRIAL_*_PREREG.json")):
        record = sealed(path, "preregistration_digest")
        if record["held_out"]:
            spent.extend(record["cases"])
    return spent


def freeze(arguments: argparse.Namespace) -> int:
    folder = BENCH / arguments.name
    recorded = sealed(folder / "PLAN.json", "plan_digest")
    lineage = sealed(folder / "LINEAGE.json", "lineage_digest")
    target = BENCH / f"TRIAL_{arguments.trial}_PREREG.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    split = sealed(SPLIT, "split_digest")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": "genesis-repair-lineage-preregistration-v1", "name": arguments.trial, "held_out": True,
        "split_digest": split["split_digest"],
        "cases": next_held_out(split, _consumed(), arguments.held_out),
        "arms": {"seed": recorded["seed_genome_digest"], "final": lineage["final_genome_digest"]},
        "final_generation": lineage["final_generation"],
        "plan_digest": recorded["plan_digest"], "lineage_digest": lineage["lineage_digest"],
        "envelope": recorded["envelope"], "spending_ceiling_usd": arguments.ceiling,
        "arm_order": "seed first on even-numbered cases, final first on odd-numbered ones",
        "primary_comparison": "cases repaired by final versus by seed among usable cases; exact one-sided sign "
                              "test on the cases only one arm repairs",
        "acceptance": recorded["acceptance"], "plausible_is_not_correct": True,
        "benchmark_may_be_in_model_training_data": True,
        "claim_boundary": "a positive result shows that one bounded lineage produced a better configuration for a "
                          "fixed external model on these cases; it does not establish general recursive "
                          "self-improvement. A null or negative result is kept as such.",
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    if body["arms"]["seed"] == body["arms"]["final"]:
        body["degenerate"] = "no successor was promoted: both arms are the seed genome"
    seal(target, body, "preregistration_digest")
    print(f"{target.name}: {len(body['cases'])} held-out cases, final generation {lineage['final_generation']}")
    return 0


def heldout(arguments: argparse.Namespace) -> int:
    folder = BENCH / arguments.name
    recorded = sealed(folder / "PLAN.json", "plan_digest")
    lineage = sealed(folder / "LINEAGE.json", "lineage_digest")
    prereg = sealed(BENCH / f"TRIAL_{arguments.trial}_PREREG.json", "preregistration_digest")
    target = BENCH / f"TRIAL_{arguments.trial}_RESULT.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists; a trial is run once")
    if prereg["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the preregistration")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    genomes = {"seed": recorded["seed_genome"], "final": lineage["final_genome"]}
    if {arm: genome_digest(genome) for arm, genome in genomes.items()} != prereg["arms"]:
        raise SystemExit("genomes differ from the preregistration")
    envelope = envelope_of(prereg)
    # The trial has its own ceiling, on top of whatever development had spent when it started.
    base, spent_now = arguments.workspace / "heldout_base_spend", ledger_for(arguments.workspace, 0).spent
    if not base.exists():
        base.write_text(str(spent_now), encoding="utf-8")
    ledger = Ledger(float(base.read_text(encoding="utf-8")) + prereg["spending_ceiling_usd"], spent_now)
    store = arguments.workspace / "runs" / f"trial-{arguments.trial}"
    store.mkdir(parents=True, exist_ok=True)

    def one(item: tuple[int, str]) -> dict:
        index, case = item
        saved = store / f"{case}.json"
        if saved.exists():
            return json.loads(saved.read_text(encoding="utf-8"))
        prepared = prepare(arguments.workspace, case)
        if not prepared["usable"]:
            outcome = {"case": case, "usable": False, "reason": prepared["reason"], "arms": {}}
        else:
            order = ("seed", "final") if index % 2 == 0 else ("final", "seed")
            arms = {arm: run_case(arguments.workspace, case, genomes[arm], envelope, ledger, f"trial-{arm}")
                    for arm in order}
            outcome = {"case": case, "usable": True, "order": list(order), "arms": arms}
        saved.write_text(json.dumps(outcome, sort_keys=True), encoding="utf-8")
        print(case, {arm: data["solved"] for arm, data in outcome["arms"].items()} or outcome.get("reason"),
              f"spent {ledger.spent:.3f}", flush=True)
        return outcome

    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        cases = list(pool.map(one, enumerate(prereg["cases"])))
    usable = [case for case in cases if case["usable"]]
    table = {"both": 0, "seed_only": 0, "final_only": 0, "neither": 0}
    for case in usable:
        seed_solved, final_solved = case["arms"]["seed"]["solved"], case["arms"]["final"]["solved"]
        table["both" if seed_solved and final_solved else "seed_only" if seed_solved else
              "final_only" if final_solved else "neither"] += 1
    calls = {arm: [call for case in usable for call in case["arms"][arm]["calls"]] for arm in genomes}
    body = {
        "schema": "genesis-repair-lineage-result-v1", "name": prereg["name"], "held_out": True,
        "preregistration_digest": prereg["preregistration_digest"], "cases": cases,
        "summary": {
            "cases": len(cases), "usable_cases": len(usable),
            "solved": {arm: sum(case["arms"][arm]["solved"] for case in usable) for arm in genomes},
            "paired": table,
            "one_sided_exact_sign_test_p": round(exact_sign_test(table["seed_only"], table["final_only"]), 6),
            "validated": {arm: sum(case["arms"][arm]["validated"] for case in usable) for arm in genomes},
            "model_requests": {arm: len(calls[arm]) for arm in genomes},
            "cost_usd": {arm: round(sum(call.get("cost_usd") or 0 for call in calls[arm]), 6) for arm in genomes},
            "calls_with_unknown_cost": {arm: sum(call.get("cost_usd") is None for call in calls[arm]) for arm in genomes},
        },
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "fixed_revision_consulted": False,
    }
    seal(target, body, "result_digest")
    print(json.dumps(body["summary"], indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, handler in (("plan", plan), ("evolve", evolve), ("meta", meta), ("freeze", freeze), ("heldout", heldout)):
        command = commands.add_parser(name)
        command.add_argument("--name", required=True)
        if name != "freeze":
            command.add_argument("--workspace", type=Path, required=True)
            command.add_argument("--parallel", type=int, default=3)
        if name == "plan":
            command.add_argument("--training", type=int, default=10)
            command.add_argument("--selection", type=int, default=10)
            command.add_argument("--generations", type=int, default=4)
            command.add_argument("--model", default="anthropic/claude-haiku-5.5")
            command.add_argument("--ceiling", type=float, default=1.5)
        if name in ("freeze", "heldout"):
            command.add_argument("--trial", required=True)
        if name == "freeze":
            command.add_argument("--held-out", type=int, default=40)
            command.add_argument("--ceiling", type=float, default=1.0)
        command.set_defaults(handler=handler)
    arguments = parser.parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
