"""A blind repair bench: frozen split, line-level localisation, bounded validation.

The bench exists so that a change to the repair machinery can be scored on bugs nobody involved
has looked at. It fixes three things that the earlier studies left open:

* the split between development and held-out cases is derived from a hash and frozen in a file;
* a case's evidence is what a run of its own tests on the buggy revision shows, nothing else;
* every candidate, whatever produced it, is validated the same way behind the container boundary.

Nothing here generates a repair. Proposers are passed in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import difflib
import hashlib
from pathlib import Path
import re
from typing import Callable, Mapping, Sequence

from genesis.defects4j_sandbox import Defects4JSandbox
from genesis.trust_root import digest_of

SPLIT_SCHEMA = "genesis-repair-bench-split-v1"
EVIDENCE_SCHEMA = "genesis-repair-bench-evidence-v1"
VERDICT_SCHEMA = "genesis-repair-bench-verdict-v1"
SPLIT_DOMAIN = "genesis-repair-bench-v1|"
HELD_OUT_ONE_IN = 5

# Cases a recorded study, an audit or a smoke test has already opened. They can never be blind.
EXPOSED: frozenset[tuple[str, int]] = frozenset({
    ("Codec", 15), ("Compress", 6), ("Math", 53), ("Csv", 16), ("Collections", 24), ("Gson", 2),
    ("Jsoup", 68), ("JacksonCore", 11), ("Cli", 34), ("Time", 22), ("JxPath", 12), ("Chart", 23),
    ("JacksonXml", 4), ("Mockito", 22), ("Closure", 10), ("Time", 4),
})
# Lang was the ER1 working set: twelve selected cases plus an unattended campaign over others.
EXPOSED_PROJECTS: frozenset[str] = frozenset({"Lang"})

_FRAME = re.compile(r"^\s+at ([\w.$]+)\.[\w$<>]+\(([\w$]+\.java):(\d+)\)", re.MULTILINE)
_HEADER = re.compile(r"^--- (\S+)\s*$", re.MULTILINE)


class RepairBenchError(RuntimeError):
    """Raised when the bench cannot give a case a fair, identical treatment."""


def squashed_sha256(text: str) -> str:
    """Digest of a source text with all whitespace removed, to compare two versions of a file."""
    return hashlib.sha256(re.sub(r"\s+", "", text).encode()).hexdigest()


def case_name(project: str, bug_id: int) -> str:
    return f"{project}-{bug_id}"


def _order_key(project: str, bug_id: int) -> str:
    return hashlib.sha256(f"{SPLIT_DOMAIN}{case_name(project, bug_id)}".encode()).hexdigest()


def build_split(active: Sequence[tuple[str, int]]) -> dict:
    """Assign every active case to ``development`` or ``held_out`` by hash, exposed cases aside.

    Held-out cases are listed in hash order. Trials consume that list from the front, so which
    cases a trial gets is decided here, before anyone knows what the trial will be.
    """
    held_out, development = [], []
    for project, bug_id in sorted(set(active)):
        key = _order_key(project, bug_id)
        exposed = project in EXPOSED_PROJECTS or (project, bug_id) in EXPOSED
        if not exposed and int(key, 16) % HELD_OUT_ONE_IN == 0:
            held_out.append((key, case_name(project, bug_id)))
        else:
            development.append((key, case_name(project, bug_id)))
    body = {
        "schema": SPLIT_SCHEMA,
        "domain": SPLIT_DOMAIN,
        "rule": f"held out when sha256(domain + case) mod {HELD_OUT_ONE_IN} == 0 and the case was never exposed",
        "exposed_projects": sorted(EXPOSED_PROJECTS),
        "exposed_cases": sorted(case_name(*case) for case in EXPOSED),
        "held_out": [name for _, name in sorted(held_out)],
        "development": [name for _, name in sorted(development)],
    }
    return {**body, "split_digest": digest_of(body)}


def next_held_out(split: Mapping, consumed: Sequence[str], count: int) -> list[str]:
    """The next ``count`` held-out cases no trial has used. Order is the split's, never chosen."""
    spent = set(consumed)
    unknown = spent - set(split["held_out"])
    if unknown:
        raise RepairBenchError(f"consumed cases are not held-out cases: {sorted(unknown)}")
    remaining = [name for name in split["held_out"] if name not in spent]
    if len(remaining) < count:
        raise RepairBenchError(f"only {len(remaining)} held-out cases remain, {count} requested")
    return remaining[:count]


