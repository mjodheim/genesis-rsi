"""Fetch libraries, record how their tests call them, and chain verified improvements of their functions.

    fetch     download the pinned source distributions of the corpus and unpack them
    record    run each library's tests once and keep the distinct calls its functions received
    prepare   turn recorded functions into cases: usable calls, what the original does with them,
              what they cost, which tests cover them
    plan      freeze the cases of a trial, its arms and its protocol
    run       chain rewrites of every case in every arm
    report    seal the records of a finished trial and compare its arms

Library sources, recorded calls and rewritten functions stay in the workspace, outside the
repository. OPENROUTER_API_KEY is read from the environment by ``run`` only.
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
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import program_improvement as improvement  # noqa: E402
from genesis.repair_lineage import BudgetExhausted, Envelope, Ledger, ModelUnavailable  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/improvement"
CORPUS = HOME / "CORPUS_V1.json"
MACHINERY = ("genesis/program_improvement.py", "genesis/improvement_harness.py", "genesis/repair_lineage.py",
             "scripts/run_program_improvement.py", "deploy/program-improvement/Dockerfile",
             "deploy/program-improvement/marker.c")
MAX_FUNCTION_CHARACTERS = 6000
UNKNOWN_COST_USD = 0.03


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


def corpus() -> dict:
    return sealed(CORPUS, "corpus_digest")


def image_id() -> str:
    done = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", improvement.IMAGE],
                          capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"image {improvement.IMAGE} is missing: docker build -t {improvement.IMAGE} deploy/program-improvement")
    return done.stdout.strip()


# -- fetch --------------------------------------------------------------------------------------


def fetch(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    (workspace / "sdists").mkdir(parents=True, exist_ok=True)
    (workspace / "packages").mkdir(exist_ok=True)
    for package in corpus()["packages"]:
        archive = workspace / "sdists" / package["sdist"]
        if not archive.is_file():
            with urllib.request.urlopen(f"https://pypi.org/pypi/{package['name']}/{package['version']}/json", timeout=60) as reply:
                listing = json.load(reply)
            (entry,) = [item for item in listing["urls"] if item["filename"] == package["sdist"]]
            with urllib.request.urlopen(entry["url"], timeout=180) as reply:
                archive.write_bytes(reply.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest() != package["sdist_sha256"]:
            raise SystemExit(f"{package['sdist']}: digest differs from the corpus")
        target = workspace / "packages" / package["name"]
        if not target.is_dir():
            staging = workspace / "packages" / (package["name"] + ".unpacking")
            shutil.rmtree(staging, ignore_errors=True)
            with tarfile.open(archive) as handle:
                handle.extractall(staging, filter="data")
            (inner,) = list(staging.iterdir())
            inner.rename(target)
            staging.rmdir()
        print(json.dumps({"package": package["name"], "version": package["version"], "ready": True}), flush=True)


# -- record -------------------------------------------------------------------------------------


def record_package(package: dict, workspace: Path) -> dict:
    target = workspace / "recorded" / package["name"]
    if (target / "DONE").is_file():
        return {"package": package["name"], "functions": len(list(target.glob("*.json"))), "cached": True}
    shutil.rmtree(target, ignore_errors=True)
    root = package["import_root"]
    spec = {"path": ["/harness", "/tree/" + root if root else "/tree", "/tree"], "cwd": "/tree",
            "arguments": package["tests"]}
    result = improvement.run_harness("pytest", spec, tree=workspace / "packages" / package["name"],
                                     scratch=workspace / "scratch", timeout=2400, keep=target,
                                     environment={"GENESIS_RECORD_PACKAGE": package["package_import"]})
    target.mkdir(parents=True, exist_ok=True)
    tests = result.get("tests") or []
    (target / "DONE").write_text(str(len(tests)), encoding="utf-8")
    return {"package": package["name"], "functions": len(list(target.glob("*.json"))),
            "tests_passed": len(improvement.passed_tests(tests)), "test_reports": len(tests)}


def record(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    (workspace / "scratch").mkdir(exist_ok=True)
    packages = [package for package in corpus()["packages"] if not arguments.package or package["name"] in arguments.package]
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        for row in pool.map(lambda package: record_package(package, workspace), packages):
            print(json.dumps(row), flush=True)


# -- prepare ------------------------------------------------------------------------------------


def case_directory(workspace: Path, case: str) -> Path:
    return workspace / "cases" / case.replace(":", "--")


def prepare_case(package: dict, path: Path, workspace: Path) -> dict:
    """Build one case from one recorded function, or say why it is not one."""
    recorded = json.loads(path.read_text(encoding="utf-8"))
    case = f"{package['name']}:{recorded['module']}.{recorded['name']}"
    directory = case_directory(workspace, case)
    marker = workspace / "cases" / "_rejected" / (directory.name + ".json")
    if (directory / "case.json").is_file():
        return {"case": case, "eligible": True, "cached": True}
    if marker.is_file():
        return {"case": case, "eligible": False, "cached": True}

    def reject(reason: str) -> dict:
        shutil.rmtree(directory, ignore_errors=True)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({"case": case, "reason": reason}), encoding="utf-8")
        return {"case": case, "eligible": False, "reason": reason}

    tree = workspace / "packages" / package["name"]
    source = (tree / recorded["file"]).read_text(encoding="utf-8")
    try:
        span = improvement.function_span(source, recorded["name"])
    except (improvement.ImprovementError, SyntaxError):
        return reject("not a single top-level function")
    if list(span) != [recorded["first"], recorded["last"]]:
        return reject("span differs from the recording")
    if len(improvement.function_text(source, recorded["name"])) > MAX_FUNCTION_CHARACTERS:
        return reject("function too long")
    if len(recorded["calls"]) < improvement.MIN_USABLE_CALLS:
        return reject("too few recorded calls")
    root = package["import_root"]
    spec = {"module": recorded["module"], "name": recorded["name"], "seconds": improvement.CALL_SECONDS,
            "path": ["/harness", "/tree/" + root if root else "/tree", "/tree"]}
    scratch = workspace / "scratch"
    runs = [improvement.run_harness("outcomes", spec, tree=tree, scratch=scratch, calls=recorded["calls"]).get("outcomes")
            for _ in (1, 2)]
    if not all(isinstance(run, list) and len(run) == len(recorded["calls"]) for run in runs):
        return reject("replay of the original did not finish")
    usable = [index for index, (one, two) in enumerate(zip(*runs))
              if one["kind"] in ("returned", "raised") and one["digest"] == two["digest"]]
    if len(usable) < improvement.MIN_USABLE_CALLS:
        return reject("too few calls replay identically")
    outcomes = [runs[0][index] for index in usable]
    if sum(row["kind"] == "returned" for row in outcomes) < improvement.MIN_RETURNED_SHARE * len(outcomes):
        return reject("most calls raise")
    if len({(row["kind"], row["preview"]) for row in outcomes}) < 3:
        return reject("the calls all give the same thing")
    calls = [recorded["calls"][index] for index in usable]
    shown, hidden, measured = improvement.split_calls([improvement.text_digest(call) for call in calls])
    if len(hidden) < improvement.MIN_HIDDEN_CALLS:
        return reject("too few hidden calls")
    if sum(outcomes[index]["seconds"] for index in measured) > improvement.MAX_REPLAY_SECONDS:
        return reject("replay too slow")
    data = {"schema": "genesis-improvement-case-v1", "case": case, "package": package["name"],
            "version": package["version"], "package_import": package["package_import"],
            "import_root": root, "module": recorded["module"], "name": recorded["name"], "file": recorded["file"],
            "file_sha256": improvement.text_digest(source), "span": list(span), "outcomes": outcomes,
            "shown": shown, "hidden": hidden, "measured": measured, "tests": [], "passing_tests": [],
            "instructions": 0, "role": improvement.role_of(case)}
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "calls.json").write_text(json.dumps(calls), encoding="utf-8")
    (directory / "case.json").write_text(json.dumps(data), encoding="utf-8")
    loaded = improvement.Case(directory, workspace / "packages")
    counts = improvement.measure(loaded, None, scratch)
    if not counts:
        return reject("measurement did not finish")
    if min(counts) < improvement.MIN_INSTRUCTIONS:
        return reject("too cheap to measure")
    if (max(counts) - min(counts)) / max(counts) > improvement.MAX_REPEAT_SPREAD:
        return reject("instruction count not repeatable")
    files = [name for name in recorded["tests"] if (tree / name).is_file()][:3]
    passing: list[str] = []
    if files:
        tests = improvement.run_harness("pytest", {**loaded.spec(), "cwd": "/tree", "arguments": files},
                                        tree=tree, scratch=scratch, timeout=900)
        passing = sorted(improvement.passed_tests(tests.get("tests")))[:4000]
    data.update(instructions=max(counts), instruction_runs=counts, tests=files if passing else [],
                passing_tests=passing,
                seconds=round(sum(outcomes[index]["seconds"] for index in measured), 6))
    (directory / "case.json").write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    return {"case": case, "eligible": True, "calls": len(calls), "instructions": max(counts),
            "passing_tests": len(passing), "role": data["role"]}


def prepare(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    (workspace / "scratch").mkdir(exist_ok=True)

    def one_package(package: dict) -> list[dict]:
        paths = sorted((workspace / "recorded" / package["name"]).glob("*.json"),
                       key=lambda path: improvement.order_key(f"{package['name']}:{path.stem}"))
        rows, eligible = [], 0
        for path in paths:
            if eligible >= arguments.per_package:
                break
            try:
                row = prepare_case(package, path, workspace)
            except (OSError, ValueError, KeyError) as error:
                row = {"case": f"{package['name']}:{path.stem}", "eligible": False, "reason": type(error).__name__}
            eligible += row["eligible"]
            rows.append(row)
            print(json.dumps(row), flush=True)
        return rows

    packages = [package for package in corpus()["packages"] if not arguments.package or package["name"] in arguments.package]
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        rows = [row for group in pool.map(one_package, packages) for row in group]
    print(json.dumps({"tried": len(rows), "eligible": sum(row["eligible"] for row in rows)}))


# -- plan ---------------------------------------------------------------------------------------


def available_cases(workspace: Path, role: str) -> list[str]:
    names = []
    for path in sorted((workspace / "cases").glob("*/case.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["role"] == role and data["instructions"]:
            names.append(data["case"])
    return sorted(names, key=improvement.order_key)


def case_digest(workspace: Path, case: str) -> str:
    directory = case_directory(workspace, case)
    return digest_of([(directory / name).read_bytes().hex() for name in ("case.json", "calls.json")])


def plan(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    home = HOME / arguments.name
    if (home / "PLAN.json").exists():
        raise SystemExit(f"{arguments.name} already has a plan")
    cases = available_cases(workspace, arguments.role)
    cases = cases[:arguments.cases] if arguments.cases else cases
    if not cases:
        raise SystemExit("no prepared case has this role")
    body = {
        "schema": "genesis-improvement-plan-v1", "trial": arguments.name, "role": arguments.role,
        "cases": cases, "case_digests": {case: case_digest(workspace, case) for case in cases},
        "arms": arguments.arms.split(","),
        "protocol": {
            "model": arguments.model, "max_output_tokens": arguments.max_tokens, "max_steps": arguments.steps,
            "attempts_per_step": arguments.attempts, "required_gain": improvement.REQUIRED_GAIN,
            "memory_batch": arguments.batch, "warm_up_cases": arguments.warm_up,
            "shown_calls": improvement.SHOWN_CALLS, "measured_calls": improvement.MEASURED_CALLS,
            "ceiling_usd": arguments.ceiling, "judge": arguments.judge,
            **({"strict": STRICT_RULE} if arguments.judge == "strict" else {}),
            "acceptance": "identical outcome digest on every recorded call, no previously passing covering test "
                          "lost, and at most (1 - required_gain) of the current instruction count on the hidden "
                          "measured calls, taking the larger of two counts",
            "comparison": "per case, between arms, on the cases after the warm-up: accepted at least one rewrite "
                          "(one-sided exact sign test, accumulating over isolated) and final instruction ratio",
        },
        "corpus_digest": corpus()["corpus_digest"], "image": improvement.IMAGE, "image_id": image_id(),
        "machinery": machinery(),
    }
    record = seal(home / "PLAN.json", body, "plan_digest")
    print(json.dumps({"trial": arguments.name, "cases": len(cases), "arms": body["arms"], "plan_digest": record["plan_digest"]}))


STRICT_RULE = ("in addition: no private attribute or private outside import the original function does not use; "
               "on generated variants of the recorded calls on which the original gives the same outcome twice, the "
               "same outcome digest when it returns and the same exception type when it raises; without "
               f"instrumentation, at most {improvement.MAX_NATIVE_RATIO} of the processor time of the version it "
               f"replaces (best of two alternating runs) and at most {improvement.MAX_PEAK_RATIO} of its peak "
               f"allocation plus {improvement.PEAK_ALLOWANCE} bytes")


def checked_plan(name: str, workspace: Path) -> dict:
    record = sealed(HOME / name / "PLAN.json", "plan_digest")
    if record["machinery"] != machinery():
        raise SystemExit("the machinery changed since the plan was frozen")
    if record["image_id"] != image_id():
        raise SystemExit("the measurement image changed since the plan was frozen")
    for case, digest in record["case_digests"].items():
        if case_digest(workspace, case) != digest:
            raise SystemExit(f"{case}: the prepared case changed since the plan was frozen")
    return record


# -- run ----------------------------------------------------------------------------------------


def run(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    protocol = record["protocol"]
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("OPENROUTER_API_KEY is missing")
    scratch = workspace / "scratch"
    scratch.mkdir(exist_ok=True)
    runs = workspace / "runs" / arguments.name
    envelope = Envelope(model=protocol["model"], max_tokens=protocol["max_output_tokens"])

    def stored(arm: str, case: str) -> Path:
        return runs / arm / case.replace(":", "--") / "record.json"

    def finished(arm: str) -> list[dict]:
        return [json.loads(stored(arm, case).read_text(encoding="utf-8")) for case in record["cases"]
                if stored(arm, case).is_file()]

    spent = sum(item["cost_usd"] + UNKNOWN_COST_USD * item["unknown_cost_requests"]
                for arm in record["arms"] for item in finished(arm))
    ledger = Ledger(protocol["ceiling_usd"], spent)

    def one(arm: str, case: str, memory: str | None) -> dict | None:
        path = stored(arm, case)
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        path.parent.mkdir(parents=True, exist_ok=True)
        loaded = improvement.Case(case_directory(workspace, case), workspace / "packages")
        try:
            result = improvement.improve(
                loaded, envelope, ledger, scratch, memory=memory, max_steps=protocol["max_steps"],
                attempts_per_step=protocol["attempts_per_step"], strict=protocol.get("judge") == "strict",
                save=lambda name, text: (path.parent / name).write_text(text, encoding="utf-8"))
        except (BudgetExhausted, ModelUnavailable) as error:
            print(json.dumps({"arm": arm, "case": case, "stopped": type(error).__name__}), flush=True)
            return None
        result["memory_digest"] = improvement.text_digest(memory) if memory is not None else None
        path.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps({"arm": arm, "case": case, "chain": result["chain_length"], "ratio": result["final_ratio"],
                          "requests": result["requests"], "spent_usd": round(ledger.spent, 4)}), flush=True)
        return result

    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        for arm in record["arms"]:
            if arm == "isolated":
                list(pool.map(lambda case: one(arm, case, None), record["cases"]))
                continue
            done: list[dict] = []
            for start in range(0, len(record["cases"]), protocol["memory_batch"]):
                memory = improvement.memory_of(done)
                batch = record["cases"][start:start + protocol["memory_batch"]]
                results = list(pool.map(lambda case: one(arm, case, memory), batch))
                if any(result is None for result in results):
                    raise SystemExit("stopped before the arm was complete; run again to resume")
                done += results
    missing = [(arm, case) for arm in record["arms"] for case in record["cases"] if not stored(arm, case).is_file()]
    print(json.dumps({"complete": not missing, "missing": len(missing), "spent_usd": round(ledger.spent, 4)}))


# -- report -------------------------------------------------------------------------------------


def report(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    runs = workspace / "runs" / arguments.name
    arms = {}
    for arm in record["arms"]:
        arms[arm] = []
        for case in record["cases"]:
            path = runs / arm / case.replace(":", "--") / "record.json"
            if not path.is_file():
                raise SystemExit(f"{arm} {case}: not run yet")
            item = json.loads(path.read_text(encoding="utf-8"))
            body = {key: value for key, value in item.items() if key not in ("record_digest", "memory_digest")}
            if digest_of(body) != item["record_digest"]:
                raise SystemExit(f"{arm} {case}: record does not match its digest")
            arms[arm].append(item)
    body = {"schema": "genesis-improvement-result-v1", "trial": arguments.name, "plan_digest": record["plan_digest"],
            "summary": improvement.summarize(arms, record["protocol"]["warm_up_cases"]), "records": arms}
    sealed_result = seal(HOME / arguments.name / "RESULT.json", body, "result_digest")
    print(json.dumps(sealed_result["summary"], indent=1))


def rejudge(arguments) -> None:
    """Re-examine, without any model, the final accepted rewrite of each improved case of a sealed trial.

    Only the checks that need no champion are applied: private access, then generated variants
    against the original. Nothing in the sealed result changes; the outcome is a separate file.
    """
    workspace = Path(arguments.workspace).resolve()
    result = sealed(HOME / arguments.name / "RESULT.json", "result_digest")
    scratch = workspace / "scratch"
    scratch.mkdir(exist_ok=True)

    def one(item: dict) -> dict:
        case = improvement.Case(case_directory(workspace, item["case"]), workspace / "packages")
        last = item["chain"][-1]
        text = (workspace / "runs" / arguments.name / arguments.arm / item["case"].replace(":", "--")
                / f"step{last['step']}_attempt{last['attempt']}.py").read_text(encoding="utf-8")
        row = {"case": item["case"], "candidate_sha256": last["candidate_sha256"], "final_ratio": item["final_ratio"]}
        if improvement.text_digest(text) != last["candidate_sha256"]:
            raise SystemExit(f"{item['case']}: the stored rewrite does not match the sealed record")
        try:
            improvement.checked_private(text, case.source, case.name, case.data["package_import"])
        except improvement.ImprovementError as error:
            row.update(verdict="private access", detail=str(error)[:200])
        else:
            reference = case.variants(scratch)
            rows = improvement.variant_rows(case, improvement.patched(case.source, case.name, text), scratch)
            missed = improvement.variant_differences(reference, rows)
            row.update(variants=len(reference), different_variants=len(missed),
                       verdict="differs on variants" if missed else "kept" if reference else "no usable variant")
            if missed:
                row["first"] = {key: str(value)[:240] for key, value in missed[0].items()}
        print(json.dumps({key: row[key] for key in ("case", "verdict")}), flush=True)
        return row

    improved = [item for item in result["records"][arguments.arm] if item["chain_length"]]
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        rows = list(pool.map(one, improved))
    counts: dict = {}
    for row in rows:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    body = {"schema": "genesis-improvement-rejudge-v1", "trial": arguments.name, "arm": arguments.arm,
            "result_digest": result["result_digest"], "machinery": machinery(), "improved": len(rows),
            "verdicts": dict(sorted(counts.items())), "rows": rows}
    seal(HOME / arguments.name / f"STRICT_REJUDGE_{arguments.arm.upper()}.json", body, "rejudge_digest")
    print(json.dumps({"improved": len(rows), "verdicts": body["verdicts"]}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("fetch", fetch), ("record", record), ("prepare", prepare), ("plan", plan),
                           ("run", run), ("report", report), ("rejudge", rejudge)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--workspace", required=True)
        if name in ("record", "prepare"):
            command.add_argument("--package", action="append")
        if name in ("record", "prepare", "run", "rejudge"):
            command.add_argument("--workers", type=int, default=4)
        if name == "prepare":
            command.add_argument("--per-package", type=int, default=20)
        if name in ("plan", "run", "report", "rejudge"):
            command.add_argument("--name", required=True)
        if name == "rejudge":
            command.add_argument("--arm", default="isolated")
        if name == "plan":
            command.add_argument("--role", choices=("pilot", "trial"), required=True)
            command.add_argument("--cases", type=int, default=0)
            command.add_argument("--arms", default="isolated,accumulating")
            command.add_argument("--model", default="anthropic/claude-haiku-5.5")
            command.add_argument("--max-tokens", type=int, default=6000)
            command.add_argument("--steps", type=int, default=6)
            command.add_argument("--attempts", type=int, default=2)
            command.add_argument("--batch", type=int, default=8)
            command.add_argument("--warm-up", type=int, default=24)
            command.add_argument("--ceiling", type=float, default=3.0)
            command.add_argument("--judge", choices=("recorded", "strict"), default="recorded")
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
