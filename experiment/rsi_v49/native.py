"""Coupled native pipelines; references and candidate execution are separate."""
import base64
import hashlib
import itertools
import json
import random
import subprocess
import sys
import tempfile
import zlib
from functools import lru_cache
from pathlib import Path

from experiment.rsi_v25.commitments import canonical, digest, digest_bytes
from experiment.rsi_v35.native import WORKER, runtime

DOMAINS = ("punctuation", "unicode", "json-text", "base64-text")
WITNESSES = ("Ab..::33\\\"", "éΩ9!", '{"a":1,"b":[2]}', "YmluYXJ5AA==")
TEMPLATE = '''import sqlite3
import re
import json
import zlib
import hashlib
def run(operation, data):
    text = data["text"]
    visits = processed = 0
    connection = None
    try:
        for choice in OPS:
            raw = text.encode("utf-8")
            if choice == 1:
                if connection is None:
                    connection = sqlite3.connect(":memory:")
                transformed = connection.execute("SELECT hex(?)", (raw,)).fetchone()[0].encode("ascii")
            elif choice == 2:
                runs = re.finditer(r"(.)\\1*", text, flags=re.DOTALL)
                transformed = "".join(str(len(m.group())) + ":" + str(ord(m.group()[0])) + ";" for m in runs).encode("ascii")
            elif choice == 3:
                transformed = json.dumps(text, ensure_ascii=True, separators=(",", ":")).encode("ascii")
            else:
                transformed = zlib.compress(raw, level=6)
            visits += 1
            processed += len(raw) + len(transformed)
            text = hashlib.sha256(transformed).hexdigest()
        return {"value": text, "primitive_visits": visits, "transformed_bytes": processed}
    finally:
        if connection is not None:
            connection.close()
'''


def genome(domain, ops):
    if domain not in DOMAINS or type(ops) not in (list, tuple) or any(type(op) is not int or op not in (1, 2, 3, 4) for op in ops):
        raise ValueError("Invalid coupled native body")
    return {"domain": domain, "ops": list(ops)}


def validate(value):
    if type(value) is not dict or set(value) != {"domain", "ops"} or genome(value["domain"], value["ops"]) != value:
        raise ValueError("Noncanonical coupled native body")
    return value


def render(value):
    return "OPS = " + repr(tuple(validate(value)["ops"])) + "\n" + TEMPLATE


def descriptor(value):
    return {"source_sha256": digest_bytes(render(value).encode()), "structure_sha256": digest(validate(value))}


def quote_ascii(text):
    escapes = {'"': '\\"', "\\": "\\\\", "\b": "\\b", "\f": "\\f", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    result = []
    for char in text:
        number = ord(char)
        if char in escapes:
            result.append(escapes[char])
        elif number < 32 or number > 126:
            if number <= 65535:
                result.append("\\u%04x" % number)
            else:
                number -= 65536
                result.append("\\u%04x\\u%04x" % (55296 + (number >> 10), 56320 + (number & 1023)))
        else:
            result.append(char)
    return ('"' + "".join(result) + '"').encode("ascii")


def reference(ops, text):
    visits = processed = 0
    for choice in ops:
        raw = text.encode("utf-8")
        if choice == 1:
            transformed = raw.hex().upper().encode("ascii")
        elif choice == 2:
            transformed = "".join(str(sum(1 for _ in group)) + ":" + str(ord(char)) + ";" for char, group in itertools.groupby(text)).encode("ascii")
        elif choice == 3:
            transformed = quote_ascii(text)
        else:
            compressor = zlib.compressobj(level=6, wbits=15)
            transformed = compressor.compress(raw) + compressor.flush()
        visits += 1
        processed += len(raw) + len(transformed)
        text = hashlib.sha256(transformed).hexdigest()
    return {"value": text, "primitive_visits": visits, "transformed_bytes": processed}


@lru_cache(maxsize=8192)
def development_program(domain, ops):
    functions = {}
    exec(compile(render(genome(domain, ops)), "<coupled-native-development>", "exec"), functions)
    return functions["run"]


def execute(value, texts, *, isolated):
    validate(value)
    operations = [{"operation": "pipeline", "data": {"text": text}} for text in texts]
    if isolated:
        with tempfile.TemporaryDirectory(prefix="v49-native-") as directory:
            path = Path(directory) / "body.py"
            path.write_text(render(value))
            try:
                result = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(path)],
                    input=json.dumps({"operations": operations}), text=True, capture_output=True,
                    cwd=directory, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=5)
            except subprocess.TimeoutExpired as error:
                # The ledger's pending reservation consumes the attempt. No retry,
                # invented completed work meter, or successful campaign completion.
                raise RuntimeError("Native instrument timeout; quarantine full reservation") from error
        if result.returncode or len(result.stdout.encode()) > 1024 * 1024:
            raise RuntimeError("Native instrument failed; quarantine full reservation")
        outputs = json.loads(result.stdout)
    else:
        run = development_program(value["domain"], tuple(value["ops"]))
        outputs = []
        for case in operations:
            try:
                outputs.append({"ok": True, "value": run(case["operation"], case["data"])})
            except Exception as error:
                outputs.append({"ok": False, "error": type(error).__name__})
    if type(outputs) is not list or len(outputs) != len(texts):
        raise ValueError("Incomplete native dataflow output")
    return outputs


def receipt(task, value, outputs, *, isolated):
    if len(outputs) != len(task["inputs"]) + len(WITNESSES):
        raise ValueError("Omitted task or diagnostic context")
    count = len(task["inputs"])
    matched = sum(row.get("ok") is True and row["value"]["value"] == expected for row, expected in zip(outputs[:count], task["answers"]))
    good = all(row.get("ok") is True for row in outputs)
    diagnostic = [row.get("value", {}).get("value") for row in outputs[count:]]
    return {"accepted": good, **descriptor(value), "evaluator_task_sha256": digest(task),
        "native_source_executed": True, "isolated": isolated, "outputs": outputs,
        "output_sha256": digest(outputs), "matched_contexts": matched,
        "quality_milli": matched * 1000 // count, "semantic_sha256": digest(diagnostic) if good else None,
        "primitive_visits": sum(row["value"]["primitive_visits"] for row in outputs if row.get("ok") is True),
        "transformed_bytes": sum(row["value"]["transformed_bytes"] for row in outputs if row.get("ok") is True),
        "instrument_failed": not good}


def evaluate(task, value, *, isolated=True):
    if value["domain"] != task["domain"] or len(value["ops"]) > task["slots"]:
        raise ValueError("Outside admitted pipeline interface")
    return receipt(task, value, execute(value, [*task["inputs"], *WITNESSES], isolated=isolated), isolated=isolated)


def contexts(seed, domain, epoch, position, count=4):
    rng = random.Random(digest(["v49-contexts", seed, domain, epoch, position]))
    rows = []
    for i in range(count):
        number = rng.randrange(1, 1000000)
        if domain == "punctuation":
            text = f"Ab{number}..::[{i}]\\\""
        elif domain == "unicode":
            text = f"éΩ🙂\t{number}\n{i}"
        elif domain == "json-text":
            text = json.dumps({"z": number, "a": [i, "é"]}, ensure_ascii=False)
        elif domain == "base64-text":
            text = base64.b64encode((str(number) + "\x00" + str(i)).encode()).decode()
        else:
            raise ValueError("Unknown input family")
        rows.append(text)
    return rows
