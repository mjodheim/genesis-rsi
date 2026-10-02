"""Commit immutable governance before the first fresh epoch, not before each retuning."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v33 import campaign as predecessor_campaign, freeze as previous, storage
from experiment.rsi_v35 import bank, development, engine, programs

HERE = ROOT / "experiment/rsi_v35"
PATH = HERE / "V35_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = {ROOT / relative for relative in json.loads(previous.PATH.read_text())["inputs"]}
    paths.add(previous.PATH)
    paths.update(p for p in (ROOT / "experiment/rsi_v34").rglob("*")
                 if p.is_file() and "__pycache__" not in p.parts and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v34.py", ROOT / "docs/IP_REVIEWS/V34_CONTINUING_ARCHIVE_REVIEW.md"))
    paths.update(predecessor_campaign.DIRECTORY / name for name in (
        "V33_RESERVATION.json", "V33_ATTEMPT_RAW.json.gz", "V33_FINAL_ADJUDICATION.json", "V33_COMPLETION.json"))
    paths.update(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p != PATH and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v35.py", ROOT / "docs/IP_REVIEWS/V35_DOMAIN_AGE_REVIEW.md"))
    return sorted(paths)


def constants():
    return {"schema": "mira-genesis-v35-continuing-archive-freeze-v1", "bank_sha256": bank.population_sha256(),
            "fresh_seeds": list(bank.FRESH_SEEDS), "initial_epochs": bank.INITIAL_EPOCHS,
            "tasks_per_arm_first_prefix": sum(len(bank.stream(seed, epoch)) for seed in bank.FRESH_SEEDS for epoch in range(bank.INITIAL_EPOCHS)),
            "arms": list(engine.ARMS), "caps": engine.CAPS.__dict__, "max_charged_evaluations_per_task": engine.MAX_EVALUATIONS,
            "domain_introduction_order": list(programs.DOMAINS), "grammar_capacity_instructions": programs.MAX_STEPS,
            "parent_policy_sha256": programs.PARENT_SHA256, "root_evaluations_per_task": 1, "probe_evaluations_per_task": 2,
            "controller_calls_per_task": 1, "checkpoint_position": 3, "track": "B", "scientific_external_model_calls": 0,
            "fresh_consumed_before_freeze": False, "new_recursive_transition_established": False,
            "l9_open_ended_passed": False, "l10_independent_passed": False}


def build():
    if PATH.exists() or (ROOT / "results/rsi-v35/continuing-20261002/epoch-000/RESERVATION.json").exists():
        raise ValueError("Never replace a freeze or consumed first epoch")
    development.verify(replay=True)
    predecessor = predecessor_campaign.check(require_result=True, replay=False)
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {**constants(), "apparatus_commit": commit, "inputs": manifest, "python_version": sys.version.split()[0],
             "previous_finite_result_sha256": digest(predecessor)}
    value["freeze_sha256"] = digest(value)
    storage.publish_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("freeze_sha256") != digest({key: item for key, item in value.items() if key != "freeze_sha256"}):
        raise ValueError("Altered V35 freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V35 governance freeze must be committed before behavior")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Scientific apparatus ancestry was lost")
    if set(value["inputs"]) != {path.relative_to(ROOT).as_posix() for path in inputs()}:
        raise ValueError("Incomplete V35 input manifest")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen governance input changed: " + relative)
    if any(value.get(key) != item for key, item in constants().items()):
        raise ValueError("Frozen costs, domain, grammar, task stream or scientific authority changed")
    return True


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