# -- evidence ---------------------------------------------------------------------------------


def _window(lines: Sequence[str], centre: int, radius: int) -> tuple[int, int]:
    return max(1, centre - radius), min(len(lines), centre + radius)


def _numbered(lines: Sequence[str], first: int, last: int) -> str:
    return "\n".join(f"{number:5d}| {lines[number - 1]}" for number in range(first, last + 1))


def _excerpts(root: Path, locations: Sequence[tuple[str, int]], radius: int, budget: int) -> list[dict]:
    """Numbered source windows around ``locations``, overlapping windows of one file merged."""
    by_path: dict[str, list[tuple[int, int]]] = {}
    for path, line in locations:
        text = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
        first, last = _window(text, line, radius)
        spans = by_path.setdefault(path, [])
        for index, (a, b) in enumerate(spans):
            if first <= b + 1 and a <= last + 1:
                spans[index] = (min(a, first), max(b, last))
                break
        else:
            spans.append((first, last))
    excerpts, used = [], 0
    for path, spans in by_path.items():
        text = (root / path).read_text(encoding="utf-8", errors="replace").splitlines()
        for first, last in sorted(spans):
            body = _numbered(text, first, last)
            if used + len(body) > budget:
                return excerpts
            used += len(body)
            excerpts.append({"path": path, "first_line": first, "last_line": last, "numbered_source": body})
    return excerpts


