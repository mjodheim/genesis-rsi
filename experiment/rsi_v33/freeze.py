"""Full prospective commitment, including inherited evidence and public tuning."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v31 import programs
from experiment.rsi_v32 import campaign as predecessor_campaign, freeze as previous
from experiment.rsi_v33 import bank, development, engine, storage

HERE = ROOT / "experiment/rsi_v33"
PATH = HERE / "V33_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = {ROOT / relative for relative in json.loads(previous.PATH.read_text())["inputs"]}
    paths.add(previous.PATH)
    paths.update(p for p in predecessor_campaign.DIRECTORY.iterdir() if p.is_file())
    paths.update((ROOT / "scripts/check_rsi_v31_transport_recovery.py", ROOT / "tests/test_rsi_v31_transport.py"))
    paths.update(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p != PATH and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v33.py", ROOT / "docs/IP_REVIEWS/V33_ACTIVE_MEMORY_PROBES_REVIEW.md"))
    return sorted(paths)


def constants():
    return {"schema": "mira-genesis-v33-active-probe-memory-freeze-v1", "bank_sha256": bank.population_sha256(),
            "fresh_seeds": list(bank.FRESH_SEEDS), "tasks_per_arm": len(bank.stream(bank.FRESH_SEEDS[0])) * len(bank.FRESH_SEEDS),
            "caps": engine.CAPS.__dict__, "arms": list(engine.ARMS), "max_charged_evaluations_per_task": engine.MAX_EVALUATIONS,
            "root_evaluations_per_task": 1, "probe_evaluations_per_task": 2, "controller_calls_per_task": 1,
            "margin_milli": development.selection(), "parent_policy_sha256": programs.PARENT_SHA256,
            "controller_sha256": {arm: digest_bytes(engine.controller(arm).encode()) for arm in engine.ARMS},
            "track": "B", "fresh_consumed_before_freeze": False, "scientific_external_model_calls": 0,
            "new_recursive_transition_established": False, "l9_open_ended_passed": False, "l10_independent_passed": False}


def build():
    if PATH.exists() or (ROOT / "results/rsi-v33/probes-20261002/V33_RESERVATION.json").exists():
        raise ValueError("Never replace a freeze or consumed attempt")
    from scripts.check_rsi_v31_transport_recovery import check
    check()
    development.verify(replay=True)
    predecessor = predecessor_campaign.check(require_result=True, replay=False)
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {**constants(), "apparatus_commit": commit, "inputs": manifest,
             "python_version": sys.version.split()[0], "previous_operational_evidence_sha256": digest(predecessor)}
    value["freeze_sha256"] = digest(value)
    storage.publish_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("freeze_sha256") != digest({key: item for key, item in value.items() if key != "freeze_sha256"}):
        raise ValueError("Altered V33 freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V33 freeze must be committed before execution")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Apparatus ancestry was lost")
    if set(value["inputs"]) != {p.relative_to(ROOT).as_posix() for p in inputs()}:
        raise ValueError("Incomplete V33 manifest")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(
                git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen input changed: " + relative)
    if any(value.get(key) != item for key, item in constants().items()):
        raise ValueError("Frozen authority, scope, selection, bank or costs changed")
    return True


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
