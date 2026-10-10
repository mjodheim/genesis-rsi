"""Improve a function of a working program, again and again, and accept nothing on a model's word.

Repair starts from a failing test. Improvement starts from a program that works, so there is no
failure to remove and the question becomes what "better" means and who says so. Here a case is
one top-level function of an existing Python library, and three things are decided before any
model is asked:

* the *behaviour to keep* is what the original function does on calls recorded while the
  library's own tests ran: what it returns or raises, and what it leaves in its arguments;
* the *cost* is the number of instructions executed while replaying recorded calls, counted by
  Callgrind between two markers. It is a count, not a duration, so a gain of a few per cent can
  be told from noise;
* some recorded calls are *shown* to the writer and the rest are *hidden*. Cost is measured on
  hidden calls only, and behaviour is compared on all of them.

A rewritten function replaces the current one only if it behaves identically on every recorded
call, breaks no test that passed before, and costs clearly less on the hidden calls. The next
rewrite then starts from it: a chain. Calls are distinct, so remembering answers between calls
buys nothing.

Library code and model-written functions run only in a container without network. The host
parses source text and reads JSON; it never imports or unpickles what the container handled.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from typing import Callable, Mapping, Sequence

from genesis.repair_lineage import Envelope, Ledger, _send, exact_sign_test
from genesis.trust_root import digest_of

SPLIT_DOMAIN = "genesis-program-improvement-v1|"
CALL_SCHEMA = "genesis-program-improvement-call-v1"
IMAGE = "genesis-improve:v1"
HARNESS = Path(__file__).with_name("improvement_harness.py")
MAX_CANDIDATE_CHARACTERS = 12_000
SHOWN_CALLS = 8
MEASURED_CALLS = 150
MIN_USABLE_CALLS = 20
MIN_HIDDEN_CALLS = 12
MIN_RETURNED_SHARE = 0.6
MIN_INSTRUCTIONS = 300_000
MAX_REPEAT_SPREAD = 0.003
MAX_REPLAY_SECONDS = 1.0
CALL_SECONDS = 2
REQUIRED_GAIN = 0.03
FORBIDDEN_TEXT = ("ctypes", "genesis", "callgrind", "valgrind")
FORBIDDEN_ATTRIBUTES = ("__new__", "__dict__", "__wrapped__", "__code__", "__globals__")
MAX_NATIVE_RATIO = 1.05
MAX_PEAK_RATIO = 1.2
PEAK_ALLOWANCE = 65_536
NATIVE_REPEATS = 5


class ImprovementError(ValueError):
    """A candidate, a case or a measurement that cannot be used."""


def role_of(case: str) -> str:
    """Pilot cases are used while the apparatus is built; trial cases are not touched before a plan."""
    return "pilot" if int(hashlib.sha256((SPLIT_DOMAIN + case).encode()).hexdigest(), 16) % 4 == 0 else "trial"


def order_key(case: str) -> str:
    return hashlib.sha256((SPLIT_DOMAIN + "order|" + case).encode()).hexdigest()


def text_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# -- a function inside a file -------------------------------------------------------------------


def function_span(source: str, name: str) -> tuple[int, int]:
    """First and last line (1-based, decorators included) of the top-level function ``name``."""
    spans = [(min([node.lineno] + [item.lineno for item in node.decorator_list]), node.end_lineno)
             for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(spans) != 1:
        raise ImprovementError(f"{len(spans)} top-level functions named {name}")
    return spans[0]


def function_text(source: str, name: str) -> str:
    first, last = function_span(source, name)
    return "\n".join(source.splitlines()[first - 1:last]) + "\n"


def _top_level_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        else:
            names.update(item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store))
    return names


def _interface(node: ast.FunctionDef) -> str:
    return "|".join([
        ast.dump(node.args), ast.dump(node.returns) if node.returns else "",
        *(ast.dump(item) for item in node.decorator_list)])


def private_uses(node: ast.AST) -> set[str]:
    """Private attributes read or written in ``node``: ``x._name``, and the dunders that bypass an object."""
    return {item.attr for item in ast.walk(node) if isinstance(item, ast.Attribute)
            and ((item.attr.startswith("_") and not item.attr.startswith("__")) or item.attr in FORBIDDEN_ATTRIBUTES)}


def checked_private(candidate: str, source: str, name: str, package: str) -> None:
    """Refuse a rewrite that reaches into internals the original function did not touch."""
    tree = ast.parse(candidate)
    original_tree = ast.parse(source)
    original = next(node for node in original_tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    added = sorted(private_uses(tree) - private_uses(original))
    if added:
        raise ImprovementError(f"the rewrite reaches a private attribute the original does not use ({added[0]}); "
                               "stay on the public interface of the objects involved")
    known = _top_level_names(original_tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level and (node.module or "").split(".")[0] != package.split(".")[0]:
            for alias in node.names:
                if alias.name.startswith("_") and (alias.asname or alias.name) not in known:
                    raise ImprovementError(f"import of the private name {alias.name!r} from {node.module} is not allowed")


def checked_candidate(candidate: str, source: str, name: str, package: str) -> str:
    """Refuse, without executing anything, a rewrite that is not one function with the same interface.

    Besides the function, a rewrite may bring imports of standard-library or same-package modules
    and assignments to new private module-level names, for values computed once at import.
    """
    if not isinstance(candidate, str) or not candidate.strip():
        raise ImprovementError("the answer holds no function")
    if len(candidate) > MAX_CANDIDATE_CHARACTERS:
        raise ImprovementError(f"the rewrite is longer than {MAX_CANDIDATE_CHARACTERS} characters")
    lowered = candidate.lower()
    for word in FORBIDDEN_TEXT:
        if word in lowered:
            raise ImprovementError(f"the rewrite mentions {word!r}, which is not allowed")
    try:
        tree = ast.parse(candidate)
    except SyntaxError as error:
        raise ImprovementError(f"the rewrite does not parse: {error.msg} at line {error.lineno}") from error
    original_tree = ast.parse(source)
    original = next(node for node in original_tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    taken = _top_level_names(original_tree)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or functions[0].name != name:
        raise ImprovementError(f"the rewrite must define exactly one top-level function, named {name}")
    if tree.body[-1] is not functions[0]:
        raise ImprovementError("nothing may follow the function")
    for node in tree.body[:-1]:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id.startswith("_") and node.targets[0].id not in taken):
            continue
        raise ImprovementError("before the function only imports and assignments to new private names "
                               "(starting with an underscore) are allowed")
    if _interface(functions[0]) != _interface(original):
        raise ImprovementError("the signature, defaults, annotations and decorators must stay exactly as they are")
    declared = {type(node).__name__ for node in ast.walk(original) if isinstance(node, (ast.Global, ast.Nonlocal))}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Global, ast.Nonlocal)) and type(node).__name__ not in declared:
            raise ImprovementError("the rewrite may not keep state between calls (global/nonlocal)")
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
            raise ImprovementError("the rewrite may not be asynchronous")
        modules = ([alias.name for alias in node.names] if isinstance(node, ast.Import)
                   else [] if isinstance(node, ast.ImportFrom) and node.level
                   else [node.module or package] if isinstance(node, ast.ImportFrom) else [])
        for module in modules:
            head = module.split(".")[0]
            if head != package.split(".")[0] and head not in sys.stdlib_module_names:
                raise ImprovementError(f"import of {module!r} is not allowed: standard library or {package} only")
    return candidate.strip("\n") + "\n"


def patched(source: str, name: str, candidate: str) -> str:
    """``source`` with the top-level function ``name`` replaced by ``candidate``."""
    first, last = function_span(source, name)
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    text = "".join(lines[:first - 1]) + candidate + "".join(lines[last:])
    try:
        compile(text, "<patched>", "exec", dont_inherit=True, flags=ast.PyCF_ONLY_AST)
    except SyntaxError as error:
        raise ImprovementError(f"the file no longer parses with the rewrite: {error.msg}") from error
    return text


def prelude_names(text: str) -> set[str]:
    """Module-level names a version brings with it, before its function."""
    return {node.targets[0].id for node in ast.parse(text).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)}


def loaded_names(text: str) -> set[str]:
    return {node.id for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}


_FENCE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)\n```", re.DOTALL)


def extract_candidate(answer: str) -> tuple[str, str]:
    """The longest fenced block of an answer and the prose around it."""
    blocks = _FENCE.findall(answer or "")
    if not blocks:
        raise ImprovementError("the answer holds no fenced Python block")
    return max(blocks, key=len) + "\n", _FENCE.sub("", answer).strip()[:600]


# -- the container boundary ---------------------------------------------------------------------


def container_command(image: str, tree: Path, run_directory: Path, arguments: Sequence[str], *, name: str,
                      overlay: tuple[Path, str] | None = None, environment: Mapping[str, str] | None = None,
                      counted: bool = False, docker: str = "docker") -> list[str]:
    """The exact ``docker run`` argv. Pure, so the boundary can be tested.

    ``overlay`` puts one file over its original inside the read-only library tree.
    """
    command = [
        docker, "run", "--rm", "--name", name,
        "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "128", "--memory", "2048m", "--memory-swap", "2048m", "--cpus", "1",
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m",
        "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1", "--env", "PYTHONHASHSEED=0",
        "--env", "GENESIS_TREE=/tree", "--env", "GENESIS_OUT=/out", "--env", "TZ=UTC", "--env", "LC_ALL=C.UTF-8",
    ]
    for key, value in sorted((environment or {}).items()):
        command += ["--env", f"{key}={value}"]
    command += ["--mount", f"type=bind,source={tree},target=/tree,readonly"]
    if overlay is not None:
        command += ["--mount", f"type=bind,source={overlay[0]},target=/tree/{overlay[1]},readonly"]
    command += [
        "--mount", f"type=bind,source={run_directory / 'harness'},target=/harness,readonly",
        "--mount", f"type=bind,source={run_directory / 'out'},target=/out",
        "--workdir", "/tmp", image,
    ]
    if counted:
        command += ["valgrind", "--tool=callgrind", "--instr-atstart=no", "--collect-atstart=no",
                    "--callgrind-out-file=/out/callgrind.out"]
    return command + ["python", "-I", "/harness/improvement_harness.py", *arguments]


def _read_json(path: Path, limit: int = 80_000_000):
    if path.is_file() and not path.is_symlink() and path.stat().st_size < limit:
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None
    return None


def _remove(directory: Path) -> None:
    for path in sorted(directory.rglob("*"), reverse=True):
        path.unlink() if path.is_file() or path.is_symlink() else path.rmdir()
    directory.rmdir()


def run_harness(mode: str, spec: Mapping, *, tree: Path, scratch: Path, calls: Sequence[str] | None = None,
                overlay_text: str | None = None, overlay_path: str | None = None,
                environment: Mapping[str, str] | None = None, timeout: int = 300, keep: Path | None = None,
                image: str = IMAGE, runner: Callable | None = None) -> dict:
    """One container run of the harness. Returns what it wrote, or ``{}`` if it did not finish."""
    run_directory = Path(scratch).resolve() / f"run-{secrets.token_hex(6)}"
    (run_directory / "harness").mkdir(parents=True)
    (run_directory / "out").mkdir()
    (run_directory / "harness" / "improvement_harness.py").write_bytes(HARNESS.read_bytes())
    body = {**spec, "calls": "/harness/calls.json", "out": "/out/result.json"}
    (run_directory / "harness" / "spec.json").write_text(json.dumps(body), encoding="utf-8")
    (run_directory / "harness" / "calls.json").write_text(json.dumps(list(calls or [])), encoding="utf-8")
    overlay = None
    if overlay_text is not None:
        (run_directory / "harness" / "overlay.py").write_text(overlay_text, encoding="utf-8")
        overlay = (run_directory / "harness" / "overlay.py", str(overlay_path))
    name = f"genesis-improve-{secrets.token_hex(8)}"
    command = container_command(image, Path(tree).resolve(), run_directory, [mode, "/harness/spec.json"],
                                name=name, overlay=overlay, environment=environment, counted=mode == "measure")
    try:
        (runner or subprocess.run)(command, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "kill", name], capture_output=True, check=False)
    out = run_directory / "out"
    result = _read_json(out / "result.json") or {}
    result = result if isinstance(result, dict) else {}
    if mode == "measure":
        text = (out / "callgrind.out").read_text(errors="replace") if (out / "callgrind.out").is_file() else ""
        found = re.search(r"^totals: (\d+)\s*$", text, re.MULTILINE)
        result["instructions"] = int(found.group(1)) if found and result.get("calls") is not None else None
    if mode == "pytest":
        reports = _read_json(out / "tests.json")
        result["tests"] = reports if isinstance(reports, list) else None
    if keep is not None and (out / "targets").is_dir():
        keep.mkdir(parents=True, exist_ok=True)
        for path in (out / "targets").iterdir():
            if path.is_file() and not path.is_symlink() and path.stat().st_size < 4_000_000:
                (keep / path.name).write_bytes(path.read_bytes())
    _remove(run_directory)
    return result


# -- a case: one function, its recorded calls, what the original does with them ------------------


def split_calls(digests: Sequence[str]) -> tuple[list[int], list[int], list[int]]:
    """Indexes of shown, hidden and measured calls. Shown calls are the only ones a writer sees."""
    ranked = sorted(range(len(digests)), key=lambda index: hashlib.sha256(
        (SPLIT_DOMAIN + "shown|" + digests[index]).encode()).hexdigest())
    shown = sorted(ranked[:SHOWN_CALLS])
    hidden = sorted(ranked[SHOWN_CALLS:])
    return shown, hidden, hidden[:MEASURED_CALLS]


def passed_tests(reports: Sequence | None) -> set[str]:
    """Tests whose call phase passed and that reported no failure in any phase."""
    if not isinstance(reports, list):
        return set()
    bad = {row[0] for row in reports if isinstance(row, list) and len(row) == 3 and row[2] == "failed"}
    return {row[0] for row in reports if isinstance(row, list) and len(row) == 3
            and row[1] == "call" and row[2] == "passed" and row[0] not in bad}


class Case:
    """A prepared case on disk: ``case.json`` and the recorded calls, base64 text the host never decodes."""

    def __init__(self, directory: Path, packages: Path):
        self.directory = Path(directory)
        self.data = json.loads((self.directory / "case.json").read_text(encoding="utf-8"))
        self.calls = json.loads((self.directory / "calls.json").read_text(encoding="utf-8"))
        self.tree = Path(packages) / self.data["package"]
        self.file = self.data["file"]
        self.name = self.data["name"]
        self.source = (self.tree / self.file).read_text(encoding="utf-8")
        if text_digest(self.source) != self.data["file_sha256"]:
            raise ImprovementError(f"{self.data['case']}: the library file changed since the case was prepared")

    def spec(self, **extra) -> dict:
        root = self.data["import_root"]
        return {"module": self.data["module"], "name": self.name,
                "path": ["/harness", "/tree/" + root if root else "/tree", "/tree"],
                "seconds": CALL_SECONDS, **extra}

    def select(self, indexes: Sequence[int]) -> list[str]:
        return [self.calls[index] for index in indexes]

    def variants(self, scratch: Path, *, runner: Callable | None = None) -> dict:
        """What the original does on generated variants of its recorded calls, kept when two runs agree."""
        if getattr(self, "_variants", None) is None:
            runs = [variant_rows(self, None, scratch, runner=runner) for _ in (1, 2)]
            self._variants = stable_variants(*runs)
        return self._variants


def variant_rows(case: Case, file_text: str | None, scratch: Path, *, runner: Callable | None = None) -> list[dict]:
    result = run_harness("variants", case.spec(), tree=case.tree, scratch=scratch, calls=case.calls,
                         overlay_text=file_text, overlay_path=case.file, timeout=400, runner=runner)
    rows = result.get("variants")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def stable_variants(first: Sequence[Mapping], second: Sequence[Mapping]) -> dict:
    """Variants on which the original returns or raises the same thing twice, by key."""
    again = {row.get("key"): row for row in second}
    return {row["key"]: dict(row) for row in first
            if row.get("kind") in ("returned", "raised") and again.get(row.get("key"), {}).get("digest") == row.get("digest")}


def variant_differences(reference: Mapping[str, Mapping], rows: Sequence[Mapping]) -> list[dict]:
    """Variants a rewrite treats differently: another value, another state left behind, another exception type."""
    got = {row.get("key"): row for row in rows}
    different = []
    for key, expected in reference.items():
        row = got.get(key) or {}
        same = (row.get("kind") == expected["kind"]
                and (row.get("error") == expected["error"] if expected["kind"] == "raised"
                     else row.get("digest") == expected["digest"]))
        if not same:
            different.append({"label": expected.get("label", ""), "call": expected.get("call", ""),
                              "expected": f"{expected['kind']} {expected.get('preview', '')}",
                              "got": f"{row.get('kind', 'nothing')} {row.get('preview', '')}"})
    return different


def native_cost(case: Case, file_text: str | None, scratch: Path, *, runner: Callable | None = None) -> dict:
    result = run_harness("native", case.spec(total_seconds=120, repeats=NATIVE_REPEATS), tree=case.tree,
                         scratch=scratch, calls=case.select(case.data["measured"]), overlay_text=file_text,
                         overlay_path=case.file, timeout=300, runner=runner)
    return result if isinstance(result.get("processor"), float) and isinstance(result.get("peak_bytes"), int) else {}


def native_verdict(case: Case, file_text: str, champion_text: str | None, scratch: Path, *,
                   runner: Callable | None = None) -> dict:
    """Compare a rewrite with the version it would replace, uninstrumented, in alternating runs."""
    old, new = [], []
    for _ in (1, 2):
        old.append(native_cost(case, champion_text, scratch, runner=runner))
        new.append(native_cost(case, file_text, scratch, runner=runner))
    if not all(old) or not all(new):
        return {}
    best = lambda rows, key: min(row[key] for row in rows)
    return {"processor_ratio": round(best(new, "processor") / max(best(old, "processor"), 1e-9), 4),
            "wall_ratio": round(best(new, "wall") / max(best(old, "wall"), 1e-9), 4),
            "peak_bytes": best(new, "peak_bytes"), "champion_peak_bytes": best(old, "peak_bytes"),
            "processor_seconds": round(best(new, "processor"), 9)}


def measure(case: Case, file_text: str | None, scratch: Path, *, runs: int = 2, runner: Callable | None = None) -> list[int]:
    """Instruction counts of the measured calls, one per run; empty if a run did not finish."""
    counts = []
    for _ in range(runs):
        result = run_harness("measure", case.spec(total_seconds=120), tree=case.tree, scratch=scratch,
                             calls=case.select(case.data["measured"]), overlay_text=file_text,
                             overlay_path=case.file, timeout=400, runner=runner)
        if result.get("instructions") is None or result.get("calls") != len(case.data["measured"]):
            return []
        counts.append(result["instructions"])
    return counts


def judge(case: Case, candidate: str, champion_instructions: int, scratch: Path, *,
          runner: Callable | None = None, strict: bool = False, champion: str | None = None) -> dict:
    """Decide one rewrite. Every refusal names the first check that failed.

    ``strict`` adds what the recorded calls cannot show: generated variants of those calls on
    which the rewrite must still agree with the original, and an uninstrumented comparison with
    ``champion``, the version it would replace, on processor time and peak allocation.
    """
    verdict: dict = {"accepted": False, "candidate_sha256": text_digest(candidate)}
    try:
        file_text = patched(case.source, case.name, candidate)
    except ImprovementError as error:
        return {**verdict, "reason": "unusable", "detail": str(error)}
    replay = run_harness("outcomes", case.spec(), tree=case.tree, scratch=scratch, calls=case.calls,
                         overlay_text=file_text, overlay_path=case.file, runner=runner)
    outcomes = replay.get("outcomes")
    expected = case.data["outcomes"]
    if not isinstance(outcomes, list) or len(outcomes) != len(expected):
        return {**verdict, "reason": "did not finish", "detail": "the replay of the recorded calls did not complete"}
    different = [index for index, row in enumerate(outcomes)
                 if not isinstance(row, dict) or row.get("digest") != expected[index]["digest"]]
    if different:
        shown = [index for index in different if index in set(case.data["shown"])]
        detail = f"{len(different)} of {len(expected)} recorded calls behave differently"
        if shown:
            index = shown[0]
            got = outcomes[index] if isinstance(outcomes[index], dict) else {}
            detail += (f"; shown call {case.data['shown'].index(index) + 1} should give "
                       f"{expected[index]['kind']} {expected[index]['preview'][:160]!r} but gives "
                       f"{got.get('kind')} {str(got.get('preview'))[:160]!r}")
            if got.get("kind") == expected[index]["kind"] and got.get("preview") == expected[index]["preview"]:
                detail += " (it prints the same, so a type, an element order or the state left in the arguments differs)"
        else:
            detail += ", none of them among the shown calls"
        return {**verdict, "reason": "behaviour differs", "detail": detail, "different_calls": len(different),
                "different_shown": len(shown)}
    if strict:
        reference = case.variants(scratch, runner=runner)
        missed = variant_differences(reference, variant_rows(case, file_text, scratch, runner=runner))
        verdict["variants"] = len(reference)
        if missed:
            first = missed[0]
            return {**verdict, "reason": "behaviour differs on variants", "different_variants": len(missed),
                    "detail": f"{len(missed)} of {len(reference)} generated variants of the recorded calls behave "
                              f"differently; with {first['label']} the call ({first['call'][:200]}) should give "
                              f"{first['expected'][:160]!r} but gives {first['got'][:160]!r}"}
    counts = measure(case, file_text, scratch, runner=runner)
    if not counts:
        return {**verdict, "reason": "did not finish", "detail": "the measured replay did not complete"}
    verdict["instructions"] = max(counts)
    verdict["ratio_to_champion"] = round(max(counts) / champion_instructions, 5)
    verdict["seconds"] = round(sum(outcomes[index]["seconds"] for index in case.data["measured"]), 6)
    if max(counts) > (1 - REQUIRED_GAIN) * champion_instructions:
        return {**verdict, "reason": "not cheaper",
                "detail": f"{max(counts)} instructions against {champion_instructions}: "
                          f"{(max(counts) / champion_instructions - 1) * 100:+.1f}%, at least "
                          f"-{REQUIRED_GAIN * 100:.0f}% is required"}
    if strict:
        champion_text = None if champion is None else patched(case.source, case.name, champion)
        native = native_verdict(case, file_text, champion_text, scratch, runner=runner)
        if not native:
            return {**verdict, "reason": "did not finish", "detail": "the uninstrumented replay did not complete"}
        verdict["native"] = native
        if native["processor_ratio"] > MAX_NATIVE_RATIO:
            return {**verdict, "reason": "slower natively",
                    "detail": f"fewer instructions but {(native['processor_ratio'] - 1) * 100:+.1f}% processor time "
                              "without instrumentation"}
        if native["peak_bytes"] > MAX_PEAK_RATIO * native["champion_peak_bytes"] + PEAK_ALLOWANCE:
            return {**verdict, "reason": "uses more memory",
                    "detail": f"peak allocation {native['peak_bytes']} bytes against {native['champion_peak_bytes']}"}
    if case.data["tests"]:
        tests = run_harness("pytest", {**case.spec(), "cwd": "/tree", "arguments": case.data["tests"]},
                            tree=case.tree, scratch=scratch, overlay_text=file_text, overlay_path=case.file,
                            timeout=900, runner=runner)
        broken = sorted(set(case.data["passing_tests"]) - passed_tests(tests.get("tests")))
        if broken:
            return {**verdict, "reason": "breaks tests", "broken_tests": len(broken),
                    "detail": f"{len(broken)} tests of the library that passed no longer pass, first: {broken[0][:160]}"}
    return {**verdict, "accepted": True, "reason": "accepted",
            "detail": f"{(max(counts) / champion_instructions - 1) * 100:+.1f}% instructions"}


# -- what the writer is shown -------------------------------------------------------------------

WRITER_SYSTEM = (
    "You improve one function of a working Python library so that it does the same thing with "
    "fewer executed instructions. You are shown the function, the file it lives in, some real "
    "calls recorded from the library's tests with what they give, how often each line ran, and "
    "what earlier rewrites tried. Your rewrite is replayed on many recorded calls you are not "
    "shown: it must return or raise exactly what the current function does on each of them, leave "
    "the arguments in the same state, and execute at least 3% fewer instructions in total. If it "
    "does, it becomes the current function and you may be asked to improve it again."
)

CONTRACT = """## Contract

