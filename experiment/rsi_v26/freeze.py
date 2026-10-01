"""Commit the complete new V26 apparatus before canonical source selection."""
import json
import subprocess

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, write_json
from experiment.rsi_v25.scientific_freeze import runtime_versions
from experiment.rsi_v25.check_executable_result import check as check_v25
from experiment.rsi_v25.build_l5_freeze import preserved_v24_files
from experiment.rsi_v25.l4_history_retention import REFERENCE, TRANSCRIPTS
from experiment.rsi_v26.family import universe
from experiment.rsi_v26.native_bank import HERE, TASKS, CAPS

PATH=HERE/"V26_SCIENTIFIC_FREEZE.json"


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT)


def inputs():
    paths=set()
    for directory in (HERE,ROOT/"experiment/rsi_v25",ROOT/"experiment/rsi_v23"):
        paths.update(p for p in directory.rglob("*") if p.is_file() and "__pycache__"not in p.parts
                     and p.suffix in (".py",".java",".js",".json",".md") and p!=PATH)
    paths.update((ROOT/"experiment/rsi_v22/policies/g1_search_policy.py",
                  ROOT/"experiment/rsi_v22/policies/g2_search_policy.py",REFERENCE,*TRANSCRIPTS))
    paths.update(preserved_v24_files())
    paths.update(p for p in (ROOT/"results/rsi-v25/executable-20261001").iterdir() if p.is_file())
    paths.update((ROOT/"scripts/replicate_v25_consumed_result.py",
                  ROOT/"tests/test_rsi_v26_frontier.py",
                  ROOT/"docs/IP_REVIEWS/V26_FRONTIER_L5_PUBLICATION_REVIEW.md",
                  ROOT/"AGENTS.md",ROOT/".github/workflows/ci.yml"))
    return tuple(sorted(paths))


def build():
    if PATH.exists():raise ValueError("Never overwrite a scientific freeze")
    previous=check_v25(require_result=True)
    if previous["v25_l5_positive"] or not previous["holdout_consumed"]:
        raise ValueError("V26 must preserve the actual consumed V25 negative")
    commit=git("rev-parse","HEAD").decode().strip();manifest={}
    for p in inputs():
        relative=p.relative_to(ROOT).as_posix()
        if p.is_symlink() or git("show",commit+":"+relative)!=p.read_bytes():
            raise ValueError("V26 scientific inputs must be exact committed regular files: "+relative)
        manifest[relative]=digest_bytes(p.read_bytes())
    result={"schema":"mira-genesis-rsi-v26-full-scientific-freeze-v1",
            "apparatus_commit":commit,"inputs":manifest,"candidate_count":len(universe()),
            "candidate_universe_sha256":digest(universe()),"native_population_sha256":digest(TASKS),
            "external_caps":CAPS.__dict__,"runtime_versions":runtime_versions(),"track":"A",
            "scientific_external_model_calls":0,"candidate_transfer_consumed_before_freeze":False,
            "previous_v25_negative":previous,"canonical_output":"results/rsi-v26/frontier-20261001/V26_ATTEMPT.json"}
    result["freeze_sha256"]=digest(result);write_json(PATH,result);return result


def verify(result,*,require_committed=True):
    if (result.get("schema")!="mira-genesis-rsi-v26-full-scientific-freeze-v1"
        or result.get("freeze_sha256")!=digest({k:v for k,v in result.items() if k!="freeze_sha256"})):
        raise ValueError("Altered V26 scientific freeze")
    if require_committed and git("show","HEAD:"+PATH.relative_to(ROOT).as_posix())!=PATH.read_bytes():
        raise ValueError("V26 freeze must be committed before canonical execution")
    if subprocess.run(["git","merge-base","--is-ancestor",result["apparatus_commit"],"HEAD"],cwd=ROOT).returncode:
        raise ValueError("The V26 apparatus commit is not preserved in ancestry")
    if set(result["inputs"])!={p.relative_to(ROOT).as_posix() for p in inputs()}:
        raise ValueError("V26 freeze has an incomplete apparatus manifest")
    for relative,sha in result["inputs"].items():
        p=ROOT/relative
        if (p.is_symlink() or digest_bytes(p.read_bytes())!=sha
            or digest_bytes(git("show",result["apparatus_commit"]+":"+relative))!=sha):
            raise ValueError("Frozen V26 input changed: "+relative)
    if (result["candidate_universe_sha256"]!=digest(universe())
        or result["native_population_sha256"]!=digest(TASKS) or result["external_caps"]!=CAPS.__dict__):
        raise ValueError("V26 executable family, bank or authority changed")
    return True


if __name__=="__main__":
    print(json.dumps({k:v for k,v in build().items() if k in ("apparatus_commit","freeze_sha256","candidate_count")},indent=2))
