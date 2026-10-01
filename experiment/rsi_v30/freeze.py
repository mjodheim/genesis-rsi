"""Complete prospective commitment of measured bottleneck selection."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v27.engine import CAPS
from experiment.rsi_v29 import campaign as v29, freeze as v29_freeze
from experiment.rsi_v30 import family, fresh_bank
from experiment.rsi_v30.pipeline_contexts import PUBLIC_CAPS

HERE = ROOT / "experiment/rsi_v30"
PATH = HERE / "V30_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = {ROOT / relative for relative in json.loads(v29_freeze.PATH.read_text())["inputs"]}
    paths.add(v29_freeze.PATH)
    paths.update(p for p in v29.ATTEMPT.parent.iterdir() if p.is_file())
    paths.update(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p != PATH and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v30.py", ROOT / "docs/IP_REVIEWS/V30_MEASURED_BOTTLENECK_REVIEW.md"))
    return tuple(sorted(paths))


def build():
    if PATH.exists() or (ROOT / "results/rsi-v30/target-20261001/V30_ATTEMPT.json").exists():
        raise ValueError("Never replace a freeze or consumed attempt")
    previous = v29.check(require_result=True)
    if not previous["v29_l7_positive"]:
        raise ValueError("The qualified L7 predecessor is required")
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {"schema": "mira-genesis-v30-full-freeze-v1", "apparatus_commit": commit,
             "inputs": manifest, "source_universe_sha256": digest(family.universe()),
             "bank_sha256": digest(fresh_bank.CONTEXTS), "meta_caps": CAPS.__dict__,
             "probe_and_post_caps": PUBLIC_CAPS.__dict__, "target_calls_per_arm_context": 1,
             "python_version": sys.version.split()[0], "previous_l7": previous,
             "parent_policy_sha256": family.PARENT_SHA256, "new_holdout_consumed_before_freeze": False,
             "track": "A", "scientific_external_model_calls": 0,
             "canonical_output": "results/rsi-v30/target-20261001/V30_ATTEMPT.json"}
    value["freeze_sha256"] = digest(value)
    write_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("schema") != "mira-genesis-v30-full-freeze-v1" or value.get("freeze_sha256") != digest(
            {k: v for k, v in value.items() if k != "freeze_sha256"}):
        raise ValueError("Altered V30 scientific freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V30 freeze must be committed before execution")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Apparatus ancestry was lost")
    if set(value["inputs"]) != {p.relative_to(ROOT).as_posix() for p in inputs()}:
        raise ValueError("Incomplete V30 scientific freeze")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(
                git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen scientific input changed: " + relative)
    if (value["source_universe_sha256"] != digest(family.universe())
            or value["bank_sha256"] != digest(fresh_bank.CONTEXTS)
            or value["meta_caps"] != CAPS.__dict__ or value["probe_and_post_caps"] != PUBLIC_CAPS.__dict__
            or value["parent_policy_sha256"] != digest_bytes(family.parent().encode())
            or value["target_calls_per_arm_context"] != 1):
        raise ValueError("Frozen population, parent, or budget changed")
    return True


if __name__ == "__main__":
    value = build()
    print(json.dumps({key: value[key] for key in ("apparatus_commit", "freeze_sha256")}, indent=2))