- Answer with one or two sentences saying what you changed and why it costs less, then the
  complete rewritten function in one ```python fenced block.
- Same name, parameters, defaults, annotations and decorators. Same return values (type, order of
  elements, laziness: a generator stays a generator), same exception types and messages, same
  effect on the arguments.
- Before the function you may add imports (standard library or the library itself) and
  assignments to new module-level names starting with an underscore, for values computed once.
  Nothing else outside the function; no global/nonlocal state.
- Your answer replaces the whole current version shown at the end, including any lines it has
  before `def`: repeat the ones you still need, they are not kept otherwise.
- Every measured call has different arguments, so caching results between calls gains nothing.
- Python 3.12. Cost is instructions executed by the interpreter and by C code alike."""

STRICT_CONTRACT = """
- The rewrite is also replayed on generated variants of the recorded calls: boundary numbers,
  empty or reversed sequences, unhashable elements, NaN, defaults replaced. On each it must
  return what the original returns, or raise the same exception type. Keep every path of the
  original, including those the shown calls never take.
- No private attribute (`x._name`) the original function does not already use, and no private
  import from outside the library.
- It must not be slower in real processor time nor allocate noticeably more memory."""


def annotate(text: str, first: int, counts: Mapping[str, int]) -> str:
    """The function with, in front of each line, how many times it ran on the shown calls."""
    rows = []
    for offset, line in enumerate(text.rstrip("\n").split("\n")):
        count = counts.get(str(first + offset))
        rows.append(f"{count if count is not None else '':>7} | {line}")
    return "\n".join(rows)


def context_of(source: str, name: str, limit: int = 7000) -> str:
    """What surrounds the function in its file: imports, module-level values, helpers it names."""
    tree = ast.parse(source)
    lines = source.splitlines()
    target = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name)
    used = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
    head, helpers, others = [], [], []
    for node in tree.body:
        text = "\n".join(lines[node.lineno - 1:node.end_lineno])
        if node is target:
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            head.append(text)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            if node.name in used:
                helpers.append(text[:2500])
            else:
                others.append(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            names = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
            if names & used:
                head.append(text[:600])
    parts = ["\n".join(head)]
    if helpers:
        parts.append("# Definitions of this file that the function uses:\n\n" + "\n\n".join(helpers))
    if others:
        parts.append("# Other names defined in this file: " + ", ".join(others[:80]))
    return "\n\n".join(parts)[:limit]


def describe_calls(case: Case) -> str:
    rows = []
    for position, index in enumerate(case.data["shown"], 1):
        row = case.data["outcomes"][index]
        rows.append(f"{position}. {case.name}({row['call']})\n   -> {row['kind']}: {row['preview']}")
    return "\n".join(rows)


def describe_attempts(attempts: Sequence[Mapping]) -> str:
    if not attempts:
        return "None yet."
    return "\n".join(f"- step {item['step']}, attempt {item['attempt']}: {item['reason']} ({item['detail']}). "
                     f"Writer's note: {item.get('note', '')[:300]}" for item in attempts)


def prompt_for(case: Case, champion: str, champion_instructions: int, line_counts: Mapping[str, int],
               attempts: Sequence[Mapping], memory: str | None, strict: bool = False) -> list[dict]:
    original = case.data["instructions"]
    first, _ = function_span(case.source, case.name)
    state = (f"`{case.name}` in `{case.file}` of {case.data['package']} {case.data['version']}. On the measured "
             f"calls the original function executes {original} instructions; the current one executes "
             f"{champion_instructions} ({(champion_instructions / original - 1) * 100:+.1f}%).")
    sections = [CONTRACT + (STRICT_CONTRACT if strict else ""), "## The function\n\n" + state]
    if memory is not None:
        sections.append("## What was learned on other functions\n\n" + memory)
    sections += [
        "## Earlier rewrites of this function\n\n" + describe_attempts(attempts),
        "## The rest of its file\n\n```python\n" + context_of(case.source, case.name) + "\n```",
        f"## Calls recorded from the library's tests ({len(case.data['shown'])} of {len(case.calls)} are shown)\n\n"
        + describe_calls(case),
        "## Current version, with how many times each line ran on the shown calls\n\n```\n"
        + annotate(champion, first, line_counts) + "\n```",
    ]
    return [{"role": "system", "content": WRITER_SYSTEM}, {"role": "user", "content": "\n\n".join(sections)}]


