"""Container side of program improvement: record calls, replay them, count what they cost.

This file is copied into the measurement container and run there, next to third-party library
code and model-written functions. It uses the standard library only and never imports Genesis.
The host never unpickles anything this file produced: recorded arguments travel as opaque
base64 text and come back here to be replayed.

As a pytest plugin (``-p improvement_harness``) it wraps the top-level functions of one package
and keeps the distinct, picklable arguments the package's own tests call them with. As a script
it replays recorded calls against the function currently on disk:

    outcomes   a digest of what every call returned or raised and of its arguments afterwards
    measure    the calls run between the two marker calls Callgrind counts instructions between
    lines      how often each line of the function ran
    pytest     the package's tests, with one JSON line of outcomes per test
"""
from __future__ import annotations

import ast
import base64
import collections
import functools
import hashlib
import inspect
import itertools
import json
import os
import pickle
import signal
import sys
import time
import types

CALL_LIMIT = 200
SEEN_LIMIT = 2000
BLOB_LIMIT = 8000
MIN_LINES, MAX_LINES = 5, 120
DRAIN = 2000
NODE_LIMIT = 100_000
MARKER = "/usr/local/lib/libgenesis_marker.so"
_TEST_PARTS = {"tests", "test", "testing", "conftest.py"}


# -- one canonical form for whatever a call produced --------------------------------------------


class Uncanonical(Exception):
    """A value too large or too deep to compare."""


def _name(kind: type) -> str:
    return f"{kind.__module__}.{kind.__qualname__}"


def canon(value, depth: int = 0, seen: frozenset = frozenset(), budget: list | None = None):
    """A nested tuple that is equal for two values exactly when they are held to be the same.

    Element order counts for sequences and mappings and not for sets. Iterators are consumed, at
    most ``DRAIN`` items. Objects compare by type and attributes; an object that only prints its
    address compares by type.
    """
    budget = [NODE_LIMIT] if budget is None else budget
    budget[0] -= 1
    if budget[0] < 0:
        raise Uncanonical("too many nodes")
    if value is None or isinstance(value, (bool, int, float, complex, str, bytes, bytearray)):
        return (type(value).__name__, repr(value)[:20_000])
    if isinstance(value, (type, types.FunctionType, types.BuiltinFunctionType, types.MethodType, types.ModuleType)):
        return ("ref", getattr(value, "__qualname__", None) or getattr(value, "__name__", "?"))
    if id(value) in seen:
        return ("cycle",)
    if depth > 12:
        raise Uncanonical("too deep")
    inner = seen | {id(value)}
    step = functools.partial(canon, depth=depth + 1, seen=inner, budget=budget)
    if isinstance(value, BaseException):
        return ("exception", _name(type(value)), str(value)[:500])
    if isinstance(value, (list, tuple, collections.deque)):
        return (_name(type(value)), tuple(step(item) for item in value))
    if isinstance(value, dict):
        return (_name(type(value)), tuple((step(key), step(item)) for key, item in value.items()))
    if isinstance(value, (set, frozenset)):
        return (_name(type(value)), tuple(sorted(repr(step(item)) for item in value)))
    if hasattr(value, "__next__") and hasattr(value, "__iter__") and not hasattr(value, "read"):
        items, ending = [], "exhausted"
        try:
            for item in itertools.islice(value, DRAIN):
                items.append(step(item))
            else:
                if len(items) == DRAIN:
                    ending = "cut"
        except Uncanonical:
            raise
        except Exception as error:
            ending = ("raised", _name(type(error)), str(error)[:500])
        return ("iterator", tuple(items), ending)
    state = None
    if hasattr(value, "__dict__") and isinstance(getattr(value, "__dict__", None), dict):
        state = dict(vars(value))
    slots = [name for kind in type(value).__mro__ for name in getattr(kind, "__slots__", ())
             if isinstance(name, str) and name not in ("__dict__", "__weakref__")]
    if slots:
        state = state or {}
        for name in slots:
            if hasattr(value, name):
                state[name] = getattr(value, name)
    if state is not None:
        return (_name(type(value)), tuple((key, step(item)) for key, item in state.items()))
    text = repr(value)
    return (_name(type(value)), text[:2000] if " at 0x" not in text else "")


class Deadline(BaseException):
    pass


def _alarm(signum, frame):
    raise Deadline()