def collect_evidence(
    sandbox: Defects4JSandbox, directory: str, *, max_locations: int = 6, radius: int = 40,
    source_budget: int = 48_000, localize_assertions: bool = False, separate_environment: bool = False,
) -> dict:
    """What the buggy revision's own failing tests show: names, traces, and the code they reach.

    Runs the relevant tests in the container, then reads ``failing_tests``. Production frames of the
    stack traces give line-level suspects; test frames give the failing test's own source. The
    fixed revision is never consulted.

    With ``separate_environment`` the failing tests are narrowed to the ones Defects4J declares as
    triggering the defect, and the whole suite is run once on the unmodified buggy revision. Tests
    that fail there without being triggers fail because of where they run (no network, no home
    directory), not because of the defect: they are recorded as ``tolerated_failures`` and a
    candidate is not blamed for them.
    """
    source_dir = sandbox.export(directory, "dir.src.classes").output.strip()
    test_dir = sandbox.export(directory, "dir.src.tests").output.strip()
    if not source_dir or not test_dir:
        raise RepairBenchError(f"{directory}: Defects4J did not report its source directories")
    if not sandbox.compile(directory).ok:
        raise RepairBenchError(f"{directory}: the unmodified buggy revision does not compile")
    tested = sandbox.test(directory, relevant_only=True)
    if not tested.ok:
        raise RepairBenchError(f"{directory}: the relevant tests did not run")
    failing = sandbox.failing_tests(directory)
    if not failing:
        raise RepairBenchError(f"{directory}: the buggy revision fails no relevant test")
    root = sandbox.workspace / directory
    report = (root / "failing_tests").read_text(encoding="utf-8", errors="replace")[:400_000]
    environment: dict = {}
    if separate_environment:
        triggers = set(sandbox.export(directory, "tests.trigger").output.split())
        kept = [name for name in failing if name in triggers]
        if not kept:
            raise RepairBenchError(f"{directory}: none of the declared trigger tests fails here")
        pieces = _HEADER.split(report)
        report = "".join(
            f"--- {pieces[index]}\n{pieces[index + 1]}" for index in range(1, len(pieces) - 1, 2)
            if pieces[index] in triggers)
        whole = sandbox.test(directory)
        if not whole.ok:
            raise RepairBenchError(f"{directory}: the full suite did not run on the buggy revision")
        baseline = sandbox.failing_tests(directory)
        environment = {
            "trigger_tests": sorted(triggers),
            "tolerated_failures": sorted((set(baseline) | set(failing)) - triggers),
        }
        failing = kept

    def resolve(classname: str, base: str) -> str | None:
        path = f"{base}/{classname.split('$', 1)[0].replace('.', '/')}.java"
        return path if (root / path).is_file() else None

    production: list[tuple[str, int]] = []
    tests: list[tuple[str, int]] = []
    for classname, _, line in _FRAME.findall(report):
        for base, bucket in ((source_dir, production), (test_dir, tests)):
            path = resolve(classname, base)
            if path is not None and (path, int(line)) not in bucket:
                bucket.append((path, int(line)))
    # A trace that never enters production code (an assertion in the test) still names the test;
    # fall back to the class the test is named after, from its first line.
    fallback = False
    if not production:
        fallback = True
        for name in failing:
            guess = resolve(re.sub(r"Tests?$", "", name.split("::")[0]), source_dir)
            if guess is not None and (guess, 1) not in production:
                production.append((guess, 1))
    sections = _HEADER.split(report)[1:]
    traces = [
        {"test": sections[index], "trace": "\n".join(sections[index + 1].strip().splitlines()[:25])}
        for index in range(0, len(sections) - 1, 2)
    ][:4]
    body = {
        "schema": EVIDENCE_SCHEMA,
        "source_directory": source_dir,
        "test_directory": test_dir,
        "failing_tests": failing,
        "traces": traces,
        "suspect_locations": [list(item) for item in production[:max_locations]],
        "suspects_from_stack_trace": not fallback,
        "test_source": _excerpts(root, tests[:2], 25, 12_000),
        "production_source": _excerpts(
            root, production[:max_locations], 200 if fallback else radius, source_budget),
        "fixed_revision_consulted": False,
        **environment,
    }
    evidence = {**body, "evidence_digest": digest_of(body)}
    if localize_assertions:
        from genesis.repair_source_localization import enrich
        return enrich(root, evidence)
    return evidence


# -- candidates and validation ----------------------------------------------------------------


@dataclass(frozen=True)
class Candidate:
    """One proposed repair: the complete new text of one source file."""

    path: str
    content: str
    origin: str
    description: str = ""
    provenance: dict | None = field(default=None, compare=False, hash=False)

    @property
    def digest(self) -> str:
        return digest_of({"path": self.path, "content": self.content})


def apply_edits(
    root: Path, path: str, edits: Sequence[tuple[str, str]], origin: str, description: str = "",
) -> Candidate | None:
    """Turn exact-text edits of one file into a candidate, or ``None`` when one does not apply.

    Each ``search`` text must occur exactly once in the file as it stands when its edit is applied.
    A proposal that cannot be located unambiguously is dropped rather than guessed at.
    """
    if not path or Path(path).is_absolute() or ".." in Path(path).parts or not edits:
        return None
    target = root / path
    if not target.is_file() or target.is_symlink():
        return None
    original = text = target.read_text(encoding="utf-8", errors="replace")
    for search, replace in edits:
        if not search or search == replace or text.count(search) != 1:
            return None
        text = text.replace(search, replace)
    if text == original:
        return None
    return Candidate(path=path, content=text, origin=origin, description=description)