def write_candidate(messages: list[dict], case: Case, champion: str, envelope: Envelope, ledger: Ledger, *,
                    transport: Callable | None = None, strict: bool = False) -> dict:
    """Ask the model for a rewrite. One correction is allowed for an answer refused before execution."""
    messages = list(messages)
    calls: list[dict] = []
    for _ in (1, 2):
        payload = {"model": envelope.model, "messages": messages, "max_tokens": envelope.max_tokens,
                   "provider": {"allow_fallbacks": True, "sort": "price", "max_price": dict(envelope.max_price)}}
        record: dict = {"schema": CALL_SCHEMA, "prompt_digest": digest_of(messages)}
        raw, cost = _send(payload, envelope, ledger, transport)
        record["cost_usd"] = cost
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        record["tokens"] = {key: usage.get(key) for key in ("prompt_tokens", "completion_tokens")}
        answer = ""
        try:
            choice = raw["choices"][0]
            answer = choice["message"].get("content") or ""
            if choice.get("finish_reason") == "length":
                raise ImprovementError("the answer was cut off before the function ended")
            text, note = extract_candidate(answer)
            text = checked_candidate(text, case.source, case.name, case.data["package_import"])
            if strict:
                checked_private(text, case.source, case.name, case.data["package_import"])
            if text_digest(text) == text_digest(champion):
                raise ImprovementError("the rewrite is identical to the current function")
            dropped = sorted(prelude_names(champion) & loaded_names(text) - prelude_names(text))
            if dropped:
                raise ImprovementError(f"the rewrite uses {', '.join(dropped)} without defining it: your answer replaces "
                                       "the whole current version, so repeat the lines before the function you still need")
            record["candidate_sha256"] = text_digest(text)
            calls.append(record)
            return {"candidate": text, "note": note, "calls": calls}
        except (ImprovementError, KeyError, TypeError, IndexError) as error:
            problem = str(error)[:300]
        record["refused"] = problem
        calls.append(record)
        messages.append({"role": "assistant", "content": answer[:12_000] or "(no content)"})
        messages.append({"role": "user", "content": f"That answer was refused before running: {problem}. "
                         "Send the note and the complete function again, corrected."})
    return {"candidate": None, "note": "", "calls": calls, "problem": problem}