def outcome(function, blob: bytes, seconds: int) -> dict:
    """Call ``function`` on one recorded call and describe everything observable about it."""
    try:
        args, kwargs = pickle.loads(blob)
    except Exception as error:
        return {"kind": "unloadable", "digest": "", "preview": type(error).__name__, "seconds": 0.0}
    shown = (repr(args)[1:-1].rstrip(",") + "".join(f", {key}={item!r}" for key, item in kwargs.items()))[:400]
    started = time.perf_counter()
    signal.alarm(seconds)
    try:
        try:
            result = function(*args, **kwargs)
            kind, body, preview = "returned", canon(result), ""
            preview = repr(body)[:300] if hasattr(result, "__next__") else repr(result)[:300]
        except Deadline:
            raise
        except Uncanonical:
            raise
        except BaseException as error:
            kind, body = "raised", (_name(type(error)), str(error)[:500])
            preview = f"{type(error).__name__}: {str(error)[:250]}"
        after = canon((args, kwargs))
        signal.alarm(0)
    except Deadline:
        return {"kind": "timeout", "digest": "", "preview": "", "seconds": float(seconds), "call": shown}
    except Uncanonical as error:
        signal.alarm(0)
        return {"kind": "uncanonical", "digest": "", "preview": str(error), "seconds": 0.0, "call": shown}
    except BaseException as error:
        signal.alarm(0)
        return {"kind": "uncanonical", "digest": "", "preview": type(error).__name__, "seconds": 0.0, "call": shown}
    elapsed = time.perf_counter() - started
    digest = hashlib.sha256(repr((kind, body, after)).encode("utf-8", "backslashreplace")).hexdigest()
    return {"kind": kind, "digest": digest, "preview": preview, "seconds": round(elapsed, 6), "call": shown}


# -- recording, as a pytest plugin --------------------------------------------------------------

_RECORDS: dict = {}
_STATE = {"test": "", "busy": False, "installed": False}
_REPORTS: list = []


def top_level_functions(source: str) -> list[dict]:
    """Plain top-level functions of a file, with the lines they span including decorators."""
    found = []
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef):
            first = min([node.lineno] + [item.lineno for item in node.decorator_list])
            if MIN_LINES <= node.end_lineno - first + 1 <= MAX_LINES:
                found.append({"name": node.name, "first": first, "last": node.end_lineno})
    return found


def _wrapper(slot: dict, original):
    @functools.wraps(original)
    def recorded(*args, **kwargs):
        if not _STATE["busy"] and slot["seen"] < SEEN_LIMIT and len(slot["calls"]) < CALL_LIMIT:
            slot["seen"] += 1
            _STATE["busy"] = True
            try:
                blob = pickle.dumps((args, kwargs), protocol=4)
                if len(blob) <= BLOB_LIMIT:
                    slot["calls"].setdefault(hashlib.sha256(blob).hexdigest(), blob)
                    if len(slot["tests"]) < 6:
                        slot["tests"].add(_STATE["test"])
            except Exception:
                pass
            finally:
                _STATE["busy"] = False
        return original(*args, **kwargs)
    return recorded


def _install(package: str, root: str) -> None:
    replaced: dict = {}
    for module in list(sys.modules.values()):
        name, path = getattr(module, "__name__", ""), getattr(module, "__file__", None) or ""
        if not (name == package or name.startswith(package + ".")) or not path.endswith(".py"):
            continue
        relative = os.path.relpath(path, root)
        if relative.startswith("..") or _TEST_PARTS & set(relative.split(os.sep)) or os.path.basename(path).startswith("test_"):
            continue
        try:
            with open(path, encoding="utf-8") as handle:
                functions = top_level_functions(handle.read())
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for item in functions:
            current = vars(module).get(item["name"])
            try:
                inner = inspect.unwrap(current) if callable(current) else None
            except ValueError:
                inner = None
            code = getattr(inner, "__code__", None)
            if (not isinstance(inner, types.FunctionType) or code.co_filename != path
                    or not item["first"] <= code.co_firstlineno <= item["last"] or id(current) in replaced):
                continue
            slot = {"module": name, "name": item["name"], "file": relative, "first": item["first"],
                    "last": item["last"], "calls": {}, "tests": set(), "seen": 0}
            _RECORDS[f"{name}.{item['name']}"] = slot
            replaced[id(current)] = (current, _wrapper(slot, current))
    for module in list(sys.modules.values()):
        try:
            names = list(vars(module).items())
        except TypeError:
            continue
        for key, value in names:
            pair = replaced.get(id(value))
            if pair is not None and pair[0] is value:
                try:
                    setattr(module, key, pair[1])
                except Exception:
                    pass


