#!/usr/bin/env python3
"""Recombine archived fault localizers without any model, and judge the result on unseen cases.

    answers   run every module of the sealed lineages once on the development cases, in the
              container, and keep what each returned
    plan      freeze the archive, the answers, the roles of the cases and the rule
    evolve    choose composites on training cases, promote them on selection cases
    verify    score the chain once on the validation cases

No model is called and no key is read. Held-out cases of the repair bench are never involved.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import localizer_lineage as lineage  # noqa: E402
from genesis import localizer_recombination as recombination  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

HOME = ROOT / "experiment/localizer"
LINEAGES = ("LOCALIZER1", "LOCALIZER2")
MACHINERY = ("genesis/localizer_lineage.py", "genesis/localizer_recombination.py",
             "scripts/run_localizer_recombination.py")


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


def archive() -> dict[str, dict]:
    """Every distinct module of the sealed lineages, promoted or not, by ``lineage:name``."""
    found, seen = {}, set()
    for name in LINEAGES:
        frozen = sealed(HOME / name / "LINEAGE.json", "lineage_digest")
        for path in sorted((HOME / name / "modules").glob("*.py.txt")):
            source = path.read_text(encoding="utf-8")
            digest = lineage.source_digest(source)
            if digest != frozen["module_sha256"][path.name]:
                raise SystemExit(f"{name}/{path.name}: module differs from the frozen lineage")
            if digest not in seen:
                seen.add(digest)
                found[f"{name}:{path.name[:-7]}"] = {"source_sha256": digest, "path": str(path.relative_to(ROOT))}
    return found


def roles() -> dict:
    return sealed(HOME / "LOCALIZER1" / "PLAN.json", "plan_digest")["roles"]


def stored(workspace: Path, member: str) -> Path:
    return workspace / "recombination" / "answers" / (member.replace(":", "--") + ".json")


def answers(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    plan = sealed(HOME / "LOCALIZER1" / "PLAN.json", "plan_digest")
    cases = sorted(case for group in plan["roles"].values() for case in group)
    scratch = workspace / "runs"
    scratch.mkdir(exist_ok=True)

    def one(item) -> str:
        member, entry = item
        path = stored(workspace, member)
        if not path.is_file():
            outputs = lineage.run_module((ROOT / entry["path"]).read_text(encoding="utf-8"), cases,
                                         image=plan["python_image"], cases_directory=workspace / "cases",
                                         scratch=scratch)
            kept = {case: lineage.clean_locations((outputs.get(case) or {}).get("locations")) for case in cases}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(kept, sort_keys=True), encoding="utf-8")
            print(json.dumps({"member": member, "answered": sum(bool(item) for item in kept.values())}), flush=True)
        return member

    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        done = list(pool.map(one, archive().items()))
    print(json.dumps({"members": len(done), "cases": len(cases)}))


def load_answers(workspace: Path, members, cases) -> dict:
    wanted = set(cases)
    return {member: {case: locations for case, locations in
                     json.loads(stored(workspace, member).read_text(encoding="utf-8")).items() if case in wanted}
            for member in members}


def plan(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    home = HOME / arguments.name
    if (home / "PLAN.json").exists():
        raise SystemExit(f"{arguments.name} already has a plan")
    members = archive()
    for member in members:
        members[member]["answers_sha256"] = digest_of(stored(workspace, member).read_text(encoding="utf-8"))
    champion = "LOCALIZER1:" + sealed(HOME / "LOCALIZER1" / "LINEAGE.json", "lineage_digest")["chain"][-1]
    body = {
        "schema": "genesis-localizer-recombination-plan-v1", "name": arguments.name, "archive": members,
        "champion": champion, "roles_from": "LOCALIZER1", "machinery": machinery(),
        "protocol": {
            "generations": arguments.generations, "selection_margin": arguments.margin,
            "selection_alpha": arguments.alpha,
            "rule": "each generation pairs the champion with every other member of the archive, in either order "
                    "and with every lead from 1 to 5; the composite localizing the most training cases, if more "
                    "than the champion, is scored on the selection cases and replaces the champion when gained - "
                    "lost >= margin and the one-sided exact sign test <= alpha; a promoted composite joins the "
                    "archive; the first generation without a promotion ends the run; validation cases are scored "
                    "once by verify",
            "model_requests": 0,
        },
        "validation_already_scored_for": list(LINEAGES), "held_out_cases_involved": 0,
    }
    record = seal(home / "PLAN.json", body, "plan_digest")
    print(json.dumps({"name": arguments.name, "members": len(members), "champion": champion,
                      "plan_digest": record["plan_digest"]}))


def checked_plan(name: str, workspace: Path) -> dict:
    record = sealed(HOME / name / "PLAN.json", "plan_digest")
    if record["machinery"] != machinery():
        raise SystemExit("the machinery changed since the plan was frozen")
    for member, entry in record["archive"].items():
        if digest_of(stored(workspace, member).read_text(encoding="utf-8")) != entry["answers_sha256"]:
            raise SystemExit(f"{member}: stored answers differ from the planned ones")
    return record


def load_truth(workspace: Path, cases) -> dict:
    return {case: json.loads((workspace / "truth" / f"{case}.json").read_text(encoding="utf-8"))["sites"]
            for case in cases}


def evolve(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    home = HOME / arguments.name
    if (home / "RECOMBINATION.json").exists():
        raise SystemExit("this recombination was already run")
    groups = roles()
    scored = groups["training"] + groups["selection"]
    truth = load_truth(workspace, scored)
    known = load_answers(workspace, record["archive"], scored)
    protocol = record["protocol"]
    outcome = recombination.evolve(record["champion"], known, truth, groups["training"], groups["selection"],
                                   generations=protocol["generations"], margin=protocol["selection_margin"],
                                   alpha=protocol["selection_alpha"])
    body = {"schema": "genesis-localizer-recombination-v1", "name": arguments.name,
            "plan_digest": record["plan_digest"], **outcome,
            "champion_scores": {name: {role: {key: recombination.scored(known[name], truth, groups[role])[key]
                                              for key in ("localized", "any_site", "all_files", "case_count")}
                                       for role in ("training", "selection")} for name in outcome["chain"]}}
    seal(home / "RECOMBINATION.json", body, "recombination_digest")
    print(json.dumps({"chain": outcome["chain"], "attempts": [
        {key: attempt.get(key) for key in ("generation", "outcome", "training_localized", "selection")}
        for attempt in outcome["attempts"]]}, indent=1))


def verify(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    record = checked_plan(arguments.name, workspace)
    home = HOME / arguments.name
    frozen = sealed(home / "RECOMBINATION.json", "recombination_digest")
    if (home / "VALIDATION.json").exists():
        raise SystemExit("the validation cases were already scored for this recombination")
    cases = roles()["validation"]
    truth = load_truth(workspace, cases)
    known = load_answers(workspace, record["archive"], cases)
    for name in frozen["chain"][1:]:
        known[name] = recombination.answers_of(frozen["members"][name], known)
    evaluations = {name: recombination.scored(known[name], truth, cases) for name in frozen["chain"]}
    chain = frozen["chain"]
    body = {"schema": "genesis-localizer-recombination-validation-v1", "name": arguments.name,
            "recombination_digest": frozen["recombination_digest"], "validation_cases": len(cases),
            "scores": {name: {key: evaluation[key] for key in ("localized", "any_site", "all_files")}
                       for name, evaluation in evaluations.items()},
            "steps": [{"parent": chain[index - 1], "child": chain[index],
                       **lineage.compare(evaluations[chain[index]], evaluations[chain[index - 1]])}
                      for index in range(1, len(chain))],
            "first_to_last": (lineage.compare(evaluations[chain[-1]], evaluations[chain[0]])
                              if len(chain) > 1 else None)}
    seal(home / "VALIDATION.json", body, "validation_digest")
    print(json.dumps({"scores": body["scores"], "first_to_last": body["first_to_last"] and {
        key: body["first_to_last"][key] for key in ("parent", "child", "gained", "lost", "one_sided_sign_test")}}))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("answers", answers), ("plan", plan), ("evolve", evolve), ("verify", verify)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--workspace", required=True)
        if name == "answers":
            command.add_argument("--workers", type=int, default=3)
        else:
            command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--generations", type=int, default=6)
            command.add_argument("--margin", type=int, default=5)
            command.add_argument("--alpha", type=float, default=0.05)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