# -- the chain ----------------------------------------------------------------------------------


def line_counts(case: Case, champion: str, scratch: Path, *, runner: Callable | None = None) -> dict:
    file_text = patched(case.source, case.name, champion)
    first, last = function_span(file_text, case.name)
    result = run_harness("lines", case.spec(first=first, last=last), tree=case.tree, scratch=scratch,
                         calls=case.select(case.data["shown"]), overlay_text=file_text, overlay_path=case.file,
                         timeout=120, runner=runner)
    return result.get("lines") if isinstance(result.get("lines"), dict) else {}


def improve(case: Case, envelope: Envelope, ledger: Ledger, scratch: Path, *, memory: str | None = None,
            max_steps: int = 6, attempts_per_step: int = 2, save: Callable[[str, str], None] | None = None,
            transport: Callable | None = None, runner: Callable | None = None, strict: bool = False) -> dict:
    """Chain rewrites of one function until a step yields none that is accepted.

    Each step starts from the last accepted rewrite. The record keeps every attempt and why it
    was refused; sources go through ``save`` and are not part of the record.
    """
    champion = function_text(case.source, case.name)
    champion_instructions = original = case.data["instructions"]
    attempts: list[dict] = []
    chain: list[dict] = []
    for step in range(1, max_steps + 1):
        counts = line_counts(case, champion, scratch, runner=runner)
        accepted = False
        for attempt in range(1, attempts_per_step + 1):
            messages = prompt_for(case, champion, champion_instructions, counts, attempts, memory, strict)
            written = write_candidate(messages, case, champion, envelope, ledger, transport=transport, strict=strict)
            row = {"step": step, "attempt": attempt, "note": written["note"], "calls": written["calls"]}
            if written["candidate"] is None:
                row.update(accepted=False, reason="unusable", detail=written.get("problem", "no usable answer"))
            else:
                if save is not None:
                    save(f"step{step}_attempt{attempt}.py", written["candidate"])
                row.update(judge(case, written["candidate"], champion_instructions, scratch, runner=runner,
                                 strict=strict, champion=champion if chain else None))
            attempts.append(row)
            if row["accepted"]:
                champion, champion_instructions, accepted = written["candidate"], row["instructions"], True
                chain.append({"step": step, "attempt": attempt, "instructions": row["instructions"],
                              "seconds": row["seconds"], "candidate_sha256": row["candidate_sha256"],
                              **({"native": row["native"]} if "native" in row else {}),
                              "ratio_to_original": round(row["instructions"] / original, 5), "note": written["note"]})
                break
        if not accepted:
            break
    body = {"case": case.data["case"], "original_instructions": original, "final_instructions": champion_instructions,
            "final_ratio": round(champion_instructions / original, 5), "chain_length": len(chain), "chain": chain,
            "attempts": attempts, "requests": sum(len(item["calls"]) for item in attempts),
            "cost_usd": round(sum(call["cost_usd"] or 0.0 for item in attempts for call in item["calls"]), 6),
            "unknown_cost_requests": sum(call["cost_usd"] is None for item in attempts for call in item["calls"])}
    return {**body, "record_digest": digest_of(body)}


