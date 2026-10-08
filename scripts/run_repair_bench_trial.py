"""Run one repair-bench trial: every arm on every case, at one validation budget.

    # 1. decide and record what will be run (commit the file before step 2)
    python scripts/run_repair_bench_trial.py preregister --name T1 --held-out 20 --budget 10 \
        --arms strategist model --model claude-sonnet-5-5
    # development rehearsal on named development cases instead of held-out ones
    python scripts/run_repair_bench_trial.py preregister --name DEV1 --cases Math-2 Cli-5 --budget 10 ...

    # 2. run it
    python scripts/run_repair_bench_trial.py run --name T1 --workspace /srv/genesis/bench

A held-out case is consumed the moment a preregistration names it, whether or not the run
succeeds. The fixed revision is never checked out by this script. A case during which a model call
failed outright is not recorded; the run stops unsealed and the same command resumes it.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis.defects4j_sandbox import Defects4JSandbox, SandboxLimits  # noqa: E402
from genesis.repair_bench import RepairBenchError, collect_evidence, next_held_out, run_arm  # noqa: E402
from genesis.repair_proposers import model_proposer, strategist_proposer  # noqa: E402
from genesis.openrouter_repair import DEFAULT_MODEL, MAX_PRICE, openrouter_proposer  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

BENCH = ROOT / "experiment/bench"
SPLIT = BENCH / "REPAIR_BENCH_SPLIT_V1.json"
PREREG_SCHEMA = "genesis-repair-bench-preregistration-v1"
RESULT_SCHEMA = "genesis-repair-bench-result-v1"
ARMS = ("strategist", "model", "model_explore")


OPENROUTER_MACHINERY = ("genesis/openrouter_repair.py", "genesis/repair_proposers.py",
    "genesis/repair_bench.py", "genesis/defects4j_sandbox.py", "scripts/run_repair_bench_trial.py")


def _machinery() -> dict:
    return {name: digest_of((ROOT / name).read_bytes().hex()) for name in OPENROUTER_MACHINERY}


class CallJournal(list):
    """Keep each call even if a case aborts before its result is appended."""

    def __init__(self, path: Path, case: str, arm: str, preregistration_digest: str):
        super().__init__()
        self.path, self.case, self.arm, self.binding = path, case, arm, preregistration_digest

    def append(self, record):
        body = {"case": self.case, "arm": self.arm, "preregistration_digest": self.binding, "call": record}
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps({**body, "event_digest": digest_of(body)}, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        super().append(record)


def _sealed(path: Path, key: str) -> dict:
    record = json.loads(path.read_text(encoding="utf-8"))
    body = {name: value for name, value in record.items() if name != key}
    if record.get(key) != digest_of(body):
        raise SystemExit(f"{path.name}: {key} does not match its content")
    return record


def _consumed() -> list[str]:
    """Held-out cases named by any preregistration on disk."""
    spent: list[str] = []
    for path in sorted(BENCH.glob("TRIAL_*_PREREG.json")):
        record = _sealed(path, "preregistration_digest")
        if record["held_out"]:
            spent.extend(record["cases"])
    return spent


def preregister(arguments: argparse.Namespace) -> int:
    target = BENCH / f"TRIAL_{arguments.name}_PREREG.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists")
    split = _sealed(SPLIT, "split_digest")
    if arguments.held_out:
        cases = next_held_out(split, _consumed(), arguments.held_out)
    else:
        cases = list(arguments.cases or [])
        outside = [case for case in cases if case not in split["development"]]
        if outside or not cases:
            raise SystemExit(f"a rehearsal takes development cases only; not development: {outside}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    body = {
        "schema": PREREG_SCHEMA,
        "name": arguments.name,
        "held_out": bool(arguments.held_out),
        "split_digest": split["split_digest"],
        "cases": cases,
        "arms": list(arguments.arms),
        "validation_budget_per_arm": arguments.budget,
        "candidates_per_model_call": arguments.per_call,
        "max_rounds_per_arm": 4,
        "stop_at_first_plausible": True,
        "model": (arguments.model or (DEFAULT_MODEL if arguments.provider == "openrouter" else "claude-sonnet-5-5"))
            if any(arm.startswith("model") for arm in arguments.arms) else None,
        "acceptance": "a case is solved by an arm when one validated candidate passes the full developer test suite",
        "plausible_is_not_correct": True,
        "benchmark_may_be_in_model_training_data": True,
        "machinery_commit": head,
    }
    if arguments.provider == "openrouter":
        body.update({"provider": "openrouter", "machinery_digests": _machinery(),
                     "max_requests_per_round": 4, "max_output_tokens_per_request": arguments.output_tokens,
                     "provider_max_price_per_million_tokens": {
                         "prompt": arguments.input_price, "completion": arguments.output_price, "request": 0.0},
                     "max_reserved_cost_usd_per_request": arguments.call_cost,
                     "max_reserved_cost_usd_per_round": arguments.round_cost,
                     "reasoning_effort": arguments.reasoning_effort,
                     "model_fallback": False, "provider_fallback": True, "call_journal": True})
    target.write_text(json.dumps({**body, "preregistration_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n")
    print(f"{target.relative_to(ROOT)}: {len(cases)} cases, arms {body['arms']}, budget {arguments.budget}")
    return 0


def _run_case(workspace: Path, case: str, prereg: dict) -> dict:
    project, bug = case.rsplit("-", 1)
    directory = f"{case}-b"
    sandbox = Defects4JSandbox(workspace, limits=SandboxLimits(timeout_seconds=2400))
    record: dict = {"case": case}
    try:
        if not (workspace / directory).is_dir() and not sandbox.checkout(project, int(bug), "b", directory).ok:
            raise RepairBenchError("checkout failed")
        evidence = collect_evidence(sandbox, directory)
    except RepairBenchError as error:
        return {**record, "usable": False, "reason": str(error), "arms": {}}
    calls: dict[str, list[dict]] = {}
    proposers = {
        "strategist": strategist_proposer(prereg["validation_budget_per_arm"]),
    }
    if prereg["model"]:
        per_call = prereg["candidates_per_model_call"]
        provider = prereg.get("provider", "claude")
        make_proposer = openrouter_proposer if provider == "openrouter" else model_proposer
        options = {}
        if provider == "openrouter":
            options = {
                "max_requests": prereg["max_requests_per_round"],
                "max_tokens": prereg["max_output_tokens_per_request"],
                "max_price": prereg["provider_max_price_per_million_tokens"],
                "max_call_usd": prereg["max_reserved_cost_usd_per_request"],
                "max_round_usd": prereg["max_reserved_cost_usd_per_round"],
                "reasoning_effort": prereg.get("reasoning_effort"),
            }
            for arm in ("model", "model_explore"):
                calls[arm] = CallJournal(workspace / f"{prereg['name']}.{case}.{arm}.calls.jsonl",
                                        case, arm, prereg["preregistration_digest"])
        proposers["model"] = make_proposer(prereg["model"], per_call, calls.setdefault("model", []), **options)
        proposers["model_explore"] = make_proposer(
            prereg["model"], per_call, calls.setdefault("model_explore", []), explore=True, **options)
    arms = {
        arm: run_arm(sandbox, directory, evidence, proposers[arm], prereg["validation_budget_per_arm"])
        for arm in prereg["arms"]
    }
    return {
        **record, "usable": True,
        "evidence_digest": evidence["evidence_digest"],
        "failing_tests": len(evidence["failing_tests"]),
        "suspects_from_stack_trace": evidence["suspects_from_stack_trace"],
        "model_calls": calls,
        "arms": arms,
    }


def run(arguments: argparse.Namespace) -> int:
    prereg = _sealed(BENCH / f"TRIAL_{arguments.name}_PREREG.json", "preregistration_digest")
    target = BENCH / f"TRIAL_{arguments.name}_RESULT.json"
    if target.exists():
        raise SystemExit(f"{target.name} already exists; a trial is run once")
    if prereg.get("provider") == "openrouter":
        if prereg.get("machinery_digests") != _machinery():
            raise SystemExit("OpenRouter machinery differs from the preregistered source")
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise SystemExit("OPENROUTER_API_KEY is required before starting any case")
    arguments.workspace.mkdir(parents=True, exist_ok=True)
    probe = Defects4JSandbox(arguments.workspace).probe()
    if not probe["isolated"]:
        raise SystemExit("the Defects4J boundary does not hold; refusing to run")
    partial = arguments.workspace / f"{arguments.name}.partial.jsonl"
    done = {}
    if partial.exists():
        done = {json.loads(line)["case"]: json.loads(line) for line in partial.read_text().splitlines() if line.strip()}
    access_failed = Event()

    def one(case: str) -> dict:
        if case in done:
            return done[case]
        if access_failed.is_set():
            return {"case": case, "aborted": True, "not_started": True}
        outcome = _run_case(arguments.workspace, case, prereg)
        if any(call.get("call_failed") for calls in outcome.get("model_calls", {}).values() for call in calls):
            if prereg.get("provider") == "openrouter":
                body = {"preregistration_digest": prereg["preregistration_digest"], "outcome": outcome}
                with (arguments.workspace / f"{arguments.name}.{case}.aborted.jsonl").open('a') as handle:
                    handle.write(json.dumps({**body, "event_digest": digest_of(body)}, sort_keys=True) + '\n')
                    handle.flush()
                    os.fsync(handle.fileno())
                access_failed.set()
            # The model was not reached: this says nothing about the case. Keep nothing, so that
            # resuming the trial runs the case again from scratch.
            print(case, "ABORTED: a model call failed", flush=True)
            return {"case": case, "aborted": True}
        with partial.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(outcome, sort_keys=True) + "\n")
        solved = {arm: data["solved"] for arm, data in outcome["arms"].items()}
        print(case, "usable" if outcome["usable"] else f"UNUSABLE ({outcome.get('reason')})", solved, flush=True)
        return outcome

    with ThreadPoolExecutor(max_workers=arguments.parallel) as pool:
        cases = list(pool.map(one, prereg["cases"]))
    aborted = [case["case"] for case in cases if case.get("aborted")]
    if aborted:
        print(f"trial not sealed: {len(aborted)} case(s) aborted on a failed model call: {aborted}")
        print("run the same command again to resume; finished cases are kept")
        return 2
    usable = [case for case in cases if case["usable"]]
    body = {
        "schema": RESULT_SCHEMA,
        "name": prereg["name"],
        "held_out": prereg["held_out"],
        "preregistration_digest": prereg["preregistration_digest"],
        "sandbox_probe_digest": probe["probe_digest"],
        "cases": cases,
        "summary": {
            "cases": len(cases),
            "usable_cases": len(usable),
            "solved_per_arm": {arm: sum(case["arms"][arm]["solved"] for case in usable) for arm in prereg["arms"]},
            "cases_with_a_failed_model_call_per_arm": {
                arm: sum(any(call.get("call_failed") for call in case["model_calls"].get(arm, [])) for case in usable)
                for arm in prereg["arms"] if arm.startswith("model")
            },
            "model_cost_usd_per_arm": {
                arm: round(sum(call.get("cost_usd") or 0 for case in usable for call in case["model_calls"].get(arm, [])), 4)
                for arm in prereg["arms"] if arm.startswith("model")
            },
        },
        "plausible_is_not_correct": True,
        "benchmark_may_be_in_model_training_data": True,
        "fixed_revision_consulted": False,
    }
    if prereg.get("provider") == "openrouter":
        body["provider"] = "openrouter"
        body["model"] = prereg["model"]
        for arm in (name for name in prereg["arms"] if name.startswith("model")):
            arm_calls = [call for case in usable for call in case["model_calls"].get(arm, [])]
            if any(call.get("cost_usd") is None for call in arm_calls):
                body["summary"]["model_cost_usd_per_arm"][arm] = None
        body["cost_scope"] = "sealed cases only; all attempted calls retained separately in workspace call journals"
    target.write_text(json.dumps({**body, "result_digest": digest_of(body)}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(body["summary"], indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    pre = commands.add_parser("preregister")
    pre.add_argument("--name", required=True)
    group = pre.add_mutually_exclusive_group(required=True)
    group.add_argument("--held-out", type=int, default=0)
    group.add_argument("--cases", nargs="+")
    pre.add_argument("--budget", type=int, default=10)
    pre.add_argument("--per-call", type=int, default=4, help="candidates asked of the model per round")
    pre.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    pre.add_argument("--model", default=None)
    pre.add_argument("--provider", choices=("claude", "openrouter"), default="openrouter")
    pre.add_argument("--input-price", type=float, default=MAX_PRICE['prompt'], help="maximum USD/million input tokens")
    pre.add_argument("--output-price", type=float, default=MAX_PRICE['completion'], help="maximum USD/million output tokens")
    pre.add_argument("--call-cost", type=float, default=0.01, help="maximum conservative reservation USD/request")
    pre.add_argument("--round-cost", type=float, default=0.03, help="maximum conservative reservation USD/proposal round")
    pre.add_argument("--output-tokens", type=int, default=2048)
    pre.add_argument("--reasoning-effort", choices=("none", "minimal", "low", "medium", "high"), default=None)
    pre.set_defaults(handler=preregister)
    runner = commands.add_parser("run")
    runner.add_argument("--name", required=True)
    runner.add_argument("--workspace", type=Path, required=True)
    runner.add_argument("--parallel", type=int, default=2)
    runner.set_defaults(handler=run)
    arguments = parser.parse_args()
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
