#!/usr/bin/env python3
"""Lanceur de vérification des preuves committées du circuit 2.

Hors réseau, sans modèle, sans aucun nouveau test. Lance séparément trois
tests existants et rapporte pour chacun la sortie complète, le code de
retour et un verdict. Aucun artefact n'est créé ni régénéré ; le délai
éventuel de l'action run n'est pas contourné : un dépassement est rapporté
tel quel.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
PLAN_DIR = ROOT / "experiment" / "engine" / "CIRCUIT2"
WATCHED = (PLAN_DIR / "PLAN.json", PLAN_DIR / "EXECUTABLES.json")
TESTS = (
    "tests/test_circuit_adjudication_committed.py::test_replay_full_adjudication",
    "tests/test_circuit_adjudication_committed.py::test_full_provenance_matches_committed_adjudication",
    "tests/test_circuit2_negative_note.py::test_committed_full_provenance_note_matches_run",
)
PYTEST_OPTIONS = ("-q", "-rA", "-p", "no:cacheprovider")
FORBIDDEN = ("skipped", "deselected", "no tests ran", "error", "failed")


def current_head() -> str | None:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    head = done.stdout.strip()
    return head if done.returncode == 0 and head else None


def judge(returncode: int, output: str) -> list[str]:
    """Renvoie les motifs d'échec ; liste vide si le test est réussi."""
    reasons = []
    if returncode == 4:
        reasons.append("code 4 : test non collecté (identifiant introuvable ou usage invalide)")
    elif returncode == 5:
        reasons.append("code 5 : aucun test collecté")
    elif returncode != 0:
        reasons.append(f"code de retour {returncode} au lieu de 0")
    passed = len(re.findall(r"\bpassed\b", output))
    if passed != 1:
        reasons.append(f"occurrences de « passed » : attendu=1 obtenu={passed}")
    lowered = output.lower()
    for word in FORBIDDEN:
        if word in lowered:
            reasons.append(f"la sortie contient « {word} »")
    return reasons


def run_test(test_id: str) -> dict:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    command = [sys.executable, "-m", "pytest", test_id, *PYTEST_OPTIONS]
    try:
        done = subprocess.run(
            command, cwd=ROOT, env=env, capture_output=True, text=True,
            errors="replace", check=False,
        )
    except OSError as exc:
        return {
            "id": test_id,
            "returncode": None,
            "stdout": "",
            "stderr": str(exc),
            "reasons": [f"lancement impossible : {exc}"],
        }
    output = done.stdout + "\n" + done.stderr
    return {
        "id": test_id,
        "returncode": done.returncode,
        "stdout": done.stdout,
        "stderr": done.stderr,
        "reasons": judge(done.returncode, output),
    }


def main() -> int:
    head = current_head()
    print(f"HEAD courant : {head or 'indisponible (git rev-parse HEAD a échoué)'}")
    for path in WATCHED:
        state = "présent" if path.is_file() else "absent"
        print(f"{path.relative_to(ROOT).as_posix()} : {state}")
    sys.stdout.flush()
    results = []
    for test_id in TESTS:
        print(f"\n===== {test_id} =====", flush=True)
        result = run_test(test_id)
        print("--- stdout ---")
        print(result["stdout"])
        print("--- stderr ---")
        print(result["stderr"])
        print(f"code de retour : {result['returncode']}")
        ok = not result["reasons"]
        print(f"verdict : {'RÉUSSI' if ok else 'ÉCHEC'}")
        for reason in result["reasons"]:
            print(f"  motif : {reason}")
        sys.stdout.flush()
        results.append((test_id, ok))
    print("\n===== Récapitulatif =====")
    print(f"HEAD testé : {head or 'indisponible'}")
    for test_id, ok in results:
        print(f"{'RÉUSSI' if ok else 'ÉCHEC'} : {test_id}")
    all_ok = all(ok for _, ok in results)
    print(f"Résultat global : {'RÉUSSI' if all_ok else 'ÉCHEC'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
