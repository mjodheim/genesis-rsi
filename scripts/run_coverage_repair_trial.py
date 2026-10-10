#!/usr/bin/env python3
"""Does covering the developer's edit make the repair agent repair? A paired development trial.

    preregister   among validation-role development cases, name those where exactly one of two
                  localizers covers every edit site, and both arms, before anything runs
    run           the same repair agent on each case twice, once told to look where each
                  localizer points

The earlier paired trial drew cases at random: on most of them both localizers covered the fix
or neither did, and the arms could not differ. Here every case is one where they do differ, in
either direction. Locations are those stored when the localizers were scored; the repair agent
never sees which arm covers the fix. No held-out case of the repair bench is involved.
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
from genesis import localizer_lineage as lineage  # noqa: E402
from genesis import localizer_programs as programs  # noqa: E402
from genesis.located_evidence import located  # noqa: E402
from genesis.repair_bench import RepairBenchError, collect_evidence, run_arm  # noqa: E402
from genesis.repair_lineage import (  # noqa: E402
    SEED_GENOME, BudgetExhausted, Envelope, Ledger, ModelUnavailable, exact_sign_test, genome_digest, lineage_proposer,
)
from genesis.trust_root import digest_of  # noqa: E402

LOCALIZERS = ROOT / "experiment/localizer"
ORDER_DOMAIN = "genesis-coverage-repair-v1|"
MACHINERY = ("genesis/located_evidence.py", "genesis/localizer_lineage.py", "genesis/localizer_programs.py",
             "genesis/repair_lineage.py", "genesis/repair_bench.py", "genesis/openrouter_repair.py",
             "genesis/defects4j_sandbox.py", "scripts/run_coverage_repair_trial.py")
UNKNOWN_COST_USD = 0.02
ARMS = ("champion", "program")


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


def preregister(arguments) -> None:
    home = LOCALIZERS / arguments.search
    plan = sealed(home / "PLAN.json", "plan_digest")
    frozen = sealed(home / "EVOLUTION.json", "evolution_digest")
    target = home / f"{arguments.name}_PREREG.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    if len(frozen["chain"]) < 2:
        raise SystemExit("no program was promoted: there is nothing to compare")
    champion, name = frozen["chain"][0], frozen["chain"][-1]
    cases = sealed(LOCALIZERS / "LOCALIZER1" / "PLAN.json", "plan_digest")["roles"]["validation"]
    development = Path(arguments.development).resolve()
    known = {}
    for member, entry in plan["archive"].items():
        text = (development / "recombination" / "answers" / (member.replace(":", "--") + ".json")).read_text(
            encoding="utf-8")
        if digest_of(text) != entry["development_answers_sha256"]:
            raise SystemExit(f"{member}: stored answers differ from the planned ones")
        known[member] = json.loads(text)
    for link in frozen["chain"][1:]:
        known[link] = programs.answers_of(programs.checked(frozen["programs"][link], list(known)), known, cases)
    truth = {case: json.loads((development / "truth" / f"{case}.json").read_text(encoding="utf-8"))["sites"]
             for case in cases}
    locations = {arm: {case: known[member].get(case, [])[:lineage.MAX_LOCATIONS] for case in cases}
                 for arm, member in (("champion", champion), ("program", name))}
    covers = {arm: {case: lineage.score(truth[case], locations[arm][case])["localized"] for case in cases}
              for arm in ARMS}
    differing = sorted((case for case in cases if covers["champion"][case] != covers["program"][case]),
                       key=lambda case: hashlib.sha256((ORDER_DOMAIN + case).encode()).hexdigest())
    chosen = differing[:arguments.cases]
    envelope = Envelope(model=arguments.model)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": "genesis-coverage-repair-preregistration-v1", "name": arguments.name, "held_out": False,
        "search": arguments.search, "evolution_digest": frozen["evolution_digest"],
        "arms": {"champion": champion, "program": name},
        "validation_cases": len(cases),
        "localized_on_validation": {arm: sum(covers[arm].values()) for arm in ARMS},
        "localized_note": "these cases were scored for two lineages and RECOMBINE1 before; the counts are given "
                          "to describe the cases, not as evidence about the localizers",
        "differing_cases": len(differing),
        "cases": chosen,
        "covering_arm": {case: "program" if covers["program"][case] else "champion" for case in chosen},
        "locations": {arm: {case: locations[arm][case] for case in chosen} for arm in ARMS},
        "case_rule": (f"validation-role cases where exactly one arm covers every edit site, ordered by "
                      f"sha256({ORDER_DOMAIN!r} + case), first {arguments.cases}"),
        "repair_genome_digest": genome_digest(SEED_GENOME), "envelope": envelope.record(),
        "separate_environment": True, "spending_ceiling_usd": arguments.ceiling,
        "arm_order": "champion first on even-numbered cases, program first on odd-numbered ones",
        "primary_comparison": ("among usable cases, repaired in the arm that covers the fix versus repaired in the "
                               "arm that does not; exact one-sided sign test on the cases only one of the two "
                               "repairs"),
        "secondary": "cases repaired by the program arm minus by the champion arm, over the same cases",
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "claim_boundary": ("a development test of the link between covering the fix and repairing, on cases chosen "
                           "because the two localizers differ; it is not an estimate of the repair rate of either "
                           "and says nothing about held-out cases or recursive self-improvement"),
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    seal(target, body, "preregistration_digest")
    print(json.dumps({"validation": len(cases), "localized": body["localized_on_validation"],
                      "differing": len(differing), "chosen": len(chosen),
                      "program_covers": sum(arm == "program" for arm in body["covering_arm"].values())}))


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


def run(arguments) -> None:
    home = LOCALIZERS / arguments.search
    prereg = sealed(home / f"{arguments.name}_PREREG.json", "preregistration_digest")
    target = home / f"{arguments.name}_RESULT.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists; a trial is run once")
    if prereg["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the preregistration")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    workspace = Path(arguments.workspace).resolve()
    for name in ("runs", "scratch"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    given = prereg["envelope"]
    envelope = Envelope(model=given["model"], validations=given["validations_per_case"],
                        requests=given["model_requests_per_case"], max_tokens=given["max_output_tokens_per_request"],
                        prompt_characters=given["max_prompt_characters"],
                        max_price=tuple(sorted(given["max_price_per_million_tokens"].items())))
    spent, journal = 0.0, workspace / "calls.jsonl"
    if journal.exists():
        for line in journal.read_text(encoding="utf-8").splitlines():
            cost = json.loads(line)["call"].get("cost_usd")
            spent += UNKNOWN_COST_USD if cost is None else cost
    ledger = Ledger(prereg["spending_ceiling_usd"], spent)
    sandbox = Defects4JSandbox(workspace, limits=SandboxLimits(timeout_seconds=2400))

    def one(item: tuple[int, str]) -> dict:
        index, case = item
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
                evidence = {arm: located(collected, workspace / directory, prereg["locations"][arm][case], arm)
                            for arm in ARMS}
            except RepairBenchError as error:
                outcome = {"case": case, "usable": False, "reason": str(error), "arms": {}}
            else:
                order = ARMS if index % 2 == 0 else ARMS[::-1]
                arms = {}
                for arm in order:
                    subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "checkout", "--",
                                    collected["source_directory"]], cwd=workspace / directory, check=True, capture_output=True)
                    calls = Journal(journal, {"case": case, "arm": arm})
                    started = time.monotonic()
                    result = run_arm(sandbox, directory, evidence[arm],
                                     lineage_proposer(SEED_GENOME, envelope, ledger, calls),
                                     envelope.validations, max_rounds=SEED_GENOME["search"]["rounds"])
                    arms[arm] = {"solved": result["solved"], "validated": result["validated"], "rounds": result["rounds"],
                                 "verdicts": result["verdicts"], "plausible_patch": result["plausible_patch"],
                                 "calls": list(calls), "seconds": round(time.monotonic() - started, 1),
                                 "evidence_digest": evidence[arm]["evidence_digest"],
                                 "localization": evidence[arm]["localization"]}
                outcome = {"case": case, "usable": True, "order": list(order), "arms": arms,
                           "covering_arm": prereg["covering_arm"][case]}
        finally:
            shutil.rmtree(workspace / directory, ignore_errors=True)
        saved.write_text(json.dumps(outcome, sort_keys=True), encoding="utf-8")
        print(case, {arm: data["solved"] for arm, data in outcome["arms"].items()} or outcome.get("reason"),
              f"spent {ledger.spent:.3f}", flush=True)
        return outcome

    try:
        with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
            cases = list(pool.map(one, enumerate(prereg["cases"])))
    except (BudgetExhausted, ModelUnavailable) as error:
        raise SystemExit(f"stopped before the end, nothing sealed: {type(error).__name__}: {error}")
    usable = [case for case in cases if case["usable"]]
    table = {"both": 0, "covering_only": 0, "other_only": 0, "neither": 0}
    by_direction = {arm: {"cases": 0, "covering_arm_repairs": 0, "other_arm_repairs": 0} for arm in ARMS}
    for case in usable:
        covering = case["covering_arm"]
        other = ARMS[1 - ARMS.index(covering)]
        first, second = case["arms"][covering]["solved"], case["arms"][other]["solved"]
        table["both" if first and second else "covering_only" if first else "other_only" if second else "neither"] += 1
        row = by_direction[covering]
        row["cases"] += 1
        row["covering_arm_repairs"] += first
        row["other_arm_repairs"] += second
    calls = {arm: [call for case in usable for call in case["arms"][arm]["calls"]] for arm in ARMS}
    body = {
        "schema": "genesis-coverage-repair-result-v1", "name": prereg["name"], "held_out": False,
        "preregistration_digest": prereg["preregistration_digest"], "cases": cases,
        "summary": {
            "cases": len(cases), "usable_cases": len(usable),
            "repaired_with_the_fix_covered": table["both"] + table["covering_only"],
            "repaired_without": table["both"] + table["other_only"],
            "paired": table,
            "one_sided_exact_sign_test_p": round(exact_sign_test(table["other_only"], table["covering_only"]), 6),
            "by_covering_arm": by_direction,
            "solved": {arm: sum(case["arms"][arm]["solved"] for case in usable) for arm in ARMS},
            "fallbacks": {arm: sum(bool(case["arms"][arm]["localization"]["fallback"]) for case in usable)
                          for arm in ARMS},
            "model_requests": {arm: len(calls[arm]) for arm in ARMS},
            "cost_usd": {arm: round(sum(call.get("cost_usd") or 0 for call in calls[arm]), 6) for arm in ARMS},
            "calls_with_unknown_cost": {arm: sum(call.get("cost_usd") is None for call in calls[arm]) for arm in ARMS},
        },
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "fixed_revision_consulted": False,
    }
    seal(target, body, "result_digest")
    print(json.dumps(body["summary"], indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("preregister", preregister), ("run", run)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--search", default="PROGRAMS1")
        command.add_argument("--name", required=True)
        if name == "preregister":
            command.add_argument("--development", required=True, help="workspace of the development cases")
            command.add_argument("--cases", type=int, default=60)
            command.add_argument("--ceiling", type=float, default=2.0)
            command.add_argument("--model", default="anthropic/claude-haiku-5.5")
        else:
            command.add_argument("--workspace", required=True)
            command.add_argument("--parallel", type=int, default=3)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
