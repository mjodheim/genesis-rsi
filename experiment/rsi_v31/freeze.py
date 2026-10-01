"""Prospective full scientific commitment of archive engineering."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v30 import campaign as v30, freeze as v30_freeze
from experiment.rsi_v31 import bank, engine, programs

HERE = ROOT / "experiment/rsi_v31"
PATH = HERE / "V31_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    inherited = json.loads(v30_freeze.PATH.read_text())
    paths = {ROOT / path for path in inherited["inputs"]}
    paths.add(v30_freeze.PATH)
    paths.update(path for path in v30.ATTEMPT.parent.iterdir() if path.is_file())
    paths.update(path for path in HERE.rglob("*") if path.is_file() and "__pycache__" not in path.parts
                 and path != PATH and path.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v31.py", ROOT / "docs/IP_REVIEWS/V31_ARCHIVE_AND_L10_HANDOFF_REVIEW.md"))
    return sorted(paths)


def build():
    if PATH.exists() or (ROOT / "results/rsi-v31/archive-20261001/V31_ATTEMPT.json").exists():
        raise ValueError("Never replace a freeze or consumed attempt")
    previous = v30.check(require_result=True)
    if not previous["v30_l8_positive"]:
        raise ValueError("The qualified L8 predecessor is required")
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {"schema": "mira-genesis-v31-archive-freeze-v1", "apparatus_commit": commit,
             "inputs": manifest, "bank_sha256": digest([bank.stream(seed) for seed in bank.FRESH_SEEDS]),
             "caps": engine.CAPS.__dict__, "arms": engine.ARMS, "root_evaluations_per_task": 1,
             "python_version": sys.version.split()[0], "parent_policy_sha256": programs.PARENT_SHA256,
             "previous_l8": previous, "track": "B", "fresh_consumed_before_freeze": False,
             "scientific_external_model_calls": 0, "l9_open_ended_passed": False,
             "l10_independent_passed": False}
    value["freeze_sha256"] = digest(value)
    write_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("schema") != "mira-genesis-v31-archive-freeze-v1" or value.get("freeze_sha256") != digest(
            {key: item for key, item in value.items() if key != "freeze_sha256"}):
        raise ValueError("Altered V31 freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V31 freeze must be committed before execution")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Apparatus ancestry was lost")
    if set(value["inputs"]) != {path.relative_to(ROOT).as_posix() for path in inputs()}:
        raise ValueError("Incomplete V31 manifest")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(
                git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen input changed: " + relative)
    if (value["bank_sha256"] != digest([bank.stream(seed) for seed in bank.FRESH_SEEDS])
            or value["caps"] != engine.CAPS.__dict__ or tuple(value["arms"]) != engine.ARMS
            or value["root_evaluations_per_task"] != 1
            or value["parent_policy_sha256"] != digest_bytes(programs.parent().encode())
            or value["track"] != "B" or value["scientific_external_model_calls"] != 0
            or value["fresh_consumed_before_freeze"] is not False
            or value["l9_open_ended_passed"] is not False or value["l10_independent_passed"] is not False):
        raise ValueError("Frozen authority, scope, parent, population or costs changed")
    return True


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