def memory_of(records: Sequence[Mapping], limit: int = 5000) -> str:
    """What earlier functions taught: accepted rewrites with their measured gain, and why others were refused."""
    if not records:
        return "Nothing yet: this is the first function."
    improved = sum(record["chain_length"] > 0 for record in records)
    accepted = sorted(((1 - (step["instructions"] / previous)), step["note"])
                      for record in records
                      for previous, step in zip([record["original_instructions"]] + [s["instructions"] for s in record["chain"]],
                                                record["chain"]))
    refusals: dict[str, int] = {}
    for record in records:
        for attempt in record["attempts"]:
            if not attempt["accepted"]:
                refusals[attempt["reason"]] = refusals.get(attempt["reason"], 0) + 1
    lines = [f"{len(records)} other functions were worked on; {improved} got at least one accepted rewrite.",
             "Refused rewrites: " + (", ".join(f"{count} {reason}" for reason, count in sorted(refusals.items())) or "none") + ".",
             "Accepted rewrites, largest measured gain first (the writer's own note):"]
    lines += [f"- {gain * 100:.0f}% fewer instructions: {note[:260]}" for gain, note in reversed(accepted[-14:])]
    behaviour = [attempt for record in records for attempt in record["attempts"] if attempt["reason"] == "behaviour differs"]
    if behaviour:
        lines.append("Rewrites refused for changing behaviour (the writer's own note):")
        lines += [f"- {attempt.get('note', '')[:200]}" for attempt in behaviour[-6:]]
    return "\n".join(lines)[:limit]


