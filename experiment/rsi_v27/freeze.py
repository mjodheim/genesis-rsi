"""Complete prospective V27 commitment with unchanged historical ancestry."""
import json
import subprocess
import sys

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v26 import campaign as v26, freeze as v26_freeze
from experiment.rsi_v27 import family, fresh_bank
from experiment.rsi_v27.engine import CAPS

HERE = ROOT / "experiment/rsi_v27"
PATH = HERE / "V27_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = {ROOT / relative for relative in json.loads(v26_freeze.PATH.read_text())["inputs"]}
    paths.add(v26_freeze.PATH)
    paths.update(p for p in v26.ATTEMPT.parent.iterdir() if p.is_file())
    paths.update(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p != PATH and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v27.py",
                  ROOT / "docs/IP_REVIEWS/V27_V29_L6_L8_PUBLICATION_REVIEW.md"))
    return tuple(sorted(paths))


def build():
    if PATH.exists():
        raise ValueError("Never replace a scientific freeze")
    previous = v26.check(require_result=True)
    if not previous["v26_l5_positive"]:
        raise ValueError("The qualified L5 predecessor is required")
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    value = {"schema": "mira-genesis-v27-full-freeze-v1", "apparatus_commit": commit,
             "inputs": manifest, "candidate_universe_sha256": digest(family.effective_universe()),
             "bank_sha256": digest(fresh_bank.BANKS), "meta_caps": CAPS.__dict__,
             "fresh_caps": fresh_bank.CAPS.__dict__, "python_version": sys.version.split()[0],
             "previous_l5": previous, "new_holdout_consumed_before_freeze": False,
             "track": "A", "scientific_external_model_calls": 0,
             "canonical_output": "results/rsi-v27/chain-20261001/V27_ATTEMPT.json"}
    value["freeze_sha256"] = digest(value)
    write_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("schema") != "mira-genesis-v27-full-freeze-v1" or value.get("freeze_sha256") != digest(
            {k: v for k, v in value.items() if k != "freeze_sha256"}):
        raise ValueError("Altered V27 scientific freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V27 freeze must be committed before execution")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Apparatus ancestry was lost")
    if set(value["inputs"]) != {p.relative_to(ROOT).as_posix() for p in inputs()}:
        raise ValueError("Incomplete V27 freeze")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(
                git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen scientific input changed: " + relative)
    if (value["candidate_universe_sha256"] != digest(family.effective_universe())
            or value["bank_sha256"] != digest(fresh_bank.BANKS)
            or value["meta_caps"] != CAPS.__dict__ or value["fresh_caps"] != fresh_bank.CAPS.__dict__):
        raise ValueError("Frozen population or budget changed")
    return True


if __name__ == "__main__":
    value = build()
    print(json.dumps({k: value[k] for k in ("apparatus_commit", "freeze_sha256")}, indent=2))
