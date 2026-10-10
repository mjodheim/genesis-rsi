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


def observe(function, args, kwargs, seconds: int) -> dict:
    """Call ``function`` once and describe everything observable about it."""
    shown = (repr(args)[1:-1].rstrip(",") + "".join(f", {key}={item!r}" for key, item in kwargs.items()))[:400]
    started = time.perf_counter()
    signal.alarm(seconds)
    try:
        try:
            result = function(*args, **kwargs)
            kind, body, preview, error = "returned", canon(result), "", ""
            preview = repr(body)[:300] if hasattr(result, "__next__") else repr(result)[:300]
        except Deadline:
            raise
        except Uncanonical:
            raise
        except BaseException as caught:
            kind, body, error = "raised", (_name(type(caught)), str(caught)[:500]), _name(type(caught))
            preview = f"{type(caught).__name__}: {str(caught)[:250]}"
        after = canon((args, kwargs))
        signal.alarm(0)
    except Deadline:
        return {"kind": "timeout", "digest": "", "preview": "", "seconds": float(seconds), "call": shown}
    except Uncanonical as caught:
        signal.alarm(0)
        return {"kind": "uncanonical", "digest": "", "preview": str(caught), "seconds": 0.0, "call": shown}
    except BaseException as caught:
        signal.alarm(0)
        return {"kind": "uncanonical", "digest": "", "preview": type(caught).__name__, "seconds": 0.0, "call": shown}
    elapsed = time.perf_counter() - started
    digest = hashlib.sha256(repr((kind, body, after)).encode("utf-8", "backslashreplace")).hexdigest()
    return {"kind": kind, "digest": digest, "preview": preview, "seconds": round(elapsed, 6), "call": shown,
            "error": error}


def outcome(function, blob: bytes, seconds: int) -> dict:
    """Call ``function`` on one recorded call and describe everything observable about it."""
    try:
        args, kwargs = pickle.loads(blob)
    except Exception as error:
        return {"kind": "unloadable", "digest": "", "preview": type(error).__name__, "seconds": 0.0}
    row = observe(function, args, kwargs, seconds)
    row.pop("error", None)
    return row


# -- generated variants of recorded calls -------------------------------------------------------
#
# A recorded call only shows what the library's tests happen to exercise. Variants edit one
# argument of a recorded call at a time (a boundary number, an empty or reversed sequence, an
# unhashable element, a NaN shared by every place a value occurred) and are replayed on the
# original and on the rewrite alike.

VARIANT_SOURCES = 16
VARIANTS_PER_SOURCE = 25
VARIANT_SECONDS = 1
VARIANT_BUDGET = 90.0
_SITE_WIDTH = 4


