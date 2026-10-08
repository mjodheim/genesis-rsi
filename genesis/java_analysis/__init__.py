"""G11 read-only Java structural analysis, isolated from benchmark evaluation."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

_HELPER = Path(__file__).with_name('GenesisJavaAnalyzer.java')


def analyze(source: Path, *, java: Path, javac: Path) -> dict:
    """Parse a Java source into compiler AST nodes with exact source offsets.

    No human patches or benchmark data are passed to the analyzer. Java 11+ required.
    """
    source = Path(source).resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix='genesis-g11-') as temp:
        subprocess.run([str(javac), '-d', temp, str(_HELPER)], check=True, capture_output=True, text=True, timeout=30)
        result = subprocess.run([str(java), '-cp', temp, 'GenesisJavaAnalyzer', str(source)], check=True, capture_output=True, text=True, timeout=30)
    payload = json.loads(result.stdout)
    payload['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    payload['analyzer_sha256'] = hashlib.sha256(_HELPER.read_bytes()).hexdigest()
    return payload
