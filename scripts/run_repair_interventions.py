#!/usr/bin/env python3
"""What limits the repair agent? Read how its attempts ended, then change one component at a time.

    stops         from sealed records of the seed agent, how failed attempts ended and what they
                  left unused; no model, nothing run
    preregister   the cases the seed agent failed at least every other time in those records, the
                  control and the variants, before anything runs
    run           every arm on every case, then the diagnosis

The cases are development cases the agent has already failed: the trial says which change recovers
them, not how often the agent repairs. The control arm reruns the unchanged agent, so that a case
lost by chance earlier is not credited to a change. No held-out case is involved.
OPENROUTER_API_KEY is read from the environment by ``run``.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox, SandboxLimits  # noqa: E402
from genesis import intervention_diagnosis as interventions  # noqa: E402
from genesis import repair_interventions as repair  # noqa: E402
from genesis.located_evidence import located  # noqa: E402
from genesis.openrouter_repair import inspect_tool  # noqa: E402
from genesis.repair_bench import RepairBenchError, collect_evidence, run_arm  # noqa: E402
from genesis.repair_lineage import (  # noqa: E402
    SEED_GENOME, BudgetExhausted, Envelope, Ledger, ModelUnavailable, genome_digest, lineage_proposer,
)
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/g12"
RECORDS = (
    ("experiment/localizer/LOCALIZER1/DEV_LOCALIZED_REPAIR1_RESULT.json", "arms"),
    ("experiment/localizer/PROGRAMS1/DEV_COVERAGE_REPAIR1_RESULT.json", "arms"),
    ("experiment/bench/LINEAGE1/GEN0_EVALUATION.json", "evaluation"),
    ("experiment/bench/LINEAGE2/GEN0_EVALUATION.json", "evaluation"),
)
CASE_DOMAIN = "genesis-repair-interventions-v1|"
MACHINERY = ("genesis/intervention_diagnosis.py", "genesis/repair_interventions.py", "genesis/located_evidence.py",
             "genesis/repair_lineage.py", "genesis/repair_bench.py", "genesis/openrouter_repair.py",
             "genesis/defects4j_sandbox.py", "scripts/run_repair_interventions.py")
UNKNOWN_COST_USD = 0.05
SEED_ENVELOPE = Envelope(model="anthropic/claude-haiku-5.5")


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


def recorded() -> tuple[dict, dict]:
    """Every sealed attempt of the seed agent, by case, and the files they come from."""
    attempts: dict[str, list] = {}
    sources = {}
    seed = genome_digest(SEED_GENOME)
    for name, layout in RECORDS:
        raw = (ROOT / name).read_bytes()
        record = json.loads(raw)
        sources[name] = hashlib.sha256(raw).hexdigest()
        if layout == "arms":
            for case in record["cases"]:
                for arm, attempt in case.get("arms", {}).items():
                    attempts.setdefault(case["case"], []).append({"source": name, "arm": arm, **attempt})
        else:
            if record["genome_digest"] != seed:
                raise SystemExit(f"{name}: not an evaluation of the seed configuration")
            for label, attempt in record["cases"].items():
                attempts.setdefault(label.split("#")[0], []).append({"source": name, "arm": label, **attempt})
    return attempts, sources


def failing(attempts: dict) -> list[str]:
    """Cases the seed agent failed in at least half of two or more sealed attempts."""
    return sorted((case for case, rows in attempts.items()
                   if len(rows) >= 2 and 2 * sum(not row["solved"] for row in rows) >= len(rows)),
                  key=lambda case: hashlib.sha256((CASE_DOMAIN + case).encode()).hexdigest())


def stops(arguments) -> None:
    target = HOME / f"{arguments.name}.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    attempts, sources = recorded()
    limits = {"requests": SEED_ENVELOPE.requests, "validations": SEED_ENVELOPE.validations}
    everything = [row for rows in attempts.values() for row in rows]
    hard = failing(attempts)
    body = {
        "schema": "genesis-repair-stops-v1", "name": arguments.name, "held_out": False, "model_requests": 0,
        "sources": sources, "seed_genome_digest": genome_digest(SEED_GENOME), "envelope": SEED_ENVELOPE.record(),
        "cases": len(attempts), "all_attempts": repair.stops(everything, **limits),
        "by_source": {name: repair.stops([row for row in everything if row["source"] == name], **limits)
                      for name, _ in RECORDS},
        "cases_failed_in_half_or_more_of_two_or_more_attempts": hard,
        "attempts_on_those_cases": repair.stops([row for case in hard for row in attempts[case]], **limits),
        "reading": ("counts of recorded endings; they say where attempts stop, not why, and not what a change "
                    "would recover"),
    }
    seal(target, body, "stops_digest")
    print(json.dumps({key: body[key] for key in ("cases", "all_attempts", "attempts_on_those_cases")}, indent=2))
    print("failing cases:", len(hard))


def preregister(arguments) -> None:
    target = HOME / f"{arguments.name}_PREREG.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    attempts, sources = recorded()
    hard = failing(attempts)
    development = Path(arguments.development).resolve()
    chosen = hard[:arguments.cases]
    truth = {}
    for case in chosen:
        path = development / "truth" / f"{case}.json"
        if not path.is_file():
            raise SystemExit(f"{case}: no recorded edit sites")
        truth[case] = repair.oracle_locations(json.loads(path.read_text(encoding="utf-8"))["sites"])
    with_model = chosen[:arguments.model_cases]
    arms = [repair.CONTROL, *repair.VARIANTS]
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": "genesis-repair-interventions-preregistration-v1", "name": arguments.name, "held_out": False,
        "sources": sources, "seed_genome_digest": genome_digest(SEED_GENOME),
        "case_rule": (f"development cases with at least two sealed attempts of the seed agent in the sources and "
                      f"at least half of them failed, ordered by sha256({CASE_DOMAIN!r} + case), first {arguments.cases}"),
        "failing_cases": len(hard), "cases": chosen,
        "sealed_failures_per_case": {case: sum(not row["solved"] for row in attempts[case]) for case in chosen},
        "sealed_attempts_per_case": {case: len(attempts[case]) for case in chosen},
        "arms": {arm: repair.configuration(arm, SEED_ENVELOPE.model) for arm in arms},
        "model_arm_cases": with_model,
        "model_arm_rule": f"the model arm is run on the first {arguments.model_cases} cases only, to bound spending",
        "oracle_locations": truth,
        "oracle_note": "taken from the developers' patch; an upper bound for any localizer, never part of the agent",
        "arm_order": "rotated per case by intervention_diagnosis.order",
        "primary_comparison": ("each variant against the control on the cases that have both: cases only the "
                               "variant repairs against cases only the control repairs, exact one-sided sign test"),
        "naming_rule": {"margin": arguments.margin, "level": 0.05,
                        "text": "a component is named as limiting when its variant gains at least the margin net "
                                "and the test passes the level; no correction for the six comparisons is applied, "
                                "which the report must say"},
        "separate_environment": True, "spending_ceiling_usd": arguments.ceiling,
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "claim_boundary": ("a development diagnosis on cases chosen because the agent failed them; it names what "
                           "to change next and estimates no repair rate; a change it names still has to be judged "
                           "on cases the agent has not met"),
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    seal(target, body, "preregistration_digest")
    print(json.dumps({"failing": len(hard), "chosen": len(chosen), "model_arm": len(with_model),
                      "arms": arms}))


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


def envelope_of(given: dict) -> Envelope:
    return Envelope(model=given["model"], validations=given["validations_per_case"],
                    requests=given["model_requests_per_case"], max_tokens=given["max_output_tokens_per_request"],
                    prompt_characters=given["max_prompt_characters"],
                    max_price=tuple(sorted(given["max_price_per_million_tokens"].items())))


def run(arguments) -> None:
    prereg = sealed(HOME / f"{arguments.name}_PREREG.json", "preregistration_digest")
    target = HOME / f"{arguments.name}_RESULT.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists; a trial is run once")
    if prereg["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the preregistration")
    for arm, given in prereg["arms"].items():
        if given != repair.configuration(arm, SEED_ENVELOPE.model):
            raise SystemExit(f"{arm}: configuration differs from the preregistration")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    workspace = Path(arguments.workspace).resolve()
    (workspace / "runs").mkdir(parents=True, exist_ok=True)
    spent, journal = 0.0, workspace / "calls.jsonl"
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            cost = json.loads(line)["call"].get("cost_usd")
            spent += UNKNOWN_COST_USD if cost is None else cost
    ledger = Ledger(prereg["spending_ceiling_usd"], spent)
    sandbox = Defects4JSandbox(workspace, limits=SandboxLimits(timeout_seconds=2400))
    model_cases = set(prereg["model_arm_cases"])

    def one(case: str) -> dict:
        saved = workspace / "runs" / f"{case}.json"
        if saved.exists():
            return json.loads(saved.read_text(encoding="utf-8"))
        project, bug = case.rsplit("-", 1)
        directory = f"{case}-b"
        shutil.rmtree(workspace / directory, ignore_errors=True)
        try:
            try:
                if not sandbox.checkout(project, int(bug), "b", directory).ok:
                    raise RepairBenchError("checkout failed")
                collected = collect_evidence(sandbox, directory, separate_environment=True)
            except RepairBenchError as error:
                outcome = {"case": case, "usable": False, "reason": str(error), "arms": {}}
            else:
                names = [arm for arm in prereg["arms"] if arm != "model" or case in model_cases]
                order = interventions.order(case, names)
                arms = {}
                for arm in order:
                    given = prereg["arms"][arm]
                    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "checkout", "--",
                                    collected["source_directory"]], cwd=workspace / directory, check=True, capture_output=True)
                    evidence = collected
                    if arm == "oracle":
                        evidence = located(collected, workspace / directory, prereg["oracle_locations"][case], "oracle")
                    envelope = envelope_of(given["envelope"])
                    genome = {**SEED_GENOME, "search": given["search"]}
                    calls = Journal(journal, {"case": case, "arm": arm})
                    started = time.monotonic()
                    result = run_arm(
                        sandbox, directory, evidence,
                        lineage_proposer(genome, envelope, ledger, calls,
                                         inspector=repair.tolerant_inspect if given["tolerant_reading"] else inspect_tool),
                        envelope.validations, max_rounds=given["search"]["rounds"], persist=given["persist"])
                    arms[arm] = {"solved": result["solved"], "validated": result["validated"], "rounds": result["rounds"],
                                 "verdicts": result["verdicts"], "plausible_patch": result["plausible_patch"],
                                 "calls": list(calls), "seconds": round(time.monotonic() - started, 1),
                                 "evidence_digest": evidence["evidence_digest"]}
                outcome = {"case": case, "usable": True, "order": order, "arms": arms}
        finally:
            shutil.rmtree(workspace / directory, ignore_errors=True)
        saved.write_text(json.dumps(outcome, sort_keys=True), encoding="utf-8")
        print(case, {arm: data["solved"] for arm, data in outcome["arms"].items()} or outcome.get("reason"),
              f"spent {ledger.spent:.3f}", flush=True)
        return outcome

    try:
        with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
            cases = list(pool.map(one, prereg["cases"]))
    except (BudgetExhausted, ModelUnavailable) as error:
        raise SystemExit(f"stopped before the end, nothing sealed: {type(error).__name__}: {error}")
    usable = [case for case in cases if case["usable"]]
    outcomes = {case["case"]: {arm: data["solved"] for arm, data in case["arms"].items()} for case in usable}
    rule = prereg["naming_rule"]
    by_arm = {}
    for arm, given in prereg["arms"].items():
        attempts = [case["arms"][arm] for case in usable if arm in case["arms"]]
        calls = [call for attempt in attempts for call in attempt["calls"]]
        limits = given["envelope"]
        by_arm[arm] = {
            **repair.stops(attempts, requests=limits["model_requests_per_case"], validations=limits["validations_per_case"]),
            "model_requests": len(calls),
            "inspections": sum(len(call.get("inspections") or []) for call in calls),
            "validated_candidates": sum(attempt["validated"] for attempt in attempts),
            "cost_usd": round(sum(call.get("cost_usd") or 0 for call in calls), 6),
            "calls_with_unknown_cost": sum(call.get("cost_usd") is None for call in calls),
        }
    body = {
        "schema": "genesis-repair-interventions-result-v1", "name": prereg["name"], "held_out": False,
        "preregistration_digest": prereg["preregistration_digest"], "cases": cases,
        "summary": {
            "cases": len(cases), "usable_cases": len(usable),
            "diagnosis": interventions.diagnosis(
                outcomes, repair.CONTROL, {arm: given["component"] for arm, given in prereg["arms"].items()
                                           if arm != repair.CONTROL}, margin=rule["margin"], level=rule["level"]),
            "by_arm": by_arm,
            "cost_usd": round(sum(row["cost_usd"] for row in by_arm.values()), 6),
        },
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "fixed_revision_consulted": "by the oracle arm only, through the preregistered edit sites",
    }
    seal(target, body, "result_digest")
    print(json.dumps(body["summary"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("stops", stops), ("preregister", preregister), ("run", run)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--name", required=True)
        if name == "preregister":
            command.add_argument("--development", required=True, help="workspace holding the recorded edit sites")
            command.add_argument("--cases", type=int, default=36)
            command.add_argument("--model-cases", type=int, default=16)
            command.add_argument("--margin", type=int, default=3)
            command.add_argument("--ceiling", type=float, default=3.0)
        if name == "run":
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=4)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