def pytest_collection_finish(session):
    package = os.environ.get("GENESIS_RECORD_PACKAGE")
    if package and not _STATE["installed"]:
        _STATE["installed"] = True
        _install(package, os.environ["GENESIS_TREE"])


def pytest_runtest_setup(item):
    _STATE["test"] = item.nodeid.split("::")[0]


def pytest_runtest_logreport(report):
    if report.when == "call" or report.outcome != "passed":
        _REPORTS.append([report.nodeid, report.when, report.outcome])


def pytest_sessionfinish(session):
    out = os.environ.get("GENESIS_OUT", "/out")
    if os.environ.get("GENESIS_RECORD_PACKAGE"):
        os.makedirs(os.path.join(out, "targets"), exist_ok=True)
        for identifier, slot in _RECORDS.items():
            if not slot["calls"]:
                continue
            body = {key: slot[key] for key in ("module", "name", "file", "first", "last", "seen")}
            body["tests"] = sorted(test for test in slot["tests"] if test)
            body["calls"] = [base64.b64encode(slot["calls"][digest]).decode() for digest in sorted(slot["calls"])]
            with open(os.path.join(out, "targets", identifier + ".json"), "w", encoding="utf-8") as handle:
                json.dump(body, handle)
    with open(os.path.join(out, "tests.json"), "w", encoding="utf-8") as handle:
        json.dump(_REPORTS, handle)


# -- replay, as a script ------------------------------------------------------------------------


def _target(spec: dict):
    import importlib
    module = importlib.import_module(spec["module"])
    return getattr(module, spec["name"])


def _blobs(spec: dict) -> list[bytes]:
    with open(spec["calls"], encoding="utf-8") as handle:
        return [base64.b64decode(text) for text in json.load(handle)]


def run_outcomes(spec: dict) -> dict:
    function = _target(spec)
    return {"outcomes": [outcome(function, blob, spec["seconds"]) for blob in _blobs(spec)]}


def run_measure(spec: dict) -> dict:
    import ctypes
    function = _target(spec)
    calls = [pickle.loads(blob) for blob in _blobs(spec)]
    marker = ctypes.CDLL(MARKER)
    start, stop = marker.genesis_measure_start, marker.genesis_measure_stop
    drain, cut, done = collections.deque, itertools.islice, 0
    signal.alarm(spec["total_seconds"])
    start()
    for args, kwargs in calls:
        try:
            result = function(*args, **kwargs)
            if hasattr(result, "__next__"):
                drain(cut(result, DRAIN), maxlen=0)
        except Deadline:
            raise
        except BaseException:
            pass
        done += 1
    stop()
    signal.alarm(0)
    return {"calls": done}


def run_lines(spec: dict) -> dict:
    function = _target(spec)
    code = inspect.unwrap(function).__code__
    path, first, last = code.co_filename, spec["first"], spec["last"]
    counts: collections.Counter = collections.Counter()

    def local(frame, event, arg):
        if event == "line":
            counts[frame.f_lineno] += 1
        return local

    def tracer(frame, event, arg):
        if frame.f_code.co_filename == path and first <= frame.f_lineno <= last:
            return local
        return None

    for blob in _blobs(spec):
        try:
            args, kwargs = pickle.loads(blob)
            signal.alarm(spec["seconds"] * 5)
            sys.settrace(tracer)
            result = function(*args, **kwargs)
            if hasattr(result, "__next__"):
                collections.deque(itertools.islice(result, DRAIN), maxlen=0)
        except BaseException:
            pass
        finally:
            sys.settrace(None)
            signal.alarm(0)
    return {"lines": {str(line): count for line, count in sorted(counts.items())}}


def main(argv: list[str]) -> int:
    mode = argv[1]
    with open(argv[2], encoding="utf-8") as handle:
        spec = json.load(handle)
    sys.path[:0] = spec["path"]
    signal.signal(signal.SIGALRM, _alarm)
    if mode == "pytest":
        import pytest
        os.chdir(spec["cwd"])
        return int(pytest.main(["-p", "improvement_harness", "-p", "no:cacheprovider", "-p", "no:warnings",
                                "-o", "addopts=", "--continue-on-collection-errors", "-q", "--no-header",
                                "--tb=no", *spec["arguments"]]))
    result = {"outcomes": run_outcomes, "measure": run_measure, "lines": run_lines}[mode](spec)
    with open(spec["out"] + ".partial", "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    os.replace(spec["out"] + ".partial", spec["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
