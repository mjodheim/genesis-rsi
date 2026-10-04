"""Known-source native bodies; expected answers never enter a candidate worker."""
import base64
import gzip
import json
import random
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from functools import lru_cache
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, canonical, digest, digest_bytes

DOMAINS = ("relational-sql", "regular-expressions", "structured-json", "binary-compression")
WORKER = ROOT / "experiment/rsi_v29/native_worker.py"
TEMPLATES = {
    "relational-sql": '''import sqlite3
def run(operation, data):
    slot = int(operation)
    choice = OPS[slot] if slot < len(OPS) else 0
    if not choice:
        return None
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE items(value INTEGER)")
        connection.executemany("INSERT INTO items VALUES (?)", [(v,) for v in data["values"]])
        if choice == 1:
            return connection.execute("SELECT SUM(value) FROM items").fetchone()[0]
        if choice == 2:
            return connection.execute("SELECT MAX(value) FROM items").fetchone()[0]
        if choice == 3:
            return connection.execute("SELECT COUNT(*) FROM items WHERE value >= ?", (data["threshold"],)).fetchone()[0]
        return connection.execute("SELECT SUM(value*value) FROM items").fetchone()[0]
    finally:
        connection.close()
''',
    "regular-expressions": '''import re
def run(operation, data):
    slot = int(operation)
    choice = OPS[slot] if slot < len(OPS) else 0
    if choice == 1:
        return re.findall(r"[A-Za-z]+", data["text"])
    if choice == 2:
        return bool(re.fullmatch(r"[A-Za-z]+(?:-[A-Za-z]+)*", data["text"]))
    if choice == 3:
        return re.split(re.escape(data["separator"]), data["text"])
    if choice == 4:
        return re.sub(re.escape(data["token"]), lambda match: "X", data["text"], count=1)
    return None
''',
    "structured-json": '''import json
from decimal import Decimal
def run(operation, data):
    slot = int(operation)
    choice = OPS[slot] if slot < len(OPS) else 0
    if choice == 1:
        return json.dumps(json.loads(data["payload"]), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if choice == 2:
        return json.loads(data["payload"], object_pairs_hook=lambda pairs: list(pairs))
    if choice == 3:
        return str(json.loads(data["number"], parse_float=Decimal))
    if choice == 4:
        return sorted(json.loads(data["payload"]))
    return None
''',
    "binary-compression": '''import zlib
import base64
def run(operation, data):
    slot = int(operation)
    choice = OPS[slot] if slot < len(OPS) else 0
    if choice == 1:
        return zlib.decompress(base64.b64decode(data["gzip"]), wbits=31).hex()
    if choice == 2:
        return zlib.decompress(base64.b64decode(data["raw"]), wbits=-15).hex()
    if choice == 3:
        return zlib.decompress(base64.b64decode(data["zlib"]), wbits=15).hex()
    if choice == 4:
        return zlib.adler32(base64.b64decode(data["plain"]))
    return None
''',
}


def genome(domain, ops):
    if domain not in DOMAINS or type(ops) not in (tuple, list) or any(type(v) is not int or not 0 <= v <= 4 for v in ops):
        raise ValueError("Unknown native body or operator")
    values = list(ops)
    while values and values[-1] == 0:
        values.pop()
    return {"domain": domain, "ops": values}


def validate(value):
    if type(value) is not dict or set(value) != {"domain", "ops"}:
        raise ValueError("Invalid native genome")
    result = genome(value["domain"], value["ops"])
    if result != value:
        raise ValueError("Noncanonical trailing-null body")
    return result


def render(value):
    row = validate(value)
    return "OPS = " + repr(tuple(row["ops"])) + "\n" + TEMPLATES[row["domain"]]


@lru_cache(maxsize=16384)
def describe(domain, ops):
    value = genome(domain, ops)
    source = render(value)
    return {"source_sha256": digest_bytes(source.encode()), "semantic_sha256": digest(value),
            "structure_sha256": digest([domain, value["ops"]]),
            "target_axes": ["slot-" + str(i) for i, op in enumerate(value["ops"]) if op]}


def descriptor(value):
    row = validate(value)
    return describe(row["domain"], tuple(row["ops"]))


@lru_cache(maxsize=4096)
def development_program(domain, ops):
    functions = {}
    exec(compile(render(genome(domain, ops)), "<native-consumed-development>", "exec"), functions)
    return functions["run"]


