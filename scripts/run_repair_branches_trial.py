#!/usr/bin/env python3
"""Paired candidate-branch ablation; exposed development, common four-round genome, no promotion."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from genesis.g12_operator_lab import _write_new
from genesis.repair_local_revision import paired_summary
from genesis.repair_self_improvement import checked, sealed
from genesis.trust_root import digest_of
from genesis.repair_lineage import genome_digest, checked_genome, fits
from scripts.run_real_repair_transfer import load_api_key
from scripts.run_repair_lineage import envelope_of, ledger_for, prepare, run_case


def plan(output, workspace):
    if output.exists() or workspace.exists():
        raise ValueError("fresh trial directories required")
    old = json.loads((ROOT / "experiment/bench/LINEAGE2/PLAN.json").read_text())
    checked(old, "plan_digest")
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        models = json.load(response)["data"]
    model = next(m for m in models if m["id"] == old["envelope"]["model"])
    if float(model["pricing"]["prompt"]) * 1e6 > .2 or float(model["pricing"]["completion"]) * 1e6 > 1:
        raise ValueError("approved tariff ceiling exceeded")
    files = sorted((ROOT / "genesis").glob("*.py")) + [
        Path(__file__).resolve(), ROOT / "scripts/run_repair_lineage.py",
        ROOT / "scripts/run_real_repair_transfer.py"]
    hashes = {str(p.relative_to(ROOT)): digest_of(p.read_bytes().hex()) for p in files}
    image = subprocess.check_output([
        "docker", "image", "inspect", "genesis-defects4j:8c16da8", "--format", "{{.Id}}"], text=True).strip()
    output.mkdir(parents=True)
    workspace.mkdir(parents=True)
    for name in hashes:
        target = workspace / "snapshot" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    seed = checked_genome({**old["seed_genome"], "search": {"inspection_requests": 1, "candidates_per_round": 1, "rounds": 4}})
    if not fits(seed, envelope_of(old)):
        raise ValueError("common search allocation exceeds envelope")
    _write_new(output / "PLAN.json", sealed(dict(
        schema="genesis-repair-branches-development-v1", cases=old["selection_cases"][:3],
        selection="first three LINEAGE2 selection cases; previously exposed development",
        replicates=2, seed_genome=seed, envelope=old["envelope"],
        common_search_adapter="human-authored four rounds, one inspection request and one candidate per round; both arms get the same allocation",
        spending_ceiling_usd=.20, catalog=dict(id=model["id"], pricing=model["pricing"]),
        workspace=str(workspace), machinery_digests=hashes, image=image,
        order="parent first when (replicate + case index) is odd; otherwise child first",
        arms=dict(parent="application_feedback=True, multi_file=True, branching=False",
                  child="application_feedback=True, multi_file=True, branching=True"),
        file_limit_both_arms=3,
        representation_adapter="child adds parent digest and virtual branch reads; complete inherited edits are always validated from original tree",
        acceptance="more repaired case-runs with no paired losses warrants a larger test only",
        secondary="graded-parent extensions, virtual reads, branch depth, regressions, requests, validations, API cost and elapsed arm time",
        separate_environment=True, promotion=False, held_out_consumed=False,
        cumulative_descendant_history_tested=False, fixed_revision_consulted=False,
        scope="authored infrastructure ablation; same external model and genome; not RSI evidence",
    ), "plan_digest"))


def verify(output):
    plan = json.loads((output / "PLAN.json").read_text())
    checked(plan, "plan_digest")
    result = json.loads((output / "RESULT.json").read_text())
    checked(result, "result_digest")
    if result["plan_digest"] != plan["plan_digest"]:
        raise ValueError("wrong plan")
    if len(result["rows"]) != len(plan["cases"]) * plan["replicates"]:
        raise ValueError("incomplete result")
    receipts = []
    for row, (replicate, index, case) in zip(result["rows"], [
        (r, i, c) for r in range(1, plan["replicates"] + 1) for i, c in enumerate(plan["cases"]) ]):
        order = ["parent", "child"] if (replicate + index) % 2 else ["child", "parent"]
        if (row["case"], row["replicate"], row["order"]) != (case, replicate, order):
            raise ValueError("wrong pairing/order")
        for arm in order:
            body = row[arm]
            checked(body, "arm_digest")
            if body["validated"] > plan["envelope"]["validations_per_case"]:
                raise ValueError("validation budget exceeded")
            if len(body["calls"]) > plan["envelope"]["model_requests_per_case"]:
                raise ValueError("request budget exceeded")
            receipts.extend(dict(case=case, label=f"branches-r{replicate}-{arm}", call=c) for c in body["calls"])
    if result["summary"] != paired_summary(result["rows"]):
        raise ValueError("summary differs")
    if result["summary"]["unknown_cost_calls"]:
        raise ValueError("unknown costs prevent complete cost verification")
    if result["summary"]["known_api_cost_usd"] > plan["spending_ceiling_usd"]:
        raise ValueError("spending ceiling exceeded")
    journal = json.loads((output / "JOURNAL.json").read_text())
    checked(journal, "journal_digest")
    if any(r["genome"] != genome_digest(plan["seed_genome"]) for r in journal["calls"]):
        raise ValueError("journal genome differs")
    for row in result["rows"]:
        for arm in ("parent", "child"):
            graded = {v["candidate_digest"] for v in row[arm]["verdicts"]}
            earlier = {}
            for call in row[arm]["calls"]:
                for proposal in call.get("submission_results", []):
                    if ("parent" in proposal) != (arm == "child"):
                        raise ValueError("wrong branch mode")
                    if proposal.get("applicable"):
                        if not isinstance(proposal["files"], list) or not 1 <= len(proposal["files"]) <= 3:
                            raise ValueError("file delta limit exceeded")
                        if arm == "child":
                            paths = proposal["complete_paths"]
                            if not 1 <= len(paths) <= 3 or len(paths) != len(set(paths)):
                                raise ValueError("complete candidate file limit exceeded")
                            parent = proposal["parent"]
                            if parent and (parent not in graded or parent not in earlier or earlier[parent] >= call["round"]):
                                raise ValueError("parent was not a graded earlier-round candidate")
                            earlier.setdefault(proposal["candidate_digest"], call["round"])
    actual = [dict(case=r["case"], label=r["label"], call=r["call"]) for r in journal["calls"]]
    if actual != receipts:
        raise ValueError("journal differs from receipts")
    return dict(verified=True, calls=len(receipts), independently_replicated=False)


def execute(output):
    plan = json.loads((output / "PLAN.json").read_text())
    checked(plan, "plan_digest")
    if (output / "RESULT.json").exists():
        raise ValueError("trial already completed")
    for name, identity in plan["machinery_digests"].items():
        if digest_of((ROOT / name).read_bytes().hex()) != identity:
            raise ValueError("frozen machinery changed")
    image = subprocess.check_output([
        "docker", "image", "inspect", "genesis-defects4j:8c16da8", "--format", "{{.Id}}"], text=True).strip()
    if image != plan["image"]:
        raise ValueError("container image changed")
    workspace = Path(plan["workspace"])
    load_api_key()
    ledger = ledger_for(workspace, plan["spending_ceiling_usd"])
    envelope = envelope_of(plan)
    rows = []
    for case in plan["cases"]:
        setup = prepare(workspace, case, True)
        if not setup["usable"]:
            raise ValueError("unusable case: " + case)
    for replicate in range(1, plan["replicates"] + 1):
        for index, case in enumerate(plan["cases"]):
            order = ["parent", "child"] if (replicate + index) % 2 else ["child", "parent"]
            arms = {}
            for arm in order:
                target = output / f"{case}.r{replicate}.{arm}.json"
                if target.exists():
                    body = json.loads(target.read_text())
                    checked(body, "arm_digest")
                else:
                    body = sealed(run_case(workspace, case, plan["seed_genome"], envelope, ledger,
                        f"branches-r{replicate}-{arm}", application_feedback=True, multi_file=True, branching=arm == "child"), "arm_digest")
                    _write_new(target, body)
                arms[arm] = body
                print(case, replicate, arm, body["solved"], "validated", body["validated"],
                      "spent", ledger.spent, flush=True)
            rows.append(dict(case=case, replicate=replicate, order=order, **arms))
    calls = [json.loads(line) for line in (workspace / "calls.jsonl").read_text().splitlines()]
    _write_new(output / "JOURNAL.json", sealed(dict(calls=calls), "journal_digest"))
    summary = paired_summary(rows)
    _write_new(output / "RESULT.json", sealed(dict(plan_digest=plan["plan_digest"], rows=rows, summary=summary,
        decision="larger_test_candidate" if summary["warrants_larger_test"] else "no_demonstrated_gain",
        policy_promoted=False, held_out_consumed=False), "result_digest"))
    _write_new(output / "VERIFICATION.json", verify(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "execute", "verify"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workspace", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "plan":
        plan(output, args.workspace.resolve())
    elif args.action == "execute":
        execute(output)
    else:
        print(json.dumps(verify(output)))
