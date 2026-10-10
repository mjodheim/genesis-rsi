#!/usr/bin/env python3
"""Search programs that combine archived fault localizers, and judge them on unseen projects.

    answers   run every archived module once on the prepared external cases and keep its answers
    plan      freeze the archive, the answers, the roles of the cases and the search
    evolve    diagnose, search on the search cases, promote on the selection cases
    ablate    repeat the search with one operation removed at a time (search and selection cases)
    verify    score the chain once on the external cases kept for it

No model is called and no key is read. Held-out cases of the repair bench are never involved.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import localizer_lineage as lineage  # noqa: E402
from genesis import localizer_programs as programs  # noqa: E402
from genesis import localizer_recombination as recombination  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

LOCALIZERS = ROOT / "experiment/localizer"
EXTERNAL = ROOT / "experiment/external"
CATALOGUE = ROOT / "experiment/bench/EXTERNAL_LOCALIZATION_V1.json"
LINEAGES = ("LOCALIZER1", "LOCALIZER2")
MACHINERY = ("genesis/localizer_lineage.py", "genesis/localizer_programs.py", "genesis/localizer_recombination.py",
             "scripts/run_localizer_programs.py")


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
        frozen = sealed(LOCALIZERS / name / "LINEAGE.json", "lineage_digest")
        for path in sorted((LOCALIZERS / name / "modules").glob("*.py.txt")):
            source = path.read_text(encoding="utf-8")
            digest = lineage.source_digest(source)
            if digest != frozen["module_sha256"][path.name]:
                raise SystemExit(f"{name}/{path.name}: module differs from the frozen lineage")
            if digest not in seen:
                seen.add(digest)
                found[f"{name}:{path.name[:-7]}"] = {"source_sha256": digest, "path": str(path.relative_to(ROOT))}
    return found


def external_cases(workspace: Path, part: str) -> list[str]:
    listed = sealed(CATALOGUE, "catalogue_digest")["cases"]
    return sorted(case for case, entry in listed.items() if entry["part"] == part
                  and (workspace / "cases" / case / "case.json").is_file()
                  and (workspace / "truth" / f"{case}.json").is_file())


def stored(directory: Path, member: str) -> Path:
    return directory / (member.replace(":", "--") + ".json")


def answers(arguments) -> None:
    workspace = Path(arguments.external).resolve()
    cases = external_cases(workspace, "first") + external_cases(workspace, "second")
    image = sealed(LOCALIZERS / "LOCALIZER1" / "PLAN.json", "plan_digest")["python_image"]
    scratch = workspace / "runs"
    scratch.mkdir(exist_ok=True)

    def one(item) -> str:
        name, entry = item
        path = stored(workspace / "answers", name)
        if not path.is_file():
            outputs = lineage.run_module((ROOT / entry["path"]).read_text(encoding="utf-8"), cases, image=image,
                                         cases_directory=workspace / "cases", scratch=scratch)
            kept = {case: lineage.clean_locations((outputs.get(case) or {}).get("locations")) for case in cases}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(kept, sort_keys=True), encoding="utf-8")
            print(json.dumps({"member": name, "answered": sum(bool(value) for value in kept.values())}), flush=True)
        return name

    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        done = list(pool.map(one, archive().items()))
    print(json.dumps({"members": len(done), "cases": len(cases)}))


def truth_of(directory: Path, cases) -> dict:
    return {case: json.loads((directory / "truth" / f"{case}.json").read_text(encoding="utf-8"))["sites"]
            for case in cases}


def case_digest(workspace: Path, case: str) -> str:
    return digest_of({"case": (workspace / "cases" / case / "case.json").read_text(encoding="utf-8"),
                      "truth": (workspace / "truth" / f"{case}.json").read_text(encoding="utf-8")})


def plan(arguments) -> None:
    development, workspace = Path(arguments.development).resolve(), Path(arguments.external).resolve()
    home = LOCALIZERS / arguments.name
    if (home / "PLAN.json").exists():
        raise SystemExit(f"{arguments.name} already has a plan")
    members = archive()
    for name in members:
        members[name]["development_answers_sha256"] = digest_of(
            stored(development / "recombination" / "answers", name).read_text(encoding="utf-8"))
        members[name]["external_answers_sha256"] = digest_of(
            stored(workspace / "answers", name).read_text(encoding="utf-8"))
    roles = sealed(LOCALIZERS / "LOCALIZER1" / "PLAN.json", "plan_digest")["roles"]
    first = sorted(sealed(EXTERNAL / "EXTERNAL1" / "PLAN.json", "plan_digest")["case_digests"])
    final = external_cases(workspace, "second")
    recombined = sealed(LOCALIZERS / "RECOMBINE1" / "RECOMBINATION.json", "recombination_digest")
    body = {
        "schema": "genesis-localizer-programs-plan-v1", "name": arguments.name, "archive": members,
        "champion": recombined["chain"][0], "machinery": machinery(),
        "language": {"unary": {name: list(values) for name, values in programs.UNARY.items()},
                     "binary": list(programs.BINARY), "max_nodes": programs.MAX_NODES,
                     "max_items": programs.MAX_ITEMS},
        "cases": {
            "search": {"development_training": len(roles["training"]), "external_first": len(first),
                       "note": "the external first part was scored once for four localizers by EXTERNAL1; "
                               "it is used here as development material, not as evidence"},
            "selection": {"development_selection": len(roles["selection"])},
            "final": {"external_second": len(final), "digests": {case: case_digest(workspace, case) for case in final},
                      "note": "prepared and answered by every member, never scored"},
            "development_validation": "not used",
        },
        "protocol": {
            "seed": arguments.seed, "generations": arguments.generations, "rounds": arguments.rounds,
            "population": arguments.population, "kept": arguments.kept,
            "selection_margin": arguments.margin, "selection_alpha": arguments.alpha, "model_requests": 0,
            "rule": "each generation records what recombination can still reach, searches programs by mutation "
                    "and crossover on the search cases with seed + generation, and scores the best one, if it "
                    "beats the champion there, on the selection cases; it replaces the champion when gained - "
                    "lost >= margin and the one-sided exact sign test <= alpha; a promoted program joins the "
                    "archive as a member; the first generation without a promotion ends the run",
            "ablations": "the same run repeated with each operation removed in turn, on search and selection "
                         "cases only; descriptive, not scored on the final cases",
        },
        "questions": [
            {"name": "search", "parent": "champion", "child": "last of the chain",
             "asks": "does the searched program localize more than the model-written champion on unseen projects"},
            {"name": "against the hand-written rule", "parent": "composite of RECOMBINE1", "child": "last of the chain",
             "asks": "does the searched program localize more than the composite of the rule fixed by hand"},
        ],
        "final_rule": "the champion, the composite of RECOMBINE1 and every program of the chain are scored once on "
                      "the final cases; a gain is called established when the one-sided exact sign test is at "
                      "most 0.05; if the chain holds no program, the two reference localizers are still scored "
                      "and the search is reported as having produced nothing",
        "reference_composite": recombined["members"][recombined["chain"][-1]],
        "held_out_cases_involved": 0,
    }
    record = seal(home / "PLAN.json", body, "plan_digest")
    print(json.dumps({"members": len(members), "search": len(roles["training"]) + len(first),
                      "selection": len(roles["selection"]), "final": len(final), "plan_digest": record["plan_digest"]}))


def checked_plan(name: str, development: Path, workspace: Path) -> dict:
    record = sealed(LOCALIZERS / name / "PLAN.json", "plan_digest")
    if record["machinery"] != machinery():
        raise SystemExit("the machinery changed since the plan was frozen")
    for member, entry in record["archive"].items():
        for directory, key in ((development / "recombination" / "answers", "development_answers_sha256"),
                               (workspace / "answers", "external_answers_sha256")):
            if digest_of(stored(directory, member).read_text(encoding="utf-8")) != entry[key]:
                raise SystemExit(f"{member}: stored answers differ from the planned ones")
    return record


def material(record: dict, development: Path, workspace: Path) -> tuple[dict, dict, list, list, list]:
    """Answers and truth for every case of the plan, and the three groups of cases."""
    roles = sealed(LOCALIZERS / "LOCALIZER1" / "PLAN.json", "plan_digest")["roles"]
    first = sorted(sealed(EXTERNAL / "EXTERNAL1" / "PLAN.json", "plan_digest")["case_digests"])
    final = sorted(record["cases"]["final"]["digests"])
    searching, selection = roles["training"] + first, roles["selection"]
    known = {}
    for member in record["archive"]:
        merged = json.loads(stored(development / "recombination" / "answers", member).read_text(encoding="utf-8"))
        merged.update(json.loads(stored(workspace / "answers", member).read_text(encoding="utf-8")))
        known[member] = merged
    truth = {**truth_of(development, roles["training"] + selection), **truth_of(workspace, first)}
    return known, truth, searching, selection, final


def _run(record: dict, known: dict, truth: dict, searching: list, selection: list, allowed) -> dict:
    protocol = record["protocol"]
    return programs.evolve(record["champion"], known, truth, searching, selection, seed=protocol["seed"],
                           generations=protocol["generations"], rounds=protocol["rounds"],
                           population=protocol["population"], kept=protocol["kept"],
                           margin=protocol["selection_margin"], alpha=protocol["selection_alpha"], allowed=allowed)


def evolve(arguments) -> None:
    development, workspace = Path(arguments.development).resolve(), Path(arguments.external).resolve()
    record = checked_plan(arguments.name, development, workspace)
    home = LOCALIZERS / arguments.name
    if (home / "EVOLUTION.json").exists():
        raise SystemExit("this search was already run")
    known, truth, searching, selection, _ = material(record, development, workspace)
    outcome = _run(record, known, truth, searching, selection, programs.OPERATIONS)
    body = {"schema": "genesis-localizer-programs-evolution-v1", "name": arguments.name,
            "plan_digest": record["plan_digest"], **outcome}
    seal(home / "EVOLUTION.json", body, "evolution_digest")
    print(json.dumps({"chain": outcome["chain"], "attempts": [
        {key: attempt.get(key) for key in ("generation", "outcome", "reach", "parent_localized", "search_localized",
                                           "size", "selection", "program")}
        for attempt in outcome["attempts"]]}, indent=1))


def _ablation(job) -> dict:
    name, removed, development, workspace = job
    record = sealed(LOCALIZERS / name / "PLAN.json", "plan_digest")
    known, truth, searching, selection, _ = material(record, Path(development), Path(workspace))
    allowed = tuple(operation for operation in programs.OPERATIONS if operation != removed)
    outcome = _run(record, known, truth, searching, selection, allowed)
    return {"removed": removed, "chain_length": len(outcome["chain"]) - 1, "attempts": [
        {key: attempt.get(key) for key in ("generation", "outcome", "parent_localized", "search_localized", "size",
                                           "selection", "program")} for attempt in outcome["attempts"]]}


def ablate(arguments) -> None:
    development, workspace = Path(arguments.development).resolve(), Path(arguments.external).resolve()
    record = checked_plan(arguments.name, development, workspace)
    home = LOCALIZERS / arguments.name
    sealed(home / "EVOLUTION.json", "evolution_digest")
    if (home / "ABLATIONS.json").exists():
        raise SystemExit("the ablations were already run")
    jobs = [(arguments.name, removed, str(development), str(workspace)) for removed in programs.OPERATIONS]
    with ProcessPoolExecutor(max_workers=arguments.workers) as pool:
        rows = list(pool.map(_ablation, jobs))
    seal(home / "ABLATIONS.json", {"schema": "genesis-localizer-programs-ablations-v1", "name": arguments.name,
                                   "plan_digest": record["plan_digest"], "ablations": rows}, "ablations_digest")
    print(json.dumps([{"removed": row["removed"], "chain_length": row["chain_length"],
                       "first": {key: row["attempts"][0].get(key) for key in ("search_localized", "selection")}}
                      for row in rows], indent=1))


def verify(arguments) -> None:
    development, workspace = Path(arguments.development).resolve(), Path(arguments.external).resolve()
    record = checked_plan(arguments.name, development, workspace)
    home = LOCALIZERS / arguments.name
    frozen = sealed(home / "EVOLUTION.json", "evolution_digest")
    if (home / "FINAL.json").exists():
        raise SystemExit("the final cases were already scored for this search")
    cases = sorted(record["cases"]["final"]["digests"])
    for case in cases:
        if case_digest(workspace, case) != record["cases"]["final"]["digests"][case]:
            raise SystemExit(f"{case}: prepared case differs from the planned one")
    known = {member: json.loads(stored(workspace / "answers", member).read_text(encoding="utf-8"))
             for member in record["archive"]}
    truth = truth_of(workspace, cases)
    for name in frozen["chain"][1:]:
        known[name] = programs.answers_of(programs.checked(frozen["programs"][name], list(known)), known, cases)
    composite = record["reference_composite"]
    known[composite["name"]] = recombination.answers_of(composite, known)
    chain = frozen["chain"]
    evaluations = {name: programs.scored(known[name], truth, cases) for name in [*chain, composite["name"]]}
    pairs = [("composite of RECOMBINE1 against champion", chain[0], composite["name"])]
    if len(chain) > 1:
        pairs = [("search", chain[0], chain[-1]), ("against the hand-written rule", composite["name"], chain[-1]),
                 *pairs, *[(f"generation {index}", chain[index - 1], chain[index]) for index in range(2, len(chain))]]
    comparisons = []
    for label, parent, child in pairs:
        comparison = lineage.compare(evaluations[child], evaluations[parent])
        comparisons.append({"name": label, "parent_name": parent, "child_name": child, **comparison,
                            "established": comparison["one_sided_sign_test"] <= 0.05})
    body = {"schema": "genesis-localizer-programs-final-v1", "name": arguments.name,
            "evolution_digest": frozen["evolution_digest"], "final_cases": len(cases),
            "scores": {name: {key: evaluation[key] for key in ("localized", "any_site", "all_files")}
                       for name, evaluation in evaluations.items()},
            "comparisons": comparisons}
    seal(home / "FINAL.json", body, "final_digest")
    print(json.dumps({"cases": len(cases), "scores": body["scores"], "comparisons": [
        {key: row[key] for key in ("name", "parent", "child", "gained", "lost", "one_sided_sign_test")}
        for row in comparisons]}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("answers", answers), ("plan", plan), ("evolve", evolve), ("ablate", ablate),
                           ("verify", verify)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        command.add_argument("--external", required=True, help="workspace of the external cases")
        if name != "answers":
            command.add_argument("--development", required=True, help="workspace of the development cases")
            command.add_argument("--name", required=True)
        if name in ("answers", "ablate"):
            command.add_argument("--workers", type=int, default=3)
        if name == "plan":
            command.add_argument("--seed", type=int, default=20261010)
            command.add_argument("--generations", type=int, default=6)
            command.add_argument("--rounds", type=int, default=40)
            command.add_argument("--population", type=int, default=300)
            command.add_argument("--kept", type=int, default=60)
            command.add_argument("--margin", type=int, default=5)
            command.add_argument("--alpha", type=float, default=0.05)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
