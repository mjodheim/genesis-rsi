"""Does a better localizer make the repair agent repair more? A paired development trial.

    preregister   name the cases and both arms before anything runs
    run           the same repair agent on each case twice: once with the evidence collected from
                  the stack trace, once with the locations returned by the lineage's final module

The cases are development cases in the localizer lineage's *validation* role: no localizer was
ever shown or selected on them. Both arms use the same seed repair configuration, the same model
and the same envelope. No held-out case of the repair bench is involved. OPENROUTER_API_KEY is
read from the environment by ``run``.
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
from genesis import localizer_lineage  # noqa: E402
from genesis.localized_evidence import relocalize  # noqa: E402
from genesis.repair_bench import RepairBenchError, collect_evidence, run_arm  # noqa: E402
from genesis.repair_lineage import (  # noqa: E402
    SEED_GENOME, BudgetExhausted, Envelope, Ledger, ModelUnavailable, exact_sign_test, genome_digest, lineage_proposer,
)
from genesis.trust_root import digest_of  # noqa: E402

LOCALIZER = ROOT / "experiment/localizer"
ORDER_DOMAIN = "genesis-localized-repair-v1|"
MACHINERY = ("genesis/localized_evidence.py", "genesis/localizer_lineage.py", "genesis/repair_lineage.py",
             "genesis/repair_bench.py", "genesis/openrouter_repair.py", "genesis/defects4j_sandbox.py",
             "scripts/run_localized_repair_trial.py")
UNKNOWN_COST_USD = 0.02
ARMS = ("stack_trace", "localizer")


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
    home = LOCALIZER / arguments.lineage
    plan = sealed(home / "PLAN.json", "plan_digest")
    frozen = sealed(home / "LINEAGE.json", "lineage_digest")
    target = home / f"{arguments.name}_PREREG.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    final = frozen["chain"][-1]
    ordered = sorted(plan["roles"]["validation"],
                     key=lambda case: hashlib.sha256((ORDER_DOMAIN + case).encode()).hexdigest())
    envelope = Envelope(model=arguments.model)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": "genesis-localized-repair-preregistration-v1", "name": arguments.name, "held_out": False,
        "lineage": arguments.lineage, "lineage_digest": frozen["lineage_digest"],
        "cases": ordered[:arguments.cases],
        "case_rule": (f"validation-role cases of the localizer lineage, ordered by sha256({ORDER_DOMAIN!r} + case), "
                      f"first {arguments.cases}"),
        "arms": {"stack_trace": "evidence as collected by the repair bench",
                 "localizer": {"module": final, "sha256": frozen["module_sha256"][f"{final}.py.txt"]}},
        "repair_genome_digest": genome_digest(SEED_GENOME), "envelope": envelope.record(),
        "python_image": plan["python_image"], "separate_environment": True,
        "spending_ceiling_usd": arguments.ceiling,
        "arm_order": "stack_trace first on even-numbered cases, localizer first on odd-numbered ones",
        "primary_comparison": ("cases repaired by the localizer arm versus by the stack_trace arm among usable "
                               "cases; exact one-sided sign test on the cases only one arm repairs"),
        "plausible_is_not_correct": True, "benchmark_may_be_in_model_training_data": True,
        "claim_boundary": ("a development comparison of one component swap under a fixed external model; it "
                           "says nothing about held-out cases or about recursive self-improvement"),
        "machinery_commit": head, "machinery_digests": machinery(),
    }
    if frozen["chain"] == ["g0"]:
        raise SystemExit("no successor was promoted: there is nothing to compare")
    seal(target, body, "preregistration_digest")
    print(f"{target.name}: {len(body['cases'])} cases, module {final}")


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


def covered(evidence: dict, truth_directory: Path, case: str) -> bool | None:
    """Whether the evidence's locations cover the developer fix. Read only after both arms ran."""
    path = truth_directory / f"{case}.json"
    if not path.is_file():
        return None
    sites = json.loads(path.read_text(encoding="utf-8"))["sites"]
    return localizer_lineage.score(sites, localizer_lineage.clean_locations(evidence["suspect_locations"]))["localized"]


def run(arguments) -> None:
    home = LOCALIZER / arguments.lineage
    prereg = sealed(home / f"{arguments.name}_PREREG.json", "preregistration_digest")
    target = home / f"{arguments.name}_RESULT.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists; a trial is run once")
    if prereg["machinery_digests"] != machinery():
        raise SystemExit("machinery differs from the preregistration")
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is required")
    module = (home / "modules" / f"{prereg['arms']['localizer']['module']}.py.txt").read_text(encoding="utf-8")
    if localizer_lineage.source_digest(module) != prereg["arms"]["localizer"]["sha256"]:
        raise SystemExit("the localizer module differs from the preregistration")
    workspace = Path(arguments.workspace).resolve()
    for name in ("evidence", "runs", "scratch"):
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
                evidence = {"stack_trace": collected,
                            "localizer": relocalize(collected, workspace / directory, module,
                                                    image=prereg["python_image"], scratch=workspace / "scratch")}
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
                                 "suspect_locations": evidence[arm]["suspect_locations"],
                                 "localization": evidence[arm].get("localization")}
                outcome = {"case": case, "usable": True, "order": list(order), "arms": arms,
                           "fix_covered": {arm: covered(evidence[arm], Path(arguments.truth), case) for arm in ARMS}}
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
    table = {"both": 0, "stack_trace_only": 0, "localizer_only": 0, "neither": 0}
    for case in usable:
        first, second = case["arms"]["stack_trace"]["solved"], case["arms"]["localizer"]["solved"]
        table["both" if first and second else "stack_trace_only" if first else
              "localizer_only" if second else "neither"] += 1
    calls = {arm: [call for case in usable for call in case["arms"][arm]["calls"]] for arm in ARMS}
    body = {
        "schema": "genesis-localized-repair-result-v1", "name": prereg["name"], "held_out": False,
        "preregistration_digest": prereg["preregistration_digest"], "cases": cases,
        "summary": {
            "cases": len(cases), "usable_cases": len(usable),
            "solved": {arm: sum(case["arms"][arm]["solved"] for case in usable) for arm in ARMS},
            "paired": table,
            "one_sided_exact_sign_test_p": round(exact_sign_test(table["stack_trace_only"], table["localizer_only"]), 6),
            "fix_covered_by_evidence": {arm: sum(bool(case["fix_covered"][arm]) for case in usable) for arm in ARMS},
            "solved_when_fix_covered": {arm: sum(case["arms"][arm]["solved"] for case in usable if case["fix_covered"][arm])
                                        for arm in ARMS},
            "localizer_fallbacks": sum(bool(case["arms"]["localizer"]["localization"]["fallback"]) for case in usable),
            "validated": {arm: sum(case["arms"][arm]["validated"] for case in usable) for arm in ARMS},
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
        command.add_argument("--lineage", required=True)
        command.add_argument("--name", required=True)
        if name == "preregister":
            command.add_argument("--cases", type=int, default=40)
            command.add_argument("--ceiling", type=float, default=2.0)
            command.add_argument("--model", default="anthropic/claude-haiku-5.5")
        else:
            command.add_argument("--workspace", required=True)
            command.add_argument("--truth", required=True)
            command.add_argument("--parallel", type=int, default=3)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
