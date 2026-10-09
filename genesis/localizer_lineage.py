"""A fault localizer that is rewritten as code, generation after generation, and judged without a model.

The repair lineages before this one let a model rewrite configuration text and measured the
result with a handful of model-driven repairs: too few cases to tell two variants apart. Here
the thing that changes is executable code of Genesis itself -- the module that turns a failing
test report into suspect locations -- and the judge is arithmetic: do the returned locations
cover the lines the developers changed? That costs no model request, so hundreds of development
cases can be scored for every candidate.

Three disjoint sets of development cases keep the judgement honest. *Training* cases are the only
ones whose misses are shown to the model. *Selection* cases decide whether a successor replaces
its parent. *Validation* cases are not touched until the lineage is frozen. Held-out cases of the
repair bench are not involved at all.

A model-written module is never imported by the host. It runs in a container without network,
with a read-only root and read-only cases; the developer fixes are not mounted there.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
from typing import Callable, Mapping, Sequence

from genesis.repair_lineage import Envelope, Ledger, _send, exact_sign_test
from genesis.trust_root import digest_of

SPLIT_DOMAIN = "genesis-localizer-lineage-v1|"
RESULT_SCHEMA = "genesis-localizer-evaluation-v1"
CALL_SCHEMA = "genesis-localizer-call-v1"
MAX_LOCATIONS = 6
WINDOW = 40
CASE_SECONDS = 10
MAX_SOURCE_CHARACTERS = 60_000
ALLOWED_IMPORTS = frozenset({
    "bisect", "collections", "dataclasses", "difflib", "functools", "heapq", "itertools", "json",
    "math", "os", "pathlib", "re", "string", "typing",
})


class LocalizerError(ValueError):
    """A module, a patch or an evaluation that cannot be used."""


# -- which cases play which role ----------------------------------------------------------------


def role_of(case: str) -> str:
    """Training, selection or validation, fixed by the case name alone."""
    bucket = int(hashlib.sha256((SPLIT_DOMAIN + case).encode()).hexdigest(), 16) % 10
    return "training" if bucket < 3 else "selection" if bucket < 7 else "validation"


# -- what the developers changed ----------------------------------------------------------------

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def edit_sites(patch: str, source_directory: str) -> list[dict]:
    """Where the buggy production sources differ from the fixed ones, as line ranges of the buggy file.

    Defects4J stores each fix as the patch that turns the fixed revision back into the buggy one,
    so the ``+`` side is the buggy file. A line present only in the fix marks the buggy line it
    was inserted before. Marks of one hunk closer than four lines form one site.
    """
    prefix = source_directory.strip("/") + "/"
    sites: list[dict] = []
    path: str | None = None
    position = 0
    marks: list[int] = []

    def flush() -> None:
        nonlocal marks
        if path is not None and marks:
            first = last = marks[0]
            for mark in marks[1:]:
                if mark - last > 3:
                    sites.append({"path": path, "first": first, "last": last})
                    first = mark
                last = mark
            sites.append({"path": path, "first": first, "last": last})
        marks = []

    for line in patch.splitlines():
        if line.startswith("+++ "):
            flush()
            name = line[4:].split("\t")[0].strip()
            name = name[2:] if name.startswith(("a/", "b/")) else name
            path = name if name.startswith(prefix) and name.endswith(".java") else None
            continue
        if line.startswith("--- ") or line.startswith("diff ") or line.startswith("index "):
            continue
        header = _HUNK.match(line)
        if header:
            flush()
            position = int(header.group(1))
            continue
        if path is None or not line or line.startswith("\\"):
            continue
        if line[0] == "+":
            marks.append(position)
            position += 1
        elif line[0] == "-":
            marks.append(max(1, position))
        elif line[0] == " ":
            position += 1
    flush()
    return sites


def clean_locations(value: object) -> list[list]:
    """The first ``MAX_LOCATIONS`` well-formed ``[path, line]`` pairs of what a module returned."""
    kept: list[list] = []
    if not isinstance(value, (list, tuple)):
        return kept
    for item in value:
        if len(kept) == MAX_LOCATIONS:
            break
        if (not isinstance(item, (list, tuple)) or len(item) != 2 or not isinstance(item[0], str)
                or not isinstance(item[1], int) or isinstance(item[1], bool) or item[1] < 1):
            continue
        parts = PurePosixPath(item[0]).parts
        if not parts or PurePosixPath(item[0]).is_absolute() or ".." in parts or len(item[0]) > 400:
            continue
        kept.append([str(PurePosixPath(item[0])), item[1]])
    return kept


def covers(site: Mapping, locations: Sequence[Sequence]) -> bool:
    return any(path == site["path"] and line - WINDOW <= site["first"] and site["last"] <= line + WINDOW
               for path, line in locations)


def score(sites: Sequence[Mapping], locations: Sequence[Sequence]) -> dict:
    """``localized`` is the strict one: every edit site lies inside a returned window."""
    if not sites:
        raise LocalizerError("a case without edit sites cannot be scored")
    hit = [covers(site, locations) for site in sites]
    files = {path for path, _ in locations}
    return {"localized": all(hit), "any_site": any(hit), "all_files": all(site["path"] in files for site in sites)}


def evaluate(outputs: Mapping, truth: Mapping[str, Sequence[Mapping]], cases: Sequence[str]) -> dict:
    """Score one module's container output on ``cases``. A case it did not answer counts as a miss."""
    rows = {}
    for case in cases:
        answer = outputs.get(case) if isinstance(outputs, Mapping) else None
        answer = answer if isinstance(answer, Mapping) else {}
        locations = clean_locations(answer.get("locations"))
        rows[case] = {"locations": locations, "error": str(answer.get("error") or "")[:120] or None,
                      **score(truth[case], locations)}
    body = {"schema": RESULT_SCHEMA, "cases": rows, "case_count": len(rows),
            "localized": sum(row["localized"] for row in rows.values()),
            "any_site": sum(row["any_site"] for row in rows.values()),
            "all_files": sum(row["all_files"] for row in rows.values()),
            "errors": sum(row["error"] is not None for row in rows.values())}
    return {**body, "evaluation_digest": digest_of(body)}