def alternatives(value) -> list:
    """Small edits of one value, as ``(label, replacement)``."""
    kind = type(value)
    if kind is bool:
        found = [("flipped", not value)]
    elif kind is int:
        found = [("0", 0), ("1", 1), ("-1", -1), ("+1", value + 1), ("negated", -value)]
    elif kind is float:
        found = [("nan", float("nan")), ("inf", float("inf")), ("0.0", 0.0), ("negated", -value)]
    elif value is None:
        found = [("0", 0), ("1", 1), ("empty text", ""), ("empty tuple", ())]
    elif kind is str:
        found = [("empty", ""), ("reversed", value[::-1]), ("accented", value + "\u00e9"),
                 ("halved", value[:len(value) // 2]), ("spaced", " " + value)]
    elif kind is bytes:
        found = [("empty", b""), ("reversed", value[::-1]), ("halved", value[:len(value) // 2])]
    elif kind in (list, tuple):
        items = list(value)
        found = [("empty", []), ("reversed", items[::-1]), ("first repeated", items + items[:1]),
                 ("last dropped", items[:-1])]
        if items:
            found.append(("first boxed", [[items[0]]] + items[1:]))
        found = [(label, kind(item)) for label, item in found]
    elif kind is dict:
        found = [("empty", {}), ("last key dropped", dict(list(value.items())[:-1]))]
    elif kind in (set, frozenset):
        found = [("empty", kind())]
    else:
        found = []
    return [(label, item) for label, item in found if type(item) is not kind or repr(item) != repr(value)]


def sites(root, depth: int = 2) -> list:
    """Paths to the values a variant may edit: arguments, then the first items inside them."""
    found = []

    def walk(value, path, left):
        found.append(path)
        if not left:
            return
        if type(value) in (list, tuple):
            for index in range(min(len(value), _SITE_WIDTH)):
                walk(value[index], path + (index,), left - 1)
        elif type(value) is dict:
            for key in list(value)[:_SITE_WIDTH]:
                walk(value[key], path + (key,), left - 1)

    for index, value in enumerate(root[0]):
        walk(value, (0, index), depth)
    for key, value in root[1].items():
        walk(value, (1, key), depth)
    return found


def value_at(root, path):
    for step in path:
        root = root[step]
    return root


def replaced(value, path, new):
    """``value`` with the item at ``path`` replaced, containers on the way copied."""
    if not path:
        return new
    kind = type(value)
    if kind is dict:
        copy = dict(value)
        copy[path[0]] = replaced(value[path[0]], path[1:], new)
        return copy
    items = list(value)
    items[path[0]] = replaced(items[path[0]], path[1:], new)
    return items if kind is list else tuple(items)


def edits(root) -> list:
    """Every variant of one call, as ``(label, [(path, replacement), ...])`` in a fixed order."""
    paths = sites(root)
    found = []
    for path in paths:
        for label, new in alternatives(value_at(root, path)):
            found.append((f"{'/'.join(map(str, path[1:]))}: {label}", [(path, new)]))
    shared: dict = {}
    for path in paths:
        value = value_at(root, path)
        if type(value) in (int, str, float):
            shared.setdefault((type(value), repr(value)), []).append(path)
    for (_, shown), group in [item for item in shared.items() if len(item[1]) > 1][:3]:
        nan = float("nan")
        found.append((f"every {shown}: one NaN", [(path, nan) for path in group]))
        found.append((f"every {shown}: boxed", [(path, [value_at(root, path)]) for path in group]))
    return found


def bound(function, args, kwargs):
    """The call with its defaults written out, so that a variant can edit them too."""
    try:
        signature = inspect.signature(function)
        binding = signature.bind(*args, **kwargs)
        binding.apply_defaults()
        return [list(binding.args), dict(binding.kwargs)]
    except (TypeError, ValueError):
        return [list(args), dict(kwargs)]


def chosen(count: int, salt: str, limit: int) -> list[int]:
    ranked = sorted(range(count), key=lambda index: hashlib.sha256(f"{salt}|{index}".encode()).hexdigest())
    return sorted(ranked[:limit])


def run_variants(spec: dict) -> dict:
    function = _target(spec)
    blobs = _blobs(spec)
    digests = [hashlib.sha256(blob).hexdigest() for blob in blobs]
    sources = sorted(range(len(blobs)), key=lambda index: hashlib.sha256(("variant|" + digests[index]).encode()).hexdigest())
    rows, started = [], time.perf_counter()
    for source in sources[:VARIANT_SOURCES]:
        try:
            count = len(edits(bound(function, *pickle.loads(blobs[source]))))
        except Exception:
            continue
        for number in chosen(count, digests[source], VARIANTS_PER_SOURCE):
            key = f"{digests[source][:16]}:{number}"
            if time.perf_counter() - started > VARIANT_BUDGET:
                rows.append({"key": key, "kind": "skipped", "digest": "", "error": "", "call": "", "label": ""})
                continue
            try:
                root = bound(function, *pickle.loads(blobs[source]))
                label, changes = edits(root)[number]
                for path, new in changes:
                    root = replaced(root, path, new)
                row = observe(function, tuple(root[0]), root[1], VARIANT_SECONDS)
            except Exception as error:
                row, label = {"kind": "unbuildable", "digest": "", "error": type(error).__name__, "call": ""}, ""
            rows.append({"key": key, "kind": row["kind"], "digest": row["digest"], "error": row.get("error", ""),
                         "call": row.get("call", ""), "preview": row.get("preview", "")[:200], "label": label})
    return {"variants": rows}


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


def run_native(spec: dict) -> dict:
    """Cost of the measured calls without instrumentation: processor time, wall time, peak allocation."""
    import gc
    import tracemalloc
    function = _target(spec)
    blobs = _blobs(spec)
    drain, cut = collections.deque, itertools.islice

    def replay(calls):
        for args, kwargs in calls:
            try:
                result = function(*args, **kwargs)
                if hasattr(result, "__next__"):
                    drain(cut(result, DRAIN), maxlen=0)
            except Deadline:
                raise
            except BaseException:
                pass

    def fresh():
        return [pickle.loads(blob) for blob in blobs]

    signal.alarm(spec["total_seconds"])
    calls = fresh()
    started = time.perf_counter()
    replay(calls)
    once = time.perf_counter() - started
    loops = max(1, min(200, int(0.2 / max(once, 1e-6)) + 1))
    wall, processor = [], []
    for _ in range(spec["repeats"]):
        batches = [fresh() for _ in range(loops)]
        gc.collect()
        wall_start, processor_start = time.perf_counter(), time.process_time()
        for batch in batches:
            replay(batch)
        processor.append((time.process_time() - processor_start) / loops)
        wall.append((time.perf_counter() - wall_start) / loops)
    calls = fresh()
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    tracemalloc.reset_peak()
    replay(calls)
    peak = tracemalloc.get_traced_memory()[1] - before
    tracemalloc.stop()
    signal.alarm(0)
    return {"wall": min(wall), "processor": min(processor), "peak_bytes": max(0, peak), "loops": loops}


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
    result = {"outcomes": run_outcomes, "measure": run_measure, "lines": run_lines,
              "variants": run_variants, "native": run_native}[mode](spec)
    with open(spec["out"] + ".partial", "w", encoding="utf-8") as handle:
        json.dump(result, handle)
    os.replace(spec["out"] + ".partial", spec["out"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
