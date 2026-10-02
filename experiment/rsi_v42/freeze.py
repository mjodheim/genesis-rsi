"""Prospective V42 governance freeze; must be committed before any fresh task."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v33 import storage
from experiment.rsi_v35 import freeze as inherited
from experiment.rsi_v42 import bank, development, engine, programs

HERE = ROOT / "experiment/rsi_v42"
PATH = HERE / "V42_SCIENTIFIC_FREEZE.json"
RESULT_ROOT = ROOT / "results/rsi-v42/continuing-20261002"

LOCAL_INPUTS = (
    "bank.py", "programs.py", "engine.py", "development.py", "campaign.py",
    "freeze.py", "PROTOCOL.md", "DEVELOPMENT.json.gz", "DEVELOPMENT_RESERVATION.json",
)
EXTERNAL_INPUTS = (
    ROOT / "tests/test_rsi_v42.py",
    ROOT / "tests/test_rsi_v42_fresh.py",
)


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = [HERE / name for name in LOCAL_INPUTS]
    paths.extend(EXTERNAL_INPUTS)
    return sorted(paths)


def constants():
    return {
        "schema": "mira-genesis-v42-last-chance-continuing-freeze-v1",
        "bank_sha256": bank.population_sha256(),
        "fresh_seeds": list(bank.FRESH_SEEDS),
        "initial_epochs": bank.INITIAL_EPOCHS,
        "tasks_per_arm_first_prefix": sum(
            len(bank.stream(seed, epoch))
            for seed in bank.FRESH_SEEDS
            for epoch in range(bank.INITIAL_EPOCHS)
        ),
        "arms": list(engine.ARMS),
        "caps": engine.CAPS.__dict__,
        "max_charged_evaluations_per_task": engine.MAX_EVALUATIONS,
        "domain_introduction_order": list(programs.DOMAINS),
        "grammar_capacity_instructions": programs.MAX_STEPS,
        "parent_policy_sha256": programs.PARENT_SHA256,
        "root_evaluations_per_task": 1,
        "probe_evaluations_per_task": 2,
        "controller_calls_per_task": 1,
        "memory_policy": "last_chance_stagnation5_frontier_v1",
        "checkpoint_position": 3,
        "track": "B",
        "scientific_external_model_calls": 0,
        "fresh_consumed_before_freeze": False,
        "new_recursive_transition_established": False,
        "l9_open_ended_passed": False,
        "l10_independent_passed": False,
        "finite_prefix_cannot_establish_open_endedness": True,
    }


def build():
    if PATH.exists() or (RESULT_ROOT / "epoch-000/RESERVATION.json").exists():
        raise ValueError("Never replace a V42 freeze or consumed first epoch")
    development.verify(replay=True)
    inherited_value = json.loads(inherited.PATH.read_text())
    inherited.verify(inherited_value)
    commit = git("rev-parse", "HEAD").decode().strip()
    manifest = {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular V42 scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {
        **constants(),
        "apparatus_commit": commit,
        "inputs": manifest,
        "python_version": sys.version.split()[0],
        "inherited_v35_freeze_sha256": inherited_value["freeze_sha256"],
        "public_development_sha256": digest_bytes((HERE / "DEVELOPMENT.json.gz").read_bytes()),
    }
    value["freeze_sha256"] = digest(value)
    storage.publish_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    body = {key: item for key, item in value.items() if key != "freeze_sha256"}
    if value.get("freeze_sha256") != digest(body):
        raise ValueError("Altered V42 freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V42 freeze must be committed before fresh behavior")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("V42 apparatus ancestry was lost")
    if set(value["inputs"]) != {path.relative_to(ROOT).as_posix() for path in inputs()}:
        raise ValueError("Incomplete V42 input manifest")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if (path.is_symlink() or digest_bytes(path.read_bytes()) != sha
                or digest_bytes(git("show", value["apparatus_commit"] + ":" + relative)) != sha):
            raise ValueError("Frozen V42 input changed: " + relative)
    if any(value.get(key) != item for key, item in constants().items()):
        raise ValueError("Frozen V42 cost, task stream, memory policy or authority changed")
    inherited.verify(json.loads(inherited.PATH.read_text()))
    if value["public_development_sha256"] != digest_bytes((HERE / "DEVELOPMENT.json.gz").read_bytes()):
        raise ValueError("V42 development evidence changed after freeze")
    return True


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
