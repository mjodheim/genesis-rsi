"""Capture unique du diagnostic budget 16 du CIRCUIT2.

Lance une fois, en sous-processus, scripts/circuit2_budget16_diagnostic.py
(cwd à la racine, timeout 600 s, aucun accès réseau) et écrit stdout et stderr
dans deux fichiers distincts de results/, sans jamais réécrire un fichier
existant. Ne calcule rien et ne fabrique rien : un stdout vide est écrit tel quel.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_NAME = "circuit2_budget16_diagnostic.py"
STDOUT_NAME = "circuit2_budget16_stdout.json"
STDERR_NAME = "circuit2_budget16_stderr.txt"
TIMEOUT = 600
TIMEOUT_CODE = 124


class CaptureError(Exception):
    """Refus de capture (écrasement ou écriture hors de results/)."""


def _results_dir(root):
    root = Path(root).resolve()
    results = (root / "results").resolve()
    if results != root / "results":
        raise CaptureError("results/ doit être un dossier réel à la racine du dépôt")
    return results


def _target(results, name):
    if not name or Path(name).name != name or name in (".", ".."):
        raise CaptureError(f"nom de fichier invalide : {name!r}")
    target = (results / name).resolve()
    if target.parent != results:
        raise CaptureError(f"écriture hors de results/ refusée : {name!r}")
    return target


def _data(value):
    if value is None:
        return b""
    if isinstance(value, str):
        return value.encode("utf-8")
    return value


def _write_new(target, content):
    with open(target, "xb") as handle:
        handle.write(content)


def main(argv=None, root=None, runner=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    root = Path(root) if root is not None else ROOT
    runner = runner or subprocess.run
    try:
        results = _results_dir(root)
        out = _target(results, STDOUT_NAME)
        err = _target(results, STDERR_NAME)
        for target in (out, err):
            if target.exists():
                raise CaptureError(f"fichier existant, pas de réécriture : {target.name}")
    except CaptureError as exc:
        print(f"Refus : {exc}", file=sys.stderr)
        return 2
    script = root / "scripts" / SCRIPT_NAME
    try:
        proc = runner(
            [sys.executable, str(script)],
            cwd=str(root),
            capture_output=True,
            timeout=TIMEOUT,
            check=False,
        )
        code = proc.returncode
        stdout, stderr = _data(proc.stdout), _data(proc.stderr)
    except subprocess.TimeoutExpired as exc:
        code = TIMEOUT_CODE
        stdout, stderr = _data(exc.stdout), _data(exc.stderr)
    try:
        results.mkdir(exist_ok=True)
        _write_new(out, stdout)
        _write_new(err, stderr)
    except FileExistsError as exc:
        print(f"Refus : fichier existant, pas de réécriture : {Path(exc.filename).name}", file=sys.stderr)
        return 2
    return code


if __name__ == "__main__":
    sys.exit(main())