# -- what a trial shows -------------------------------------------------------------------------


def _geometric_mean(values: Sequence[float]) -> float:
    from math import exp, log
    return round(exp(sum(log(value) for value in values) / len(values)), 5) if values else 1.0


def summarize(arms: Mapping[str, Sequence[Mapping]], warm_up: int) -> dict:
    """Per arm: how many functions improved, how long the chains are, what they gain. Between the
    accumulating and the isolated arm: paired outcomes on the cases after the warm-up."""
    summary: dict = {"arms": {}}
    for arm, records in arms.items():
        lengths: dict[str, int] = {}
        reasons: dict[str, int] = {}
        for record in records:
            lengths[str(record["chain_length"])] = lengths.get(str(record["chain_length"]), 0) + 1
            for attempt in record["attempts"]:
                reasons[attempt["reason"]] = reasons.get(attempt["reason"], 0) + 1
        improved = [record for record in records if record["chain_length"]]
        steps = [step for record in improved for step in record["chain"]]
        summary["arms"][arm] = {
            "cases": len(records), "improved": len(improved),
            "chain_lengths": dict(sorted(lengths.items())),
            "improved_by_a_second_step": sum(record["chain_length"] >= 2 for record in records),
            "accepted_rewrites_by_step": {str(number): sum(step["step"] == number for step in steps)
                                          for number in sorted({step["step"] for step in steps})},
            "attempt_outcomes": dict(sorted(reasons.items())),
            "final_ratio_geometric_mean_all": _geometric_mean([record["final_ratio"] for record in records]),
            "final_ratio_geometric_mean_improved": _geometric_mean([record["final_ratio"] for record in improved]),
            "first_step_ratio_geometric_mean_improved": _geometric_mean([record["chain"][0]["ratio_to_original"] for record in improved]),
            "requests": sum(record["requests"] for record in records),
            "cost_usd": round(sum(record["cost_usd"] for record in records), 4),
            "unknown_cost_requests": sum(record["unknown_cost_requests"] for record in records),
        }
    if "isolated" in arms and "accumulating" in arms:
        pairs = list(zip(arms["isolated"], arms["accumulating"]))[warm_up:]
        if any(one["case"] != two["case"] for one, two in pairs):
            raise ImprovementError("the two arms do not list the same cases in the same order")
        only_isolated = sum(one["chain_length"] > 0 and two["chain_length"] == 0 for one, two in pairs)
        only_accumulating = sum(two["chain_length"] > 0 and one["chain_length"] == 0 for one, two in pairs)
        lower_isolated = sum(one["final_ratio"] < two["final_ratio"] - 0.01 for one, two in pairs)
        lower_accumulating = sum(two["final_ratio"] < one["final_ratio"] - 0.01 for one, two in pairs)
        summary["accumulating_against_isolated"] = {
            "cases_after_warm_up": len(pairs),
            "improved_only_isolated": only_isolated, "improved_only_accumulating": only_accumulating,
            "improved_sign_test": exact_sign_test(only_isolated, only_accumulating),
            "cheaper_by_a_point_isolated": lower_isolated, "cheaper_by_a_point_accumulating": lower_accumulating,
            "cheaper_sign_test": exact_sign_test(lower_isolated, lower_accumulating),
        }
    return summary
