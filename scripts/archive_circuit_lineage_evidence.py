#!/usr/bin/env python3
"""Archive de preuves de lignée de circuit (lecture seule de la trace).

Lit une trace JSON au format de sortie de run_circuit2_campaign
(arms -> liste de runs -> generations) et écrit une archive en création
exclusive (mode 'x') sous results/ ou experiment/. Aucune entrée n'est
modifiée.

Le script n'émet ni gain, ni verdict, ni succès. Toute donnée absente de la
trace est listée dans le champ "absent" et n'est jamais reconstruite.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

SCHEMA = "circuit_lineage_evidence_archive/v1"
ALLOWED_DIRS = ("results", "experiment")
PROVENANCE_KEYS = ("plan_digest", "machinery_commit", "scale", "seeds", "generations")
RUN_PROCEDURE_KEYS = ("procedure_initial", "procedure_final")
GENERATION_KEYS = ("spend", "spent", "limit", "procedure_digest", "transmission")
LIMITS = (
    "Les sorties actuelles de adjudicate_circuit_lineage.py ne contiennent pas "
    "les procédures complètes, seulement des empreintes : limite de la chaîne "
    "d'évidence. Les procédures complètes ne sont conservées ici que si la "
    "trace d'entrée les porte (procedure_initial, procedure_final).",
    "Cette archive ne contient ni gain, ni verdict, ni succès.",
)
REPO_ROOT = Path(__file__).resolve().parent.parent


class ArchiveError(Exception):
    """Entrée invalide ou sortie refusée."""


def check_output_path(output, root=None):
    """Retourne le chemin résolu si output est sous results/ ou experiment/."""
    base = Path(root).resolve() if root is not None else REPO_ROOT
    target = Path(output).resolve()
    for name in ALLOWED_DIRS:
        allowed = base / name
        if allowed.resolve() != allowed:
            continue
        if allowed in target.parents:
            return target
    raise ArchiveError(
        f"sortie refusée (hors results/ et experiment/) : {output}"
    )


def _copy_fields(source, keys, path, dest, absent):
    for key in keys:
        if key in source:
            dest[key] = copy.deepcopy(source[key])
        else:
            absent.append({"path": f"{path}.{key}", "field": key})


def _archive_generation(gen, index, path, absent):
    entry = {"generation_index": index}
    if not isinstance(gen, dict):
        absent.append({"path": path, "field": "generation"})
        return entry
    _copy_fields(gen, GENERATION_KEYS, path, entry, absent)
    return entry


def _archive_run(run, index, path, absent):
    entry = {"run_index": index}
    if not isinstance(run, dict):
        absent.append({"path": path, "field": "run"})
        return entry
    _copy_fields(run, ("seed",) + RUN_PROCEDURE_KEYS, path, entry, absent)
    gens = run.get("generations")
    if not isinstance(gens, list):
        absent.append({"path": f"{path}.generations", "field": "generations"})
        return entry
    entry["generations"] = [
        _archive_generation(gen, i, f"{path}.generations[{i}]", absent)
        for i, gen in enumerate(gens)
    ]
    return entry


def build_archive(trace, source_name, source_sha256):
    if not isinstance(trace, dict):
        raise ArchiveError("la trace doit être un objet JSON")
    arms = trace.get("arms")
    if not isinstance(arms, dict):
        raise ArchiveError("champ 'arms' absent ou n'est pas un objet")
    absent = []
    provenance = {}
    _copy_fields(trace, PROVENANCE_KEYS, "$", provenance, absent)
    arms_out = {}
    for arm, runs in arms.items():
        arm_path = f"$.arms[{json.dumps(arm)}]"
        if not isinstance(runs, list):
            absent.append({"path": arm_path, "field": "runs"})
            continue
        arms_out[arm] = [
            _archive_run(run, i, f"{arm_path}[{i}]", absent)
            for i, run in enumerate(runs)
        ]
    return {
        "schema": SCHEMA,
        "source": {"name": source_name, "sha256": source_sha256},
        "provenance": provenance,
        "limits": list(LIMITS),
        "arms": arms_out,
        "absent": absent,
    }


def archive(input_path, output_path, root=None):
    source = Path(input_path)
    target = check_output_path(output_path, root)
    if target == source.resolve():
        raise ArchiveError("la sortie ne peut pas être le fichier d'entrée")
    raw = source.read_bytes()
    try:
        trace = json.loads(raw)
    except ValueError as exc:
        raise ArchiveError(f"trace JSON invalide : {exc}") from exc
    result = build_archive(trace, source.name, hashlib.sha256(raw).hexdigest())
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(target, "x", encoding="utf-8") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise ArchiveError(f"sortie existante, écrasement refusé : {target}") from exc
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description="Archive des preuves de lignée de circuit.")
    parser.add_argument("trace", help="trace JSON existante (lecture seule)")
    parser.add_argument("output", help="archive à créer sous results/ ou experiment/")
    args = parser.parse_args(argv)
    try:
        target = archive(args.trace, args.output)
    except (ArchiveError, OSError) as exc:
        print(f"erreur : {exc}", file=sys.stderr)
        return 2
    print(f"archive écrite : {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
