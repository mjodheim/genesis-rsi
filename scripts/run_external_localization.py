#!/usr/bin/env python3
"""Score frozen fault localizers on bugs of projects that took no part in their development.

    catalogue  read a checkout of a Defects4J-format catalogue and freeze which bugs are eligible
               and which part each repository falls in
    prepare    fetch the sources of one part and build its cases (network: public repositories)
    plan       freeze the prepared cases, the localizers compared and the questions asked
    score      run the localizers once in the container and seal the paired outcomes

No model is called and no key is read. Cases of the Defects4J catalogue are never involved.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import external_localization as external  # noqa: E402
from genesis import localizer_lineage as lineage  # noqa: E402
from genesis import localizer_recombination as recombination  # noqa: E402
from genesis.trust_root import digest_of  # noqa: E402

SPLIT = ROOT / "experiment/bench/REPAIR_BENCH_SPLIT_V1.json"
CATALOGUE = ROOT / "experiment/bench/EXTERNAL_LOCALIZATION_V1.json"
LOCALIZERS = ROOT / "experiment/localizer"
HOME = ROOT / "experiment/external"
MACHINERY = ("genesis/external_localization.py", "genesis/localizer_lineage.py",
             "genesis/localizer_recombination.py", "scripts/run_external_localization.py")
INFORMATION = "framework/bug-mining/bug_mining_projects_info.txt"
GIT = {"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


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


def git(*arguments: str, cwd: Path | None = None, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *arguments], cwd=cwd, env={**os.environ, **GIT}, capture_output=True,
                          timeout=timeout, check=False)


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# -- catalogue ----------------------------------------------------------------------------------


def projects_of(source: Path) -> dict[str, dict]:
    found = {}
    for line in (source / INFORMATION).read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split("\t")
        if len(fields) >= 7 and fields[0] and fields[2].startswith("http"):
            found[fields[0]] = {"repository": fields[2].strip(), "subproject": fields[6].strip() or "."}
    return found


def bugs_of(source: Path, project: str) -> list[dict]:
    path = source / "framework/projects" / project / "active-bugs.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", errors="replace", newline="") as stream:
        return [row for row in csv.DictReader(stream) if (row.get("bug.id") or "").isdigit()]


def catalogue(arguments) -> None:
    source = Path(arguments.source).resolve()
    if CATALOGUE.exists():
        raise SystemExit("the catalogue is already frozen")
    revision = git("rev-parse", "HEAD", cwd=source).stdout.decode().strip()
    origin = git("remote", "get-url", "origin", cwd=source).stdout.decode().strip()
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    used_projects = sorted({case.rsplit("-", 1)[0] for group in ("development", "held_out", "exposed_cases")
                            for case in split[group]})
    projects = projects_of(source)
    used_repositories = [projects[name]["repository"] for name in used_projects if name in projects]
    used_revisions = {row[key] for name in used_projects for row in bugs_of(source, name)
                      for key in ("revision.id.buggy", "revision.id.fixed")}
    cases, excluded = {}, {}
    for project in sorted(projects):
        entry, bugs = projects[project], bugs_of(source, project)
        reason = external.independent(
            project, entry["repository"],
            [row[key] for row in bugs for key in ("revision.id.buggy", "revision.id.fixed")],
            used_projects=used_projects, used_repositories=used_repositories, used_revisions=used_revisions)
        if reason:
            excluded[project] = reason
            continue
        base = source / "framework/projects" / project
        rows = {row["bug.id"]: row for row in bugs
                if (base / "patches" / f"{row['bug.id']}.src.patch").is_file()
                and (base / "trigger_tests" / row["bug.id"]).is_file()}
        for bug in external.kept_bugs(project, rows):
            cases[f"{project}-{bug}"] = {
                "project": project, "bug": int(bug), "repository": external.repository_key(entry["repository"]),
                "subproject": entry["subproject"], "part": external.part_of(entry["repository"]),
                "buggy": rows[bug]["revision.id.buggy"], "fixed": rows[bug]["revision.id.fixed"],
                "patch_sha256": file_digest(base / "patches" / f"{bug}.src.patch"),
                "trigger_sha256": file_digest(base / "trigger_tests" / bug)}
    body = {
        "schema": "genesis-external-localization-catalogue-v1", "source": origin, "source_revision": revision,
        "development_split_digest": split["split_digest"],
        "rule": {
            "eligible": "a project listed with a repository address, absent from the development catalogue by "
                        "name, by repository and by revision, with a source patch and a trigger report per bug",
            "per_project": f"at most {external.PER_PROJECT} bugs, the first by sha256({external.DOMAIN!r} + case)",
            "parts": f"sha256({external.DOMAIN!r} + repository) mod 10: 0-3 first, 4-6 second, 7-9 reserve",
        },
        "excluded_projects": excluded, "cases": cases,
        "counts": {part: sum(case["part"] == part for case in cases.values()) for part in external.PARTS},
    }
    record = seal(CATALOGUE, body, "catalogue_digest")
    print(json.dumps({"cases": len(cases), **body["counts"], "excluded": excluded,
                      "catalogue_digest": record["catalogue_digest"]}))


def checked_catalogue(source: Path | None = None) -> dict:
    record = sealed(CATALOGUE, "catalogue_digest")
    if source is not None and git("rev-parse", "HEAD", cwd=source).stdout.decode().strip() != record["source_revision"]:
        raise SystemExit("the catalogue checkout is not at the frozen revision")
    return record


# -- prepare ------------------------------------------------------------------------------------

_LOCKS: dict[str, threading.Lock] = {}
_GUARD = threading.Lock()


def repository(workspace: Path, key: str) -> Path | None:
    """A clone of a repository without file contents; contents are fetched for what is extracted."""
    path = workspace / "repositories" / (hashlib.sha256(key.encode()).hexdigest()[:16] + ".git")
    with _GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock:
        if not (path / "HEAD").is_file():
            shutil.rmtree(path, ignore_errors=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            if git("clone", "--quiet", "--bare", "--filter=blob:none", f"https://{key}.git", str(path)).returncode:
                shutil.rmtree(path, ignore_errors=True)
                return None
    return path


def extract(clone: Path, revision: str, directories: list[str], target: Path) -> bool:
    if git("cat-file", "-e", f"{revision}^{{commit}}", cwd=clone).returncode:
        git("fetch", "--quiet", "--filter=blob:none", "origin", revision, cwd=clone)
    present = [name for name in directories
               if git("cat-file", "-e", f"{revision}:{name}", cwd=clone).returncode == 0]
    if not present or directories[0] not in present:
        return False
    target.mkdir(parents=True, exist_ok=True)
    archive = subprocess.Popen(["git", "archive", "--format=tar", revision, "--", *present], cwd=clone,
                               env={**os.environ, **GIT}, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    unpacked = subprocess.run(["tar", "-x", "--no-same-owner", "-C", str(target)], stdin=archive.stdout,
                              capture_output=True, timeout=1800, check=False)
    return archive.wait() == 0 and unpacked.returncode == 0


def copy_java(source: Path, target: Path) -> int:
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


def prepare_case(case: str, entry: dict, source: Path, workspace: Path) -> dict:
    """The buggy sources as the catalogue defines them: the fixed revision with the source patch applied."""
    target, truth_path = workspace / "cases" / case, workspace / "truth" / f"{case}.json"
    if (target / "case.json").is_file() and truth_path.is_file():
        return {"case": case, "status": "ready"}
    base = source / "framework/projects" / entry["project"]
    patch_path, trigger = base / "patches" / f"{entry['bug']}.src.patch", base / "trigger_tests" / str(entry["bug"])
    if file_digest(patch_path) != entry["patch_sha256"] or file_digest(trigger) != entry["trigger_sha256"]:
        return {"case": case, "status": "excluded", "reason": "patch or trigger report differs from the catalogue"}
    patch = patch_path.read_text(encoding="utf-8", errors="replace")
    with (base / "dir-layout.csv").open(encoding="utf-8", errors="replace", newline="") as stream:
        layout = external.layout_of(csv.reader(stream), [entry["fixed"], entry["buggy"]])
    if layout is None:
        return {"case": case, "status": "excluded", "reason": "no recorded directory layout"}
    paths = [line[4:].split("\t")[0].strip().removeprefix("b/") for line in patch.splitlines()
             if line.startswith("+++ ")]
    sources = external.source_directory(paths, entry["subproject"], layout[0])
    if sources is None:
        return {"case": case, "status": "excluded", "reason": "the patch edits no file of the source directory"}
    tests = external.joined(sources[:len(sources) - len(external.joined(layout[0]))], layout[1])
    clone = repository(workspace, entry["repository"])
    if clone is None:
        return {"case": case, "status": "excluded", "reason": "repository could not be cloned"}
    checkout = workspace / "work" / f"w-{case}"
    shutil.rmtree(checkout, ignore_errors=True)
    try:
        if not extract(clone, entry["fixed"], [sources, tests], checkout):
            return {"case": case, "status": "excluded", "reason": "fixed revision or source directory not found"}
        applied = git("apply", "--whitespace=nowarn", f"--include={sources}/*", str(patch_path), cwd=checkout)
        if applied.returncode:
            return {"case": case, "status": "excluded", "reason": "the source patch does not apply"}
        sites = lineage.edit_sites(patch, sources)
        if not sites or any(not (checkout / site["path"]).is_file() for site in sites):
            return {"case": case, "status": "excluded", "reason": "no edit site in an existing production file"}
        report = trigger.read_text(encoding="utf-8", errors="replace")[:400_000]
        failing = lineage.re.findall(r"^--- (\S+)\s*$", report, flags=lineage.re.MULTILINE)
        if not failing:
            return {"case": case, "status": "excluded", "reason": "trigger report names no test"}
        shutil.rmtree(target, ignore_errors=True)
        copy_java(checkout / sources, target / "tree" / sources)
        if (checkout / tests).is_dir():
            copy_java(checkout / tests, target / "tree" / tests)
        body = {"source_directory": sources, "test_directory": tests, "failing_tests": failing, "report": report}
        truth_path.parent.mkdir(parents=True, exist_ok=True)
        truth_path.write_text(json.dumps({"case": case, "sites": sites}, sort_keys=True), encoding="utf-8")
        (target / "case.json").write_text(json.dumps(body, sort_keys=True), encoding="utf-8")
        return {"case": case, "status": "ready"}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"case": case, "status": "excluded", "reason": f"preparation failed: {type(error).__name__}"}
    finally:
        shutil.rmtree(checkout, ignore_errors=True)


def prepare(arguments) -> None:
    source, workspace = Path(arguments.source).resolve(), Path(arguments.workspace).resolve()
    record = checked_catalogue(source)
    wanted = {case: entry for case, entry in sorted(record["cases"].items()) if entry["part"] == arguments.part}
    for name in ("work", "cases", "truth", "repositories"):
        (workspace / name).mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[str]] = {}
    for case, entry in wanted.items():
        groups.setdefault(entry["repository"], []).append(case)

    def one(cases: list[str]) -> list[dict]:
        return [prepare_case(case, wanted[case], source, workspace) for case in cases]

    log = workspace / f"prepare-{arguments.part}.jsonl"
    with ThreadPoolExecutor(max_workers=arguments.workers) as pool, log.open("w", encoding="utf-8") as stream:
        for records in pool.map(one, groups.values()):
            for item in records:
                stream.write(json.dumps(item, sort_keys=True) + "\n")
            stream.flush()
    print(json.dumps({"part": arguments.part, "cases": len(wanted), "ready": sum(
        (workspace / "cases" / case / "case.json").is_file() for case in wanted)}))


# -- plan ---------------------------------------------------------------------------------------


def case_digest(workspace: Path, case: str) -> str:
    return digest_of({
        "case": (workspace / "cases" / case / "case.json").read_text(encoding="utf-8"),
        "truth": (workspace / "truth" / f"{case}.json").read_text(encoding="utf-8"),
    })


def module(member: str) -> Path:
    name, generation = member.split(":")
    return LOCALIZERS / name / "modules" / f"{generation}.py.txt"


def plan(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    home = HOME / arguments.name
    if (home / "PLAN.json").exists():
        raise SystemExit(f"{arguments.name} already has a plan")
    record = checked_catalogue()
    wanted = sorted(case for case, entry in record["cases"].items() if entry["part"] == arguments.part)
    ready = [case for case in wanted if (workspace / "cases" / case / "case.json").is_file()
             and (workspace / "truth" / f"{case}.json").is_file()]
    reasons = {}
    for line in (workspace / f"prepare-{arguments.part}.jsonl").read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item["status"] != "ready":
            reasons[item["case"]] = item["reason"]
    frozen = sealed(LOCALIZERS / arguments.recombination / "RECOMBINATION.json", "recombination_digest")
    composite = frozen["members"][frozen["chain"][-1]]
    seed, champion = frozen["chain"][0].split(":")[0] + ":g0", frozen["chain"][0]
    members = sorted({seed, champion, composite["first"], composite["second"]})
    body = {
        "schema": "genesis-external-localization-plan-v1", "name": arguments.name,
        "catalogue_digest": record["catalogue_digest"], "part": arguments.part,
        "listed_cases": len(wanted), "prepared_cases": len(ready), "excluded_cases": reasons,
        "case_digests": {case: case_digest(workspace, case) for case in ready},
        "modules": {member: lineage.source_digest(module(member).read_text(encoding="utf-8")) for member in members},
        "composite": composite, "composite_from": {"recombination": arguments.recombination,
                                                   "recombination_digest": frozen["recombination_digest"]},
        "questions": [
            {"name": "lineage", "parent": seed, "child": champion,
             "asks": "does the gain of the model-written lineage over its seed hold on projects it never saw"},
            {"name": "recombination", "parent": champion, "child": composite["name"],
             "asks": "does the composite promoted without a model localize more than the champion it replaced"},
        ],
        "measure": {"max_locations": lineage.MAX_LOCATIONS, "window_lines": lineage.WINDOW,
                    "case_seconds": lineage.CASE_SECONDS, "primary": "localized: every edit site covered"},
        "rule": "each module runs once on every prepared case of the part; each question is the paired outcome "
                "of child against parent on those cases; a gain is called established when the one-sided exact "
                "sign test is at most 0.05; both questions are reported whatever their outcome, with the "
                "per-project counts; the cases of this part are not scored again for these localizers",
        "python_image": sealed(LOCALIZERS / "LOCALIZER1" / "PLAN.json", "plan_digest")["python_image"],
        "model_requests": 0, "defects4j_cases_involved": 0, "machinery": machinery(),
    }
    seal(home / "PLAN.json", body, "plan_digest")
    print(json.dumps({"listed": len(wanted), "prepared": len(ready), "modules": members,
                      "composite": composite["name"]}))


# -- score --------------------------------------------------------------------------------------


def by_project(comparison: dict, catalogue_cases: dict) -> dict:
    table: dict[str, dict] = {}
    for key in ("gained_cases", "lost_cases"):
        for case in comparison[key]:
            row = table.setdefault(catalogue_cases[case]["project"], {"gained": 0, "lost": 0})
            row[key.split("_")[0]] += 1
    return {"projects_with_a_net_gain": sum(row["gained"] > row["lost"] for row in table.values()),
            "projects_with_a_net_loss": sum(row["gained"] < row["lost"] for row in table.values()),
            "projects_level": sum(row["gained"] == row["lost"] for row in table.values()), "projects": table}


def score(arguments) -> None:
    workspace = Path(arguments.workspace).resolve()
    home = HOME / arguments.name
    record = sealed(home / "PLAN.json", "plan_digest")
    if record["machinery"] != machinery():
        raise SystemExit("the machinery changed since the plan was frozen")
    if (home / "RESULT.json").exists():
        raise SystemExit("these cases were already scored for this plan")
    cases = sorted(record["case_digests"])
    for case in cases:
        if case_digest(workspace, case) != record["case_digests"][case]:
            raise SystemExit(f"{case}: prepared case differs from the planned one")
    scratch = workspace / "runs"
    scratch.mkdir(exist_ok=True)

    def one(member: str) -> tuple[str, dict]:
        source = module(member).read_text(encoding="utf-8")
        if lineage.source_digest(source) != record["modules"][member]:
            raise SystemExit(f"{member}: module differs from the planned one")
        outputs = lineage.run_module(source, cases, image=record["python_image"],
                                     cases_directory=workspace / "cases", scratch=scratch)
        return member, {case: lineage.clean_locations((outputs.get(case) or {}).get("locations")) for case in cases}

    with ThreadPoolExecutor(max_workers=arguments.workers) as pool:
        answers = dict(pool.map(one, sorted(record["modules"])))
    composite = record["composite"]
    answers[composite["name"]] = recombination.answers_of(composite, answers)
    truth = {case: json.loads((workspace / "truth" / f"{case}.json").read_text(encoding="utf-8"))["sites"]
             for case in cases}
    evaluations = {name: recombination.scored(locations, truth, cases) for name, locations in answers.items()}
    catalogue_cases = checked_catalogue()["cases"]
    questions = []
    for question in record["questions"]:
        comparison = lineage.compare(evaluations[question["child"]], evaluations[question["parent"]])
        questions.append({**question, **comparison, "established": comparison["one_sided_sign_test"] <= 0.05,
                          "by_project": by_project(comparison, catalogue_cases)})
    body = {"schema": "genesis-external-localization-result-v1", "name": arguments.name,
            "plan_digest": record["plan_digest"], "cases": len(cases),
            "projects": len({catalogue_cases[case]["project"] for case in cases}),
            "scores": {name: {key: evaluation[key] for key in ("localized", "any_site", "all_files", "errors")}
                       for name, evaluation in evaluations.items()},
            "answers_sha256": {name: digest_of(locations) for name, locations in answers.items()},
            "questions": questions}
    seal(home / "RESULT.json", body, "result_digest")
    print(json.dumps({"cases": len(cases), "scores": body["scores"], "questions": [
        {key: question[key] for key in ("name", "parent", "child", "gained", "lost", "one_sided_sign_test")}
        for question in questions]}, indent=1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, function in (("catalogue", catalogue), ("prepare", prepare), ("plan", plan), ("score", score)):
        command = commands.add_parser(name)
        command.set_defaults(function=function)
        if name in ("catalogue", "prepare"):
            command.add_argument("--source", required=True)
        if name != "catalogue":
            command.add_argument("--workspace", required=True)
        if name in ("prepare", "plan"):
            command.add_argument("--part", choices=external.PARTS[:2], required=True)
        if name in ("plan", "score"):
            command.add_argument("--name", required=True)
        if name == "plan":
            command.add_argument("--recombination", default="RECOMBINE1")
        if name in ("prepare", "score"):
            command.add_argument("--workers", type=int, default=4)
    arguments = parser.parse_args()
    arguments.function(arguments)


if __name__ == "__main__":
    main()
