"""Lossless archived public calibration, never fresh scientific evidence."""
import gzip
import json
from pathlib import Path

from experiment.rsi_v25.commitments import digest_bytes
from experiment.rsi_v27.family import render

HISTORY = Path(__file__).with_name("development_history")


def load():
    manifest = json.loads((HISTORY / "PILOT_001_MANIFEST.json").read_text())
    archive = (HISTORY / "PILOT_001_CALIBRATION.json.gz").read_bytes()
    if digest_bytes(archive) != manifest["gzip_sha256"]:
        raise ValueError("Public development archive changed")
    raw = gzip.decompress(archive)
    if digest_bytes(raw) != manifest["raw_calibration_sha256"]:
        raise ValueError("Original public calibration bytes changed")
    result = json.loads(raw)
    for row in result["candidates"]:
        if digest_bytes(render(row["params"]).encode()) != row["source_sha256"]:
            raise ValueError("Public calibration no longer binds the executable policy family")
    return result