def execute(value, contexts, slots, *, isolated=True):
    source = render(value)
    operations = [{"operation": str(slot), "data": case["data"]} for slot in range(slots) for case in contexts]
    if isolated:
        with tempfile.TemporaryDirectory(prefix="v35-native-") as directory:
            path = Path(directory) / "body.py"
            path.write_text(source)
            result = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(path)],
                                    input=json.dumps({"operations": operations}), text=True, capture_output=True,
                                    cwd=directory, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=5)
        if result.returncode:
            raise RuntimeError("Native candidate instrument failed: " + result.stderr[-500:])
        outputs = json.loads(result.stdout)
    else:
        run = development_program(value["domain"], tuple(value["ops"]))
        outputs = []
        for case in operations:
            try:
                outputs.append({"ok": True, "value": run(case["operation"], case["data"])})
            except Exception as error:
                outputs.append({"ok": False, "error": type(error).__name__})
    if type(outputs) is not list or len(outputs) != len(operations):
        raise ValueError("Incomplete native output")
    # Both execution paths use the native worker's JSON wire types (pairs become lists).
    return json.loads(json.dumps(outputs, ensure_ascii=False))


def receipt(task, value, outputs, *, isolated):
    width = len(task["inputs"])
    if len(outputs) != task["slots"] * width:
        raise ValueError("Omitted component or context")
    passed = []
    for slot, op in enumerate(task["target"]):
        subset = outputs[slot * width:(slot + 1) * width]
        passed.append(all(row.get("ok") is True and canonical(row.get("value")) == canonical(case["answers"][op])
                          for row, case in zip(subset, task["inputs"])))
    return {"accepted": True, "source_sha256": descriptor(value)["source_sha256"],
            "evaluator_task_sha256": digest(task), "native_source_executed": True,
            "isolated": isolated, "outputs": outputs, "output_sha256": digest(outputs),
            "matched_slots": sum(passed), "passed_slots": passed,
            "quality_milli": sum(passed) * 1000 // task["slots"]}


def evaluate(task, value, *, isolated=True):
    if value["domain"] != task["domain"] or len(value["ops"]) > task["slots"]:
        raise ValueError("Candidate outside admitted interface")
    return receipt(task, value, execute(value, task["inputs"], task["slots"], isolated=isolated), isolated=isolated)


def contexts(seed, domain, epoch, position, count=4):
    rng = random.Random(digest(["v35-contexts", seed, domain, epoch, position]))
    rows = []
    for index in range(count):
        number = rng.randrange(1, 10000)
        if domain == "relational-sql":
            values = [2 + rng.randrange(9), 20 + index, -10 - index, 50 + rng.randrange(30)]
            data = {"values": values, "threshold": 17}
            answers = [None, sum(values), max(values), sum(v >= 17 for v in values), sum(v*v for v in values)]
        elif domain == "regular-expressions":
            text = f"Ab{number}-Cd.Word|Ef{index}"
            data = {"text": text, "separator": ".", "token": "|"}
            # Independently constructed expectations; no reference regex execution.
            answers = [None, ["Ab", "Cd", "Word", "Ef"], False,
                       [f"Ab{number}-Cd", f"Word|Ef{index}"], text.replace("|", "X", 1)]
        elif domain == "structured-json":
            pairs = [["z", number], ["a", "é" + str(index)], ["z", number + 1]]
            payload = "{" + ",".join(json.dumps(k) + ":" + json.dumps(v, ensure_ascii=False) for k,v in pairs) + "}"
            numeric = str(number) + ".123456789012345678901"
            data = {"payload": payload, "number": numeric}
            answers = [None, json.dumps(dict(pairs), sort_keys=True, ensure_ascii=False, separators=(",", ":")),
                       pairs, numeric, ["a", "z"]]
        elif domain == "binary-compression":
            a, b, c, d = ((prefix + str(number)).encode() for prefix in ("gzip-", "raw-", "zlib-", "plain-"))
            compressor = zlib.compressobj(wbits=-15)
            data = {"gzip": base64.b64encode(gzip.compress(a, mtime=0)).decode(),
                    "raw": base64.b64encode(compressor.compress(b) + compressor.flush()).decode(),
                    "zlib": base64.b64encode(zlib.compress(c)).decode(), "plain": base64.b64encode(d).decode()}
            lo, hi = 1, 0
            for byte in d:
                lo, hi = (lo + byte) % 65521, (hi + lo + byte) % 65521
            answers = [None, a.hex(), b.hex(), c.hex(), (hi << 16) | lo]
        else:
            raise ValueError("Unknown reference domain")
        if len({canonical(value) for value in answers}) != 5:
            raise ValueError("Primitive discrimination witness missing")
        rows.append({"data": data, "answers": answers})
    return rows


def runtime():
    return {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "zlib_compile": zlib.ZLIB_VERSION, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION}
