"""Four fixed native algorithmic domains; only reference/seed calibration before freeze."""
import base64
import gzip
import itertools
import json
import sqlite3
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.family import structure

HERE = Path(__file__).resolve().parent
WORKER = HERE / "native_worker.py"
CAPS = Caps(requests=9, rounds=8, parallelism=2, mutation_depth=3)
DOMAINS = ("relational-sql", "regular-expressions", "structured-json", "binary-compression")
VARIANTS = {
    "relational-sql": (
        ('SUM(value)', 'SUM(value)+1', 'SUM(value)-1', 'SUM(value)*2+1'),
        ('value >= ?', 'value > ?', 'value < ?', 'value = ?'),
        ('value ASC', 'value DESC', 'label ASC', '-value ASC')),
    "regular-expressions": (
        ('bool(re.fullmatch(pattern, data["text"]))', 'bool(re.search(pattern, data["text"]))',
         'bool(re.match(pattern, data["text"]))', 'not bool(re.fullmatch(pattern, data["text"]))'),
        ('re.split(re.escape(data["separator"]), data["text"])', 're.split(data["separator"], data["text"])',
         'list(data["text"])', 'data["text"].split(" ")'),
        ('1', '0', '2', '3')),
    "structured-json": (
        ('Decimal', 'float', 'lambda value: round(float(value), 2)', 'lambda value: int(float(value))'),
        ('sort_keys=True, ensure_ascii=False, separators=(",", ":")',
         'sort_keys=False, ensure_ascii=False, separators=(",", ":")',
         'sort_keys=True, ensure_ascii=True, separators=(",", ":")',
         'sort_keys=True, ensure_ascii=False'),
        ('lambda pairs: list(pairs)', 'lambda pairs: dict(pairs)',
         'lambda pairs: list(reversed(pairs))', 'lambda pairs: list(pairs[:-1])')),
    "binary-compression": (
        ('31', '15', '-15', '8'), ('-15', '15', '31', '8'),
        ('compressor.flush(zlib.Z_FINISH)', 'b""',
         'compressor.flush(zlib.Z_SYNC_FLUSH)', 'compressor.flush(zlib.Z_FULL_FLUSH)')),
}


def render(domain, choices):
    if domain not in DOMAINS or len(choices) != 3 or any(type(v) is not int or v not in range(4) for v in choices):
        raise ValueError("Native proposal outside the frozen three-locus grammar")
    a, b, c = [variants[value] for variants, value in zip(VARIANTS[domain], choices)]
    if domain == "relational-sql":
        return f'''import sqlite3
def run(operation, data):
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE items(label TEXT, value INTEGER)")
        connection.executemany("INSERT INTO items VALUES (?, ?)", data["rows"])
        if operation == "a":
            return connection.execute("SELECT {a} FROM items").fetchone()[0]
        if operation == "b":
            return connection.execute("SELECT COUNT(*) FROM items WHERE {b}", (data["threshold"],)).fetchone()[0]
        return connection.execute("SELECT label FROM items ORDER BY {c} LIMIT 1").fetchone()[0]
    finally:
        connection.close()
'''
    if domain == "regular-expressions":
        return f'''import re
def run(operation, data):
    pattern = r"[A-Za-z]+(?:-[A-Za-z]+)*"
    if operation == "a":
        return {a}
    if operation == "b":
        return {b}
    return re.sub(re.escape(data["token"]), lambda match: "X", data["text"], count={c})
'''
    if domain == "structured-json":
        return f'''import json
from decimal import Decimal
def run(operation, data):
    if operation == "a":
        return str(json.loads(data["payload"], parse_float={a}))
    if operation == "b":
        return json.dumps(json.loads(data["payload"]), {b})
    return json.loads(data["payload"], object_pairs_hook={c})
'''
    return f'''import zlib
import base64
def run(operation, data):
    value = base64.b64decode(data["encoded"])
    if operation == "a":
        return zlib.decompress(value, wbits={a}).hex()
    if operation == "b":
        return zlib.decompress(value, wbits={b}).hex()
    compressor = zlib.compressobj()
    return (compressor.compress(value) + {c}).hex()
'''


