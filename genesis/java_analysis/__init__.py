"""G11 read-only Java compiler-derived understanding, no benchmark answers.

The compiler provides AST and *partial* symbol/typing information. Branch
ranges are structural, not a complete CFG; accesses are not full def-use.
Unresolved types, missing dependencies, and diagnostics are never hidden.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Sequence

_HELPER = Path(__file__).with_name("GenesisJavaAnalyzer.java")
SCHEMA = "genesis-java-understanding-v2"


def analyze(
    source: Path,
    *,
    java: Path,
    javac: Path,
    classpath: str | Sequence[str] = (),
) -> dict:
    """Analyze only the specified source, with no patch or test material.

    The source must be a trusted, preselected buggy tree file; invoking the
    Java compiler performs parsing/analysis only, with processors disabled.
    """
    source = Path(source).resolve(strict=True)
    if not source.is_file() or source.suffix != ".java":
        raise ValueError("source must be a Java file")
    if source.stat().st_size > 512_000:
        raise ValueError("source file exceeds analysis limit")
    cp = classpath if isinstance(classpath, str) else os.pathsep.join(map(str, classpath))
    with tempfile.TemporaryDirectory(prefix="genesis-g11-") as temp:
        subprocess.run(
            [str(javac), "-proc:none", "-d", temp, str(_HELPER)],
            check=True, capture_output=True, text=True, timeout=30,
        )
        command = [str(java), "-cp", temp, "GenesisJavaAnalyzer", str(source)]
        if cp:
            command.append(cp)
        result = subprocess.run(
            command, check=True, capture_output=True, text=True, timeout=60,
        )
    payload = json.loads(result.stdout)
    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected Java analyzer schema")
    payload["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    payload["analyzer_sha256"] = hashlib.sha256(_HELPER.read_bytes()).hexdigest()
    payload["offset_unit"] = "utf16_code_units"
    return payload
