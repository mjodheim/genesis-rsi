"""Durable single-assignment files: reserve once, then add a separate completion.

No file is overwritten. Link publication is atomic and refuses an existing path;
the file and directory are fsynced and the published bytes are read back. A hard
crash or missing completion remains visibly reserved, never a free new attempt.
"""
import gzip
import json
import os
import stat
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import canonical, digest, digest_bytes


def read_regular(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Evidence must be a regular file")
        return stream.read()


def publish_once(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".v32-publication-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # No replace/rename fallback: an existing reservation/result is terminal.
        os.link(temporary, path, follow_symlinks=False)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        if read_regular(path) != raw:
            raise ValueError("Durable publication read-back differs")
    finally:
        os.unlink(temporary)


def publish_json(path, value):
    publish_once(path, canonical(value) + b"\n")


def read_json(path):
    raw = read_regular(path)
    value = json.loads(raw)
    if raw != canonical(value) + b"\n":
        raise ValueError("Altered canonical JSON evidence bytes")
    return value


def complete(directory, record, verdict):
    directory = Path(directory)
    encoded = canonical(record) + b"\n"
    raw = gzip.compress(encoded, mtime=0)
    raw_path = directory / "V32_ATTEMPT_RAW.json.gz"
    if raw_path.exists() or raw_path.is_symlink():
        if read_regular(raw_path) != raw:
            raise ValueError("Previously preserved raw evidence differs")
    else:
        publish_once(raw_path, raw)
    publish_json(directory / "V32_FINAL_ADJUDICATION.json", verdict)
    # The completion receipt is written last and never mutates the reservation.
    receipt = {"schema": "mira-genesis-v32-completion-receipt-v1", "status": record["status"],
               "freeze_sha256": record["freeze_sha256"], "canonical_attempts": record["canonical_attempts"],
               "reservation_sha256": digest_bytes(read_regular(directory / "V32_RESERVATION.json")),
               "raw_filename": "V32_ATTEMPT_RAW.json.gz", "raw_sha256": digest_bytes(raw),
               "uncompressed_sha256": digest_bytes(encoded), "record_sha256": digest(record),
               "verdict_sha256": digest(verdict)}
    publish_json(directory / "V32_COMPLETION.json", receipt)
    restored, restored_verdict = read_complete(directory)
    if restored != record or restored_verdict != verdict:
        raise ValueError("Complete published evidence differs")


def read_complete(directory):
    directory = Path(directory)
    reservation = read_json(directory / "V32_RESERVATION.json")
    receipt = read_json(directory / "V32_COMPLETION.json")
    raw = read_regular(directory / "V32_ATTEMPT_RAW.json.gz")
    encoded = gzip.decompress(raw)
    record = json.loads(encoded)
    verdict = read_json(directory / "V32_FINAL_ADJUDICATION.json")
    if (reservation.get("schema") != "mira-genesis-v32-single-attempt-reservation-v1"
            or reservation.get("status") != "RESERVED"
            or receipt.get("schema") != "mira-genesis-v32-completion-receipt-v1"
            or receipt.get("raw_filename") != "V32_ATTEMPT_RAW.json.gz"
            or receipt.get("reservation_sha256") != digest_bytes(read_regular(directory / "V32_RESERVATION.json"))
            or receipt.get("raw_sha256") != digest_bytes(raw)
            or receipt.get("uncompressed_sha256") != digest_bytes(encoded)
            or receipt.get("record_sha256") != digest(record)
            or receipt.get("verdict_sha256") != digest(verdict)
            or receipt.get("status") != record.get("status")
            or any(receipt.get(key) != record.get(key) or reservation.get(key) != record.get(key)
                   for key in ("freeze_sha256", "canonical_attempts"))):
        raise ValueError("Altered reservation, raw evidence, verdict or completion receipt")
    return record, verdict