def validate(
    sandbox: Defects4JSandbox, directory: str, candidate: Candidate, failing: Sequence[str],
    tolerated: Sequence[str] = (),
) -> dict:
    """Compile the candidate, run the tests that failed, then the whole suite. Restores the file.

    ``plausible`` means the full developer test suite passes. It does not mean the repair is
    correct: a patch can satisfy the tests and still be wrong. Tests named in ``tolerated`` already
    failed on the unmodified revision for reasons of environment and are not held against it.
    """
    target = sandbox.workspace / directory / candidate.path
    original = target.read_bytes()
    stage, remaining, detail = "compile", None, None
    try:
        target.write_text(candidate.content, encoding="utf-8")
        compiled = sandbox.compile(directory)
        if not compiled.ok:
            detail = "\n".join(
                line for line in compiled.output.splitlines() if "error:" in line or "[javac]" in line
            )[:1500]
        if compiled.ok:
            stage = "failing_tests"
            still_failing = False
            for test in list(failing)[:5]:
                run = sandbox.test(directory, single_test=test)
                if not run.ok or sandbox.failing_tests(directory):
                    still_failing = True
                    report = sandbox.workspace / directory / "failing_tests"
                    if run.ok and report.is_file() and not report.is_symlink():
                        lines = report.read_text(encoding="utf-8", errors="replace").splitlines()[:12]
                        detail = "\n".join(lines)[:1500]
                    break
            if not still_failing:
                stage = "full_suite"
                run = sandbox.test(directory)
                if run.ok:
                    remaining = [name for name in sandbox.failing_tests(directory) if name not in set(tolerated)]
                    if not remaining:
                        stage = "passed"
                    else:
                        detail = "now failing: " + ", ".join(remaining[:8])
    finally:
        target.write_bytes(original)
    body = {
        "schema": VERDICT_SCHEMA,
        "candidate_digest": candidate.digest,
        "origin": candidate.origin,
        "path": candidate.path,
        "stopped_at": stage,
        "plausible": stage == "passed",
        "full_suite_failures": None if remaining is None else len(remaining),
        "feedback": detail,
    }
    return {**body, "verdict_digest": digest_of(body)}


History = Sequence[tuple[Candidate, Mapping]]
Proposer = Callable[[Path, Mapping, History, int], Sequence[Candidate]]


def run_arm(
    sandbox: Defects4JSandbox, directory: str, evidence: Mapping, proposer: Proposer, budget: int,
    *, max_rounds: int = 4,
) -> dict:
    """Give one proposer one case: at most ``budget`` distinct candidates, each validated.

    The proposer is called in rounds. Each round it sees every earlier candidate with its verdict
    and how many validations remain, and may use that or ignore it. The arm stops at the first
    candidate that passes the full suite, when the budget is spent, when a round brings nothing
    new, or after ``max_rounds``. All arms get the same budget; only the proposer differs.
    """
    root = sandbox.workspace / directory
    history: list[tuple[Candidate, dict]] = []
    seen: set[str] = set()
    proposed = rounds = 0
    while len(history) < budget and rounds < max_rounds:
        rounds += 1
        batch = list(proposer(root, evidence, tuple(history), budget - len(history)))
        proposed += len(batch)
        fresh = []
        for candidate in batch:
            if candidate.digest not in seen:
                seen.add(candidate.digest)
                fresh.append(candidate)
        if not fresh:
            break
        solved = False
        for candidate in fresh[:budget - len(history)]:
            verdict = validate(sandbox, directory, candidate, evidence["failing_tests"],
                               evidence.get("tolerated_failures", ()))
            history.append((candidate, verdict))
            if verdict["plausible"]:
                solved = True
                break
        if solved:
            break
    verdicts = [verdict for _, verdict in history]
    patch = squashed = None
    for candidate, verdict in history:
        if verdict["plausible"]:
            squashed = squashed_sha256(candidate.content)
            before = (root / candidate.path).read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
            after = candidate.content.splitlines(keepends=True)
            patch = "".join(difflib.unified_diff(before, after, f"a/{candidate.path}", f"b/{candidate.path}"))
    return {
        "rounds": rounds,
        "plausible_patch": patch,
        "plausible_path": next((c.path for c, v in history if v["plausible"]), None),
        "plausible_squashed_sha256": squashed,
        "proposed": proposed,
        "validated": len(verdicts),
        "verdicts": verdicts,
        "solved": any(verdict["plausible"] for verdict in verdicts),
        "first_plausible_rank": next((i for i, v in enumerate(verdicts, 1) if v["plausible"]), None),
    }
