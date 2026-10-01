"""Complete prospective V29 commitment with unchanged historical ancestry."""
import json
import subprocess
from itertools import product

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v28 import campaign as v28, freeze as v28_freeze
from experiment.rsi_v29 import native_bank

HERE = ROOT / "experiment/rsi_v29"
PATH = HERE / "V29_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT)


def inputs():
    paths = {ROOT / relative for relative in json.loads(v28_freeze.PATH.read_text())["inputs"]}
    paths.add(v28_freeze.PATH)
    paths.update(p for p in v28.ATTEMPT.parent.iterdir() if p.is_file())
    paths.update(p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                 and p != PATH and p.suffix in (".py", ".md", ".json", ".gz"))
    paths.update((ROOT / "tests/test_rsi_v29.py",
                  ROOT / "docs/IP_REVIEWS/V28_V30_NEGATIVE_L6_CONTINUATION_REVIEW.md"))
    return tuple(sorted(paths))


def build():
    if PATH.exists():
        raise ValueError("Never replace a scientific freeze")
    previous = v28.check(require_result=True)
    if not previous["v28_l6_positive"]:
        raise ValueError("A genuinely qualified L6 lineage is required")
    commit, manifest = git("rev-parse", "HEAD").decode().strip(), {}
    for path in inputs():
        relative = path.relative_to(ROOT).as_posix()
        if path.is_symlink() or git("show", commit + ":" + relative) != path.read_bytes():
            raise ValueError("Uncommitted or nonregular scientific input: " + relative)
        manifest[relative] = digest_bytes(path.read_bytes())
    terminal = (v28.ATTEMPT.parent / "G6_SELECTED_POLICY.py").read_bytes()
    value = {"schema": "mira-genesis-v29-full-freeze-v1", "apparatus_commit": commit,
             "inputs": manifest, "bank_sha256": digest(native_bank.TASKS),
             "source_universe_sha256": digest({d: [native_bank.render(d, c) for c in product(range(4), repeat=3)] for d in native_bank.DOMAINS}),
             "external_caps": native_bank.CAPS.__dict__, "runtime_versions": native_bank.runtime_versions(),
             "previous_l6": previous, "terminal_policy_sha256": digest_bytes(terminal),
             "domains": native_bank.DOMAINS, "new_holdout_consumed_before_freeze": False,
             "track": "A", "scientific_external_model_calls": 0,
             "canonical_output": "results/rsi-v29/transfer-20261001/V29_ATTEMPT.json"}
    value["freeze_sha256"] = digest(value)
    write_json(PATH, value)
    return value


def verify(value, *, require_committed=True):
    if value.get("schema") != "mira-genesis-v29-full-freeze-v1" or value.get("freeze_sha256") != digest(
            {k: v for k, v in value.items() if k != "freeze_sha256"}):
        raise ValueError("Altered V29 scientific freeze")
    if require_committed and git("show", "HEAD:" + PATH.relative_to(ROOT).as_posix()) != PATH.read_bytes():
        raise ValueError("V29 freeze must be committed before execution")
    if subprocess.run(["git", "merge-base", "--is-ancestor", value["apparatus_commit"], "HEAD"], cwd=ROOT).returncode:
        raise ValueError("Apparatus ancestry was lost")
    if set(value["inputs"]) != {p.relative_to(ROOT).as_posix() for p in inputs()}:
        raise ValueError("Incomplete V29 freeze")
    for relative, sha in value["inputs"].items():
        path = ROOT / relative
        if path.is_symlink() or digest_bytes(path.read_bytes()) != sha or digest_bytes(
                git("show", value["apparatus_commit"] + ":" + relative)) != sha:
            raise ValueError("Frozen scientific input changed: " + relative)
    if (value["bank_sha256"] != digest(native_bank.TASKS)
            or value["source_universe_sha256"] != digest({d: [native_bank.render(d, c) for c in product(range(4), repeat=3)] for d in native_bank.DOMAINS})
            or value["external_caps"] != native_bank.CAPS.__dict__):
        raise ValueError("Frozen native population or budget changed")
    return True


if __name__ == "__main__":
    value = build()
    print(json.dumps({k: value[k] for k in ("apparatus_commit", "freeze_sha256")}, indent=2))