def cases(domain):
    """Balanced 8/6/6 operation coverage, independent of controller thresholds."""
    rows = []
    for index in range(8):
        if domain == "relational-sql":
            values = [index + 1, 3 * index + 4, -index - 2]
            data = {"rows": [["z", value] for value in values]}
            expected = sum(values)
        elif domain == "regular-expressions":
            text = ("alpha-beta", "Gamma", "word-word", "Abc")[index] if index < 4 else (
                "7alpha", "alpha7", "beta gamma", "-alpha-")[index - 4]
            data, expected = {"text": text}, index < 4
        elif domain == "structured-json":
            value = str(index + 2) + ".123456789012345678901"
            data, expected = {"payload": value}, value
        else:
            value = ("gzip-value-" + str(index) + "-" + "x" * (index + 1)).encode()
            data = {"encoded": base64.b64encode(gzip.compress(value, mtime=0)).decode()}
            expected = value.hex()
        rows.append({"case_id": "a-" + str(index), "operation": "a", "data": data, "expected": expected})
    for index in range(6):
        if domain == "relational-sql":
            data = {"rows": [["z", index + 1], ["a", index + 2]], "threshold": index + 1}
            expected = 2
        elif domain == "regular-expressions":
            separator = (".", "|", "+")[index % 3]
            words = ["left" + str(index), "middle", "right"]
            data, expected = {"text": separator.join(words), "separator": separator}, words
        elif domain == "structured-json":
            value = ("é", "Ω", "漢")[index % 3]
            data = {"payload": '{"z":' + str(index) + ',"a":' + json.dumps(value, ensure_ascii=False) + '}'}
            expected = '{"a":' + json.dumps(value, ensure_ascii=False) + ',"z":' + str(index) + '}'
        else:
            value = ("raw-deflate-" + str(index) + "z" * (index + 2)).encode()
            compressor = zlib.compressobj(wbits=-15)
            encoded = compressor.compress(value) + compressor.flush()
            data, expected = {"encoded": base64.b64encode(encoded).decode()}, value.hex()
        rows.append({"case_id": "b-" + str(index), "operation": "b", "data": data, "expected": expected})
    for index in range(6):
        if domain == "relational-sql":
            data = {"rows": [["z", index], ["a", index + 3]]}
            expected = "z"
        elif domain == "regular-expressions":
            token = ("$", ".", "|")[index % 3]
            text = "a" + token + "b" + token + "c" + str(index)
            data, expected = {"text": text, "token": token}, text.replace(token, "X", 1)
        elif domain == "structured-json":
            data = {"payload": '{"k":' + str(index) + ',"k":' + str(index + 1) + '}'}
            expected = [["k", index], ["k", index + 1]]
        else:
            value = ("complete-stream-" + str(index) + "abc" * (index + 1)).encode()
            data, expected = {"encoded": base64.b64encode(value).decode()}, value.hex()
        rows.append({"case_id": "c-" + str(index), "operation": "c", "data": data, "expected": expected})
    return tuple(rows)


TASKS = tuple(json.loads((HERE / "NATIVE_TASKS.json").read_text()))


def runtime_versions():
    return {"python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
            "zlib_compile": zlib.ZLIB_VERSION, "zlib_runtime": zlib.ZLIB_RUNTIME_VERSION,
            "python_executable_sha256": digest_bytes(Path(sys.executable).read_bytes())}


def evaluate(task, choices):
    source = render(task["domain"], choices)
    payload = {"operations": [{"operation": case["operation"], "data": case["data"]} for case in task["cases"]]}
    with tempfile.TemporaryDirectory(prefix="v29-native-") as directory:
        path = Path(directory) / "proposal.py"
        path.write_text(source)
        result = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(path)], input=json.dumps(payload),
                                capture_output=True, text=True, cwd=directory,
                                env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=5)
    if result.returncode:
        raise RuntimeError("V29 native instrument failed: " + result.stderr[-1000:])
    observed = json.loads(result.stdout)
    if len(observed) != len(task["cases"]):
        raise ValueError("Incomplete native results")
    passed = []
    for case, output in zip(task["cases"], observed):
        value = output.get("value")
        if task["domain"] == "binary-compression" and case["operation"] == "c" and output.get("ok"):
            try:
                value = zlib.decompress(bytes.fromhex(value)).hex()
            except (ValueError, zlib.error):
                value = None
        passed.append(bool(output.get("ok")) and value == case["expected"])
    receipt = {"accepted": True, "source_sha256": digest_bytes(source.encode()),
               "task_sha256": digest(task), "native_source_executed": True,
               "runtime_kernel": task["domain"], "observed": observed, "passed": passed,
               "quality_milli": sum(passed) * 1000 // len(passed)}
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def calibration():
    rows = []
    for task in TASKS:
        reference, seeded = evaluate(task, (0, 0, 0)), evaluate(task, (1, 1, 1))
        if reference["quality_milli"] != 1000 or seeded["quality_milli"] == 1000:
            raise ValueError("Reference/seed semantic calibration failed")
        rows.append({"domain": task["domain"], "reference": reference, "seeded": seeded})
    return {"scope": "REFERENCE_AND_SEED_ONLY_NO_CONTROLLER_TRANSFER", "controller_executed": False,
            "tasks": rows, "population_sha256": digest(TASKS), "runtime_versions": runtime_versions()}


class Host:
    def __init__(self, task, seeded):
        self.task, self.seeded = task, seeded
        self.forbidden_tokens = [task["domain"]]
    def row(self, choices):
        source = render(self.task["domain"], choices)
        return {"candidate": {"choices": list(choices)}, "source_sha256": digest_bytes(source.encode()),
                "structure_sha256": structure(source)}
    def root(self):
        return {**self.row((1, 1, 1)), "quality_milli": self.seeded["quality_milli"]}
    def children(self, candidate, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        parent, rows = candidate["choices"], []
        for axis in range(3):
            for value in range(4):
                if value != parent[axis]:
                    child = list(parent)
                    child[axis] = value
                    rows.append(self.row(child))
        return tuple(rows)  # Declared source-region order, then numeric variant; no outcomes.
    def action(self, row):
        axes = ["region-" + str(i) for i, value in enumerate(row["candidate"]["choices"]) if value != 1]
        return {"family": "native-algorithmic-repair", "target_axes": axes, "changed_regions": axes,
                "mechanisms": axes or ["seeded-root"], "structure_sha256": row["structure_sha256"]}
    def evaluate(self, row):
        return evaluate(self.task, row["candidate"]["choices"])