def compare(child: Mapping, parent: Mapping) -> dict:
    """Paired outcome of two evaluations of the same cases."""
    if set(child["cases"]) != set(parent["cases"]):
        raise LocalizerError("the two evaluations do not cover the same cases")
    gained = sorted(name for name, row in child["cases"].items()
                    if row["localized"] and not parent["cases"][name]["localized"])
    lost = sorted(name for name, row in child["cases"].items()
                  if not row["localized"] and parent["cases"][name]["localized"])
    return {"parent": parent["localized"], "child": child["localized"], "case_count": child["case_count"],
            "gained": len(gained), "lost": len(lost), "gained_cases": gained, "lost_cases": lost,
            "one_sided_sign_test": exact_sign_test(len(lost), len(gained))}


def promotes(comparison: Mapping, margin: int = 5, alpha: float = 0.05) -> bool:
    """A successor replaces its parent only on a clear paired gain on the selection cases."""
    return (comparison["gained"] - comparison["lost"] >= margin
            and comparison["one_sided_sign_test"] <= alpha)


# -- a module as data ---------------------------------------------------------------------------


def checked_source(source: str) -> str:
    """Refuse, without executing anything, a module the container should not be given."""
    if not isinstance(source, str) or not source.strip():
        raise LocalizerError("the module is empty")
    if len(source) > MAX_SOURCE_CHARACTERS:
        raise LocalizerError(f"the module is longer than {MAX_SOURCE_CHARACTERS} characters")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise LocalizerError(f"the module does not parse: {error.msg} at line {error.lineno}") from error
    if not any(isinstance(node, ast.FunctionDef) and node.name == "localize" for node in tree.body):
        raise LocalizerError("the module defines no top-level function named localize")
    for node in ast.walk(tree):
        names = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                 else [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
        for name in names:
            if name.split(".")[0] not in ALLOWED_IMPORTS:
                raise LocalizerError(f"import of {name!r} is not allowed; allowed: {sorted(ALLOWED_IMPORTS)}")
    return source


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode()).hexdigest()


