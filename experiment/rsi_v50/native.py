"""Exact native free codecs; output compression is transport, not identity."""
import base64
import gzip
import itertools
import json
import re
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from experiment.rsi_v25.commitments import digest_bytes
from experiment.rsi_v35.native import WORKER, runtime
from experiment.rsi_v49.native import quote_ascii

TEXTS = ("🌱Ab..::33\\\"", "🌱éΩ🙂\t9\n", '🌱{"a":1,"b":[2]}', "🌱YmluYXJ5AA==")
TEMPLATE = r'''import base64
import sqlite3
import re
import json
import zlib
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
                text = connection.execute("SELECT hex(?)", (raw,)).fetchone()[0]
            elif choice == 2:
                text = "".join(str(len(m.group())) + ":" + str(ord(m.group()[0])) + ";" for m in re.finditer(r"(.)\1*", text, flags=re.DOTALL))
            elif choice == 3:
                text = json.dumps(text, ensure_ascii=True, separators=(",", ":"))
            else:
                compressor = zlib.compressobj(level=6, wbits=31)
                encoded = compressor.compress(raw) + compressor.flush()
                # Canonical gzip OS=unknown, stable across Python/platform headers.
                encoded = encoded[:9] + b"\xff" + encoded[10:]
                text = base64.b64encode(encoded).decode("ascii")
            visits += 1
            processed += len(raw) + len(text.encode("utf-8"))
        output = text.encode("utf-8")
        return {"wire": base64.b64encode(zlib.compress(output, level=6)).decode("ascii"),
                "output_bytes": len(output), "primitive_visits": visits,
                "encoder_interface_bytes": processed}
    finally:
        if connection is not None:
            connection.close()
'''


def word(value):
    if type(value) not in (list, tuple) or any(type(op) is not int or op not in (1, 2, 3, 4) for op in value):
        raise ValueError("Invalid exact codec word")
    return tuple(value)


def render(ops):
    return "OPS = " + repr(word(ops)) + "\n" + TEMPLATE


def source_sha(ops):
    return digest_bytes(render(ops).encode())


def classify(text):
    if not text:
        return None
    if re.fullmatch(r"(?:[0-9A-F]{2})+", text):
        return 1
    if re.fullmatch(r"(?:[1-9][0-9]*:[0-9]+;)+", text):
        return 2
    if text.startswith('"'):
        return 3
    if text.startswith("H4sI"):
        return 4
    return None


def inverse(choice, text):
    if classify(text) != choice:
        raise ValueError("Wrong native output language")
    if choice == 1:
        result = bytes.fromhex(text).decode("utf-8")
    elif choice == 2:
        chunks = []
        for piece in text[:-1].split(";"):
            count, ordinal = (int(v) for v in piece.split(":"))
            chunks.append(chr(ordinal) * count)
        result = "".join(chunks)
    elif choice == 3:
        result = json.loads(text)
        if type(result) is not str:
            raise ValueError("Not a JSON string codec")
    else:
        result = gzip.decompress(base64.b64decode(text, validate=True)).decode("utf-8")
    if not result:
        raise ValueError("The nonempty-text codec domain excludes empty results")
    return result


def decode(text):
    recovered = []
    while (choice := classify(text)) is not None:
        recovered.append(choice)
        text = inverse(choice, text)
    return tuple(reversed(recovered)), text


def reference(ops, text):
    ops = word(ops)
    if not text:
        raise ValueError("Empty input violates the model domain")
    visits = processed = 0
    for choice in ops:
        raw = text.encode("utf-8")
        if choice == 1:
            text = raw.hex().upper()
        elif choice == 2:
            text = "".join(str(sum(1 for _ in group)) + ":" + str(ord(char)) + ";" for char, group in itertools.groupby(text))
        elif choice == 3:
            text = quote_ascii(text).decode("ascii")
        else:
            encoded = gzip.compress(raw, compresslevel=6, mtime=0)
            encoded = encoded[:9] + b"\xff" + encoded[10:]
            text = base64.b64encode(encoded).decode("ascii")
        visits += 1
        processed += len(raw) + len(text.encode("utf-8"))
    return text, {"output_bytes": len(text.encode("utf-8")), "primitive_visits": visits,
                  "encoder_interface_bytes": processed}


def unpack(row):
    import zlib
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(base64.b64decode(row["wire"], validate=True), 2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024 or not decompressor.eof or decompressor.unused_data:
        raise ValueError("Outside fixed public-fixture transport bound")
    if len(raw) != row["output_bytes"]:
        raise ValueError("Altered native transport length")
    return raw.decode("utf-8")


@lru_cache(maxsize=1024)
def development_program(ops):
    functions = {}
    exec(compile(render(ops), "<public-free-codec-fixture>", "exec"), functions)
    return functions["run"]


def execute(ops, *, isolated=True):
    ops = word(ops)
    operations = [{"operation": "codec", "data": {"text": text}} for text in TEXTS]
    if isolated:
        with tempfile.TemporaryDirectory(prefix="v50-native-") as directory:
            source = Path(directory) / "body.py"
            source.write_text(render(ops))
            result = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(source)],
                input=json.dumps({"operations": operations}), text=True, capture_output=True,
                cwd=directory, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=5)
        if result.returncode or len(result.stdout.encode()) > 1024 * 1024:
            raise RuntimeError("Native instrument failed; consume full fixture reservation")
        rows = json.loads(result.stdout)
    else:
        run = development_program(ops)
        rows = [{"ok": True, "value": run("codec", {"text": text})} for text in TEXTS]
    if type(rows) is not list or len(rows) != len(TEXTS):
        raise ValueError("Omitted public fixture context")
    return rows


def validate_outputs(ops, rows):
    ops = word(ops)
    if len(rows) != len(TEXTS):
        raise ValueError("Omitted public fixture context")
    for text, row in zip(TEXTS, rows):
        if row.get("ok") is not True:
            raise ValueError("Native codec exception")
        output = unpack(row["value"])
        expected, meter = reference(ops, text)
        if output != expected or any(row["value"][key] != value for key, value in meter.items()):
            raise ValueError("Native output or actual work differs from independent reference")
        if decode(output) != (ops, text):
            raise ValueError("Native semantic word is not exactly recoverable")
    return True
