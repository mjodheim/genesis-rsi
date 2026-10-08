"""G11 read-only Java compiler-derived understanding, no benchmark answers.

The compiler provides AST and *partial* symbol/typing information. Branch
ranges are structural, not a complete CFG; accesses are not full def-use.
Unresolved types, missing dependencies, and diagnostics are never hidden.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
import subprocess
import tempfile
from typing import Sequence

_HELPER = Path(__file__).with_name("GenesisJavaAnalyzer.java")
SCHEMA = "genesis-java-understanding-v2"

# This cache holds ONLY the trusted analyzer's compiled helper class, not
# parsed project sources, test outcomes, repaired files, or hidden oracles.
# One JVM compiler invocation per source is still required for semantics.
_CLASS_CACHE: dict[tuple[str, str], tempfile.TemporaryDirectory] = {}
_CLASS_CACHE_LOCK = threading.Lock()


def _compiled_analyzer_dir(javac: Path, helper_digest: str) -> str:
    key = (str(Path(javac).resolve()), helper_digest)
    with _CLASS_CACHE_LOCK:
        cached = _CLASS_CACHE.get(key)
        if cached is not None:
            return cached.name
        temp = tempfile.TemporaryDirectory(prefix="genesis-g11-analyzer-")
        try:
            subprocess.run(
                [str(javac), "-proc:none", "-d", temp.name, str(_HELPER)],
                check=True, capture_output=True, text=True, timeout=30,
            )
        except BaseException:
            temp.cleanup()
            raise
        _CLASS_CACHE[key] = temp
        return temp.name


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
    analyzer_digest = hashlib.sha256(_HELPER.read_bytes()).hexdigest()
    class_dir = _compiled_analyzer_dir(javac, analyzer_digest)
    command = [str(java), "-Xmx192m", "-cp", class_dir, "GenesisJavaAnalyzer", str(source)]
    if cp:
        command.append(cp)
    result = subprocess.run(
        command, check=True, capture_output=True, text=True, timeout=60,
    )
    payload = json.loads(result.stdout)
    if payload.get("schema") != SCHEMA:
        raise ValueError("unexpected Java analyzer schema")
    payload["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    payload["analyzer_sha256"] = analyzer_digest
    payload["offset_unit"] = "utf16_code_units"
    return payload