_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)\n```", re.DOTALL)


def extract_module(answer: str) -> tuple[str, str]:
    """The longest fenced block of an answer, and the prose around it as the writer's notes."""
    blocks = _FENCE.findall(answer or "")
    if not blocks:
        raise LocalizerError("the answer holds no fenced Python block")
    source = max(blocks, key=len)
    notes = _FENCE.sub("", answer).strip()
    return source + "\n", notes[:1500]


# -- running a module behind the container boundary ---------------------------------------------

DRIVER = '''\
import importlib.util, json, signal, sys, time

class Deadline(BaseException):
    pass

def _alarm(signum, frame):
    raise Deadline()

signal.signal(signal.SIGALRM, _alarm)
names = json.load(open("/candidate/cases.json"))
seconds = int(sys.argv[1])
out = {}
module = None
try:
    signal.alarm(30)
    spec = importlib.util.spec_from_file_location("candidate_localizer", "/candidate/localizer.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
except BaseException as error:
    out["__load_error__"] = type(error).__name__ + ": " + str(error)[:200]
    module = None
finally:
    signal.alarm(0)
for name in names:
    record = {"locations": [], "error": None}
    started = time.monotonic()
    if module is None:
        record["error"] = "module did not load"
    else:
        try:
            case = json.load(open("/cases/" + name + "/case.json"))
            case["root"] = "/cases/" + name + "/tree"
            signal.alarm(seconds)
            answer = module.localize(case)
            signal.alarm(0)
            kept = []
            for item in list(answer)[:50]:
                if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str) \\
                        and isinstance(item[1], int) and not isinstance(item[1], bool):
                    kept.append([item[0], item[1]])
            record["locations"] = kept
        except BaseException as error:
            signal.alarm(0)
            record["error"] = type(error).__name__ + ": " + str(error)[:100]
    record["seconds"] = round(time.monotonic() - started, 3)
    out[name] = record
    json.dump(out, open("/out/result.json.partial", "w"))
import os
os.replace("/out/result.json.partial", "/out/result.json")
'''


def container_command(image: str, cases_directory: Path, run_directory: Path, *, name: str,
                      case_seconds: int = CASE_SECONDS, docker: str = "docker") -> list[str]:
    """The exact ``docker run`` argv. Pure, so the boundary can be tested."""
    return [
        docker, "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--pids-limit", "64", "--memory", "1024m", "--memory-swap", "1024m", "--cpus", "2",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
        "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONHASHSEED=0",
        "--mount", f"type=bind,source={cases_directory},target=/cases,readonly",
        "--mount", f"type=bind,source={run_directory / 'candidate'},target=/candidate,readonly",
        "--mount", f"type=bind,source={run_directory / 'out'},target=/out",
        "--workdir", "/tmp",
        image, "python", "-I", "/candidate/driver.py", str(case_seconds),
    ]


def run_module(source: str, cases: Sequence[str], *, image: str, cases_directory: Path, scratch: Path,
               case_seconds: int = CASE_SECONDS, runner: Callable | None = None) -> dict:
    """Run one module on ``cases`` in a fresh container and return what it wrote, case by case.

    Whatever stops the container before it finishes (a hang, memory) leaves the cases it did not
    reach unanswered: they count as misses.
    """
    checked_source(source)
    run_directory = Path(scratch).resolve() / f"run-{secrets.token_hex(6)}"
    (run_directory / "candidate").mkdir(parents=True)
    (run_directory / "out").mkdir()
    (run_directory / "candidate" / "localizer.py").write_text(source, encoding="utf-8")
    (run_directory / "candidate" / "driver.py").write_text(DRIVER, encoding="utf-8")
    (run_directory / "candidate" / "cases.json").write_text(json.dumps(list(cases)), encoding="utf-8")
    name = f"genesis-localizer-{secrets.token_hex(8)}"
    command = container_command(image, Path(cases_directory).resolve(), run_directory, name=name,
                                case_seconds=case_seconds)
    deadline = 120 + 2 * len(cases)
    try:
        (runner or subprocess.run)(command, capture_output=True, timeout=deadline, check=False)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
    outputs: dict = {}
    for candidate in ("result.json", "result.json.partial"):
        path = run_directory / "out" / candidate
        if path.is_file() and not path.is_symlink() and path.stat().st_size < 50_000_000:
            try:
                loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                outputs = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError:
                outputs = {}
            break
    for path in sorted(run_directory.rglob("*"), reverse=True):
        path.unlink() if path.is_file() or path.is_symlink() else path.rmdir()
    run_directory.rmdir()
    return outputs


# -- what the writer is shown -------------------------------------------------------------------

WRITER_SYSTEM = (
    "You improve a Python module that localizes Java defects. Given the stack traces of failing "
    "tests and read access to the buggy sources, it must return the places where the developers "
    "will have to change production code. You are shown the module, its score, what earlier "
    "attempts tried and how they fared, and cases it missed together with where the fix really "
    "was. Write the whole next version of the module. It is scored on other projects and defects "
    "than the ones you are shown, so only general rules help: a rule that names a project, a "
    "class or a test from the examples is worthless."
)

CONTRACT = f"""## Contract of the module

- One file, Python 3.12, standard library only; allowed imports: {", ".join(sorted(ALLOWED_IMPORTS))}.
- Entry point `localize(case)`; `case` has `root`, `source_directory`, `test_directory`,
  `failing_tests` and `report`, exactly as documented at the top of the current module.
- It may read any file under `case["root"]` (production and test sources of the buggy revision).
  Nothing else exists: no network, no fixed revision, no build output, no test execution.
- It returns `[[path relative to root, line], ...]`, most suspect first. Only the first
  {MAX_LOCATIONS} entries count. A case is *localized* when every place the developers changed lies
  within {WINDOW} lines of one returned entry in the same file. Fixes often touch several places,
  sometimes in several files, and most fixes add lines.
- At most {CASE_SECONDS} seconds per case, deterministic, no state kept between cases. An exception
  or a timeout counts as a miss. At most {MAX_SOURCE_CHARACTERS} characters of source, and the whole
  answer must fit in the output limit: a module of a few hundred lines, not more.

Answer with a short paragraph saying what you changed and why, then the complete module in one
```python fenced block."""


def _excerpt(path: Path, first: int, last: int, limit: int = 2200) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(unreadable)"
    first, last = max(1, first), min(len(lines), last)
    return "\n".join(f"{number:5d}| {lines[number - 1][:160]}" for number in range(first, last + 1))[:limit]


_TEST_FRAME = re.compile(r"^\s+at ([\w.$]+)\.[\w$<>]+\(([\w$]+\.java):(\d+)\)", re.MULTILINE)


def describe_miss(case: str, row: Mapping, sites: Sequence[Mapping], cases_directory: Path) -> str:
    """One missed training case: what the module saw, what it answered, where the fix was."""
    directory = Path(cases_directory) / case
    data = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    root = directory / "tree"
    sections = re.split(r"^--- (\S+)\s*$", data["report"], flags=re.MULTILINE)[1:]
    traces = []
    for index in range(0, min(len(sections) - 1, 4), 2):
        body = [line for line in sections[index + 1].strip().splitlines()
                if "sun.reflect" not in line and "java.lang.reflect" not in line]
        traces.append(f"--- {sections[index]}\n" + "\n".join(line[:200] for line in body[:12]))
    test_source = ""
    for classname, _, line in _TEST_FRAME.findall(data["report"]):
        path = root / data["test_directory"] / (classname.split("$", 1)[0].replace(".", "/") + ".java")
        if path.is_file():
            test_source = (f"Test source {data['test_directory']}/{classname.replace('.', '/')}.java "
                           f"around line {line}:\n" + _excerpt(path, int(line) - 12, int(line) + 3, 1500))
            break
    answered = ", ".join(f"{path}:{line}" for path, line in row["locations"]) or "(nothing)"
    fixes = []
    for site in list(sites)[:3]:
        fixes.append(f"{site['path']} lines {site['first']}-{site['last']}"
                     + (" (covered)" if covers(site, row["locations"]) else " (MISSED)") + "\n"
                     + _excerpt(root / site["path"], site["first"] - 6, site["last"] + 6, 1400))
    more = f"\n(and {len(sites) - 3} more edit sites)" if len(sites) > 3 else ""
    return "\n".join([
        f"### Missed case ({len(data['failing_tests'])} failing test(s), {len(sites)} edit site(s))",
        f"source_directory={data['source_directory']} test_directory={data['test_directory']}",
        "Traces:\n" + "\n".join(traces),
        test_source,
        f"The module answered: {answered}" + (f" [error: {row['error']}]" if row["error"] else ""),
        "Where the developers changed the buggy file:\n" + "\n\n".join(fixes) + more,
    ])


def training_report(evaluation: Mapping, truth: Mapping, cases_directory: Path, *, offset: int = 0,
                    shown: int = 10, limit: int = 60_000) -> str:
    """Score and a rotating sample of misses on the training cases."""
    rows = evaluation["cases"]
    missed = sorted(name for name, row in rows.items() if not row["localized"])
    wrong_file = sum(not rows[name]["all_files"] for name in missed)
    partial = sum(rows[name]["any_site"] for name in missed)
    multi = sum(len(truth[name]) > 1 for name in missed)
    head = (f"Localized {evaluation['localized']} of {evaluation['case_count']} training cases. "
            f"Of the {len(missed)} misses: {wrong_file} lack a file the fix touches, "
            f"{len(missed) - wrong_file} have every file but not the right lines, {partial} cover some "
            f"but not all edit sites, {multi} have more than one edit site, "
            f"{evaluation['errors']} cases ended in an exception or timeout.")
    parts, used = [head], len(head)
    if missed:
        step = max(1, len(missed) // shown)
        chosen = [missed[(offset + index * step) % len(missed)] for index in range(min(shown, len(missed)))]
        for name in dict.fromkeys(chosen):
            text = describe_miss(name, rows[name], truth[name], cases_directory)
            if used + len(text) > limit:
                break
            parts.append(text)
            used += len(text)
    return "\n\n".join(parts)


def archive_report(attempts: Sequence[Mapping], limit: int = 6000) -> str:
    """Memory of the lineage: every earlier attempt, kept or not, with its measured outcome."""
    if not attempts:
        return "No earlier attempt."
    lines = []
    for attempt in attempts:
        outcome = attempt.get("outcome", "unknown")
        selection = attempt.get("selection")
        measured = f"training {attempt.get('training_localized')}/{attempt.get('training_cases')}"
        if selection:
            measured += f", unseen cases +{selection['gained']} -{selection['lost']}"
        lines.append(f"- generation {attempt['generation']}, attempt {attempt['index']}: {outcome} "
                     f"({measured}). Writer's notes: {str(attempt.get('notes', ''))[:500]}")
    text = "\n".join(lines)
    return text if len(text) <= limit else "(oldest entries dropped)\n" + text[-limit:]


def write_successor(parent_source: str, report: str, archive: str, envelope: Envelope, ledger: Ledger, *,
                    transport: Callable | None = None) -> dict:
    """Ask the model for the module after ``parent_source``. One correction is allowed.

    Returns ``{"source", "notes", "calls"}``; ``source`` is ``None`` when both answers were unusable.
    """
    messages = [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": "\n\n".join([
            CONTRACT,
            "## Earlier attempts in this lineage\n\n" + archive,
            "## Current module\n\n```python\n" + parent_source.rstrip("\n") + "\n```",
            "## Its results on the training cases\n\n" + report,
        ])},
    ]
    calls: list[dict] = []
    for _ in (1, 2):
        payload = {"model": envelope.model, "messages": messages, "max_tokens": envelope.max_tokens,
                   "provider": {"allow_fallbacks": True, "sort": "price", "max_price": dict(envelope.max_price)}}
        record: dict = {"schema": CALL_SCHEMA, "purpose": "successor", "prompt_digest": digest_of(messages)}
        raw, cost = _send(payload, envelope, ledger, transport)
        record["cost_usd"] = cost
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        record["tokens"] = {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens")}
        answer = ""
        try:
            choice = raw["choices"][0]
            answer = choice["message"].get("content") or ""
            record["finish_reason"] = choice.get("finish_reason")
            if choice.get("finish_reason") == "length":
                raise LocalizerError("the answer was cut off before the module ended; write a shorter module")
            source, notes = extract_module(answer)
            checked_source(source)
            if source_digest(source) == source_digest(parent_source):
                raise LocalizerError("the module is identical to the current one")
            record["source_digest"] = source_digest(source)
            calls.append(record)
            return {"source": source, "notes": notes, "calls": calls}
        except (LocalizerError, KeyError, TypeError, IndexError) as error:
            problem = f"{type(error).__name__}: {error}"[:300]
        record["rejected"] = problem
        calls.append(record)
        messages.append({"role": "assistant", "content": answer[:20_000] or "(no content)"})
        messages.append({"role": "user", "content": f"That answer was refused: {problem}. Send the complete "
                         "module again, corrected, in one ```python block."})
    return {"source": None, "notes": "", "calls": calls}
