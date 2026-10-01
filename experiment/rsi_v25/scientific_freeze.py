"""Full committed V25 scientific freeze, distinct from the old toy commitment."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import HERE, ROOT, digest, digest_bytes, write_json
from experiment.rsi_v25.executable_family import G1_SHA256, G2_SHA256, universe
from experiment.rsi_v25.native_transfer import TASKS, TRANSFER_CAPS
from experiment.rsi_v25.executable_meta import ARMS, META_CAPS
from experiment.rsi_v25.l4_history_retention import REFERENCE, TRANSCRIPTS
from experiment.rsi_v25.build_l5_freeze import preserved_v24_files

FREEZE_PATH = HERE / "V25_SCIENTIFIC_FREEZE.json"
SCHEMA = "mira-genesis-rsi-v25-full-scientific-freeze-v1"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()


def input_paths():
    paths = set()
    for directory in (HERE, ROOT / "experiment/rsi_v23"):
        paths.update(p for p in directory.rglob("*")
                     if p.is_file() and p.suffix in (".py", ".md", ".json", ".java", ".js")
                     and "__pycache__" not in p.parts and p != FREEZE_PATH)
    paths.update(ROOT / "experiment/rsi_v22/policies" / file
                 for file in ("g1_search_policy.py", "g2_search_policy.py"))
    paths.update((REFERENCE, *TRANSCRIPTS))
    paths.update(p for p in (ROOT / "results/rsi-v24/l5-20260928").rglob("*") if p.is_file())
    paths.update((ROOT / "AGENTS.md", ROOT / "IP_ASSET_REGISTER.md",
                  ROOT / "docs/IP_REVIEWS/V25_EXECUTABLE_L5_PUBLICATION_REVIEW.md",
                  ROOT / "docs/IP_PUBLICATION_POLICY.md",
                  ROOT / "docs/AI_ASSISTED_DEVELOPMENT_PROVENANCE.md",
                  ROOT / "AUTHORS.md"))
    return tuple(sorted(paths))


def runtime_versions():
    def first_line(command):
        result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=10)
        return (result.stdout + result.stderr).splitlines()[0]
    return {"python": sys.version.split()[0],
            "java": first_line(["java", "-version"]),
            "javac": first_line(["java", "com.sun.tools.javac.Main", "-version"]),
            "node": first_line(["node", "--version"])}


def build():
    if FREEZE_PATH.exists():
        raise ValueError("A scientific freeze already exists; never overwrite it")
    preserved_v24_files()
    commit = git("rev-parse", "HEAD")
    tracked = set(git("ls-files").splitlines())
    manifest = {}
    for path in input_paths():
        relative = path.relative_to(ROOT).as_posix()
        if relative not in tracked:
            raise ValueError(f"Scientific input is not committed: {relative}")
        committed = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT)
        if committed != path.read_bytes():
            raise ValueError(f"Scientific input differs from committed bytes: {relative}")
        manifest[relative] = digest_bytes(committed)
    freeze = {"schema": SCHEMA, "scope": "FULL_SCIENTIFIC_APPARATUS_BEFORE_CANONICAL_SELECTION",
              "apparatus_commit": commit, "inputs": manifest,
              "g1_sha256": G1_SHA256, "g2_sha256": G2_SHA256,
              "candidate_universe_sha256": digest(universe()), "candidate_count": len(universe()),
              "new_native_population_sha256": digest(TASKS), "native_task_count": len(TASKS),
              "canonical_arms": list(ARMS), "meta_caps": META_CAPS.__dict__,
              "transfer_caps": TRANSFER_CAPS.__dict__, "runtime_versions": runtime_versions(),
              "track": "A", "scientific_external_model_calls": 0,
              "holdout_candidates_executed_at_freeze": False,
              "canonical_output": "results/rsi-v25/executable-20261001/V25_ATTEMPT.json",
              "negative_preservation_required": True}
    freeze["freeze_sha256"] = digest(freeze)
    write_json(FREEZE_PATH, freeze)
    return freeze


def verify(freeze):
    expected = freeze.get("freeze_sha256")
    if freeze.get("schema") != SCHEMA or expected != digest(
            {k: v for k, v in freeze.items() if k != "freeze_sha256"}):
        raise ValueError("Malformed or altered scientific freeze")
    preserved_v24_files()
    commit = freeze["apparatus_commit"]
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=ROOT,
                      capture_output=True, check=False).returncode:
        raise ValueError("Apparatus commit is not preserved in current ancestry")
    expected_paths = {path.relative_to(ROOT).as_posix() for path in input_paths()}
    if set(freeze["inputs"]) != expected_paths:
        raise ValueError("Scientific freeze omits or adds an apparatus input")
    for relative, sha in freeze["inputs"].items():
        path = ROOT / relative
        if digest_bytes(path.read_bytes()) != sha:
            raise ValueError(f"Frozen working bytes changed: {relative}")
        committed = subprocess.check_output(["git", "show", f"{commit}:{relative}"], cwd=ROOT)
        if digest_bytes(committed) != sha:
            raise ValueError(f"Input identity is not in preserved apparatus commit: {relative}")
    if (freeze["candidate_universe_sha256"] != digest(universe())
            or freeze["new_native_population_sha256"] != digest(TASKS)
            or freeze["g1_sha256"] != G1_SHA256 or freeze["g2_sha256"] != G2_SHA256
            or freeze["meta_caps"] != META_CAPS.__dict__
            or freeze["transfer_caps"] != TRANSFER_CAPS.__dict__
            or freeze["canonical_arms"] != list(ARMS)):
        raise ValueError("Frozen executable identities or external rules disagree")
    return True


def committed_freeze():
    freeze = json.loads(FREEZE_PATH.read_text())
    committed = subprocess.check_output(
        ["git", "show", f"HEAD:{FREEZE_PATH.relative_to(ROOT).as_posix()}"], cwd=ROOT)
    if committed != FREEZE_PATH.read_bytes():
        raise ValueError("Full scientific freeze must be committed before execution")
    verify(freeze)
    return freeze


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    result = committed_freeze() if args.verify else build()
    print(json.dumps({k: result[k] for k in ("schema", "apparatus_commit", "freeze_sha256")}, indent=2))


if __name__ == "__main__":
    main()
