#!/usr/bin/env python3
"""Prospective untouched-project V1 vs V2.1 repair study.

The project IDs, code revision, arm definitions, pool size and candidate budgets
were committed BEFORE any checkout. All candidate proposals across all cases
are sealed BEFORE running the first candidate validator. No reference fix,
fixed checkout, hidden expected answer or model-generated patch is consulted.

This evaluates a locked static V2.1 grammar: it is a BLIND REPAIR STUDY but
NOT a recursive self-improvement study; no policy self-modification is enabled.
"""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import csv
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from genesis import repair_strategist
from genesis.failure_localization import prioritize_from_public_test_source
from genesis.trust_root import digest_of
from scripts.g11_three_repo_repair_eval import paths_for_case
from scripts.run_autonomous_defects4j_lang import D4J, D4J_ROOT, _run, _d4j_export, _failing_count

PREREG=ROOT/"experiment/v2/V21_FRESH_3PROJECT_PREREG_20261008.json"
BENCH=Path("/home/anthony/benchmarks/v21-fresh-3projects-20261008")
PREPARED=BENCH/"BASELINES_AND_SOURCE_SELECTION.json"
FROZEN=ROOT/"experiment/v2/V21_FRESH_3PROJECT_FROZEN_ALL_CANDIDATES_20261008.json"
PUBLIC_INDEX=ROOT/"experiment/v2/V21_FRESH_3PROJECT_FROZEN_INDEX_20261008.json"
OUTCOME=ROOT/"experiment/v2/V21_FRESH_3PROJECT_RESULTS_20261008.json"


def file_hash(text: str) -> str:
    return sha256(text.encode()).hexdigest()


def read_locked_manifest() -> dict:
    prereg=json.loads(PREREG.read_text())
    unsigned={k:v for k,v in prereg.items() if k!="preregistration_digest"}
    if prereg.get("preregistration_digest")!=digest_of(unsigned):
        raise RuntimeError("tampered preregistration")
    if len(prereg["projects"])!=3 or set(prereg["arms"])!={"v1_frozen_default","v21_typed_semantic_optin"}:
        raise RuntimeError("unexpected experiment scope")
    if prereg["evaluated_top_k_per_arm"]!=8 or prereg["generated_max_per_arm"]!=96:
        raise RuntimeError("candidate budgets changed")
    if prereg["evaluation_budgets_matched"] is not True:
        raise RuntimeError("unbalanced evaluation")
    original_sha=prereg["frozen_code_head"]
    for file in ("genesis/repair_strategist.py","genesis/v2/semantic_dsl.py",
                 "genesis/v2/semantic_adapter.py","genesis/v2/semantic_registry.py",
                 "genesis/java_state_consistency_mutations.py","genesis/v2/discovery.py"):
        result=subprocess.run(["git","diff","--quiet",original_sha,"--",file],
                              cwd=ROOT,check=False)
        if result.returncode!=0:
            raise RuntimeError(f"policy file modified after experiment lock: {file}")
    for rec in prereg["projects"]:
        with (D4J_ROOT/f"framework/projects/{rec['project']}/active-bugs.csv").open() as stream:
            rows=list(csv.DictReader(stream))
        index=int(rec["seed_sha256"],16)%len(rows)
        selected=rows[index]
        if (rec["seed_sha256"]!=file_hash(rec["seed"])
                or rec["bug_id"]!=int(selected["bug.id"])
                or rec["buggy_revision"]!=selected["revision.id.buggy"]
                or rec["pool_size"]!=len(rows)):
            raise RuntimeError("bug case does not match deterministic preselection")
    return prereg


def _seal(path: Path, payload: Mapping) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        raise RuntimeError(f"refusing to overwrite an existing science record: {path}")
    with path.open("x") as stream:
        json.dump(payload,stream,indent=2,sort_keys=True)
        stream.write("\n")


def _open_verified(path: Path, digest_key: str) -> dict:
    data=json.loads(path.read_text())
    if data.get(digest_key)!=digest_of({k:v for k,v in data.items() if k!=digest_key}):
        raise RuntimeError(f"tampered evidence file {path}")
    return data


def _bug_root(rec: Mapping) -> Path:
    return BENCH/f"{rec['project']}-{rec['bug_id']}-buggy"


def _extract_original_failing_tests(root: Path) -> list[str]:
    path=root/"failing_tests"
    if not path.is_file():
        raise RuntimeError("original full test failed to emit failing_tests")
    raw=[x[4:].strip() for x in path.read_text().splitlines() if x.startswith("--- ")]
    if not raw:
        raise RuntimeError("missing public failing test names")
    return raw


def prepare() -> None:
    prereg=read_locked_manifest()
    if PREPARED.exists() or FROZEN.exists():
        raise RuntimeError("baseline phase already recorded")
    BENCH.mkdir(parents=True,exist_ok=True)
    cases=[]
    for rec in prereg["projects"]:
        project,bug=rec["project"],rec["bug_id"]
        root=_bug_root(rec)
        print("CHECKOUT_PUBLIC_BUGGY_VERSION",project,bug,flush=True)
        if root.exists():
            raise RuntimeError("trial requires fresh checkout workspace")
        checkout=_run([str(D4J),"checkout","-p",project,"-v",f"{bug}b",
                       "-w",str(root)],check=False,timeout=300)
        if checkout.returncode!=0:
            raise RuntimeError(f"buggy checkout failed {project}-{bug}: {checkout.stdout[-400:]}")
        compilation=_run([str(D4J),"compile"],cwd=root,check=False,timeout=300)
        if compilation.returncode!=0:
            raise RuntimeError(f"buggy reference did not compile {project}-{bug}: {compilation.stdout[-500:]}")
        full=_run([str(D4J),"test"],cwd=root,check=False,timeout=300)
        count=_failing_count(full.stdout)
        triggers=_extract_original_failing_tests(root)
        if count is None or count<1 or len(triggers)<1:
            raise RuntimeError(f"no reproducible buggy baseline {project}-{bug}: test_exit={full.returncode}")
        source_prefix=_d4j_export(root,"dir.src.classes")[-1]
        test_prefix=_d4j_export(root,"dir.src.tests")[-1]
        sources=paths_for_case(project,bug,root,source_prefix)
        context=prioritize_from_public_test_source(
            project_root=root,test_source_dir=test_prefix,
            failing_tests_text=(root/"failing_tests").read_text(),
            source_paths=sources,max_focus_files=24,
        )
        focus=sorted(context["selected_source_paths"])
        if not focus:
            raise RuntimeError("no fixed source candidates discovered")
        if len(focus)>24:
            raise RuntimeError("too many selected Java classes")
        case={
            "project":project,
            "bug_id":bug,
            "buggy_root":str(root),
            "compile_exit":compilation.returncode,
            "compile_output_sha256":file_hash(compilation.stdout),
            "reference_full_test_exit":full.returncode,
            "reference_full_test_failures":count,
            "reference_test_output_sha256":file_hash(full.stdout),
            "source_prefix":source_prefix,
            "test_prefix":test_prefix,
            "public_trigger_tests":triggers[:8],
            "selected_sources":focus,
            "all_dynamically_loaded_source_count":len(sources),
            "localization_digest":context["priority_digest"],
            "priority_sources": [
                row["path"] for row in context["ranked_evidence"] if row["score"]>0
            ][:8],
            "public_buggy_only":True,
            "human_reference_fix_not_accessed":True,
        }
        cases.append(case)
        print("REFERENCE_BASELINE",project,bug,"failures",count,
              "loaded_sources",len(sources),"selected",len(focus),flush=True)
    body={
        "schema":"genesis-v21-fresh-prepared-baselines-v1",
        "preregistration_digest":prereg["preregistration_digest"],
        "cases":cases,
        "case_count":len(cases),
        "no_candidate_validation_yet":True,
        "buggy_revisions_only":True,
    }
    _seal(PREPARED,{**body,"preparation_digest":digest_of(body)})
    print("ALL_BUGGY_BASELINES_REPRODUCED",len(cases),flush=True)


def freeze() -> None:
    prereg=read_locked_manifest()
    prepared=_open_verified(PREPARED,"preparation_digest")
    if FROZEN.exists() or PUBLIC_INDEX.exists() or OUTCOME.exists():
        raise RuntimeError("the candidate freeze already exists")
    frozen_cases=[]
    for source_case in prepared["cases"]:
        root=Path(source_case["buggy_root"])
        focus=source_case["selected_sources"]
        if not all((root/p).is_file() for p in focus):
            raise RuntimeError("buggy checkout/source frontier changed")
        arms={}
        for arm in prereg["arms"]:
            t0=time.monotonic()
            generated=repair_strategist.generate(
                root,
                include_prefixes=focus,focus_paths=focus,
                max_candidates=prereg["generated_max_per_arm"],
                per_family_budget=prereg["per_family_budget"],
                composition_fraction=prereg["composition_fraction"],
                v21_semantic_hypotheses_experimental=(arm=="v21_typed_semantic_optin"),
            )
            elapsed=time.monotonic()-t0
            candidates=[]
            for candidate in generated["candidates"][:prereg["evaluated_top_k_per_arm"]]:
                path=candidate["path"]
                original=(root/path).read_text(encoding="utf-8")
                changed=candidate["content_utf8"]
                if candidate["expected_sha256"]!=file_hash(original) or original==changed:
                    raise RuntimeError("candidate source preimage changed")
                candidates.append({
                    "path":path,
                    "expected_sha256":candidate["expected_sha256"],
                    "candidate_sha256":file_hash(changed),
                    "candidate_digest":candidate["candidate_digest"],
                    "content_utf8":changed,
                    "component_operators":candidate["plan"]["component_operators"],
                    "depth":candidate["plan"]["depth"],
                })
            arms[arm]={
                "candidate_count":generated["candidate_count"],
                "generated_digest":generated["strategy_digest"],
                "candidate_index_digest":digest_of([
                    (cand["path"],file_hash(cand["content_utf8"]))
                    for cand in generated["candidates"]
                ]),
                "generator_elapsed_seconds":round(elapsed,3),
                "family_activation":generated["family_activation"],
                "candidates":candidates,
            }
            print("ARM_FROZEN",source_case["project"],source_case["bug_id"],arm,
                  "generated",len(generated["candidates"]),
                  "to_test",len(candidates),
                  "V21_hypotheses",generated["family_activation"].get("v21_peer_contract",{}).get("accepted",0),
                  flush=True)
        frozen_cases.append({
            "project":source_case["project"],
            "bug_id":source_case["bug_id"],
            "buggy_root":source_case["buggy_root"],
            "selected_sources":focus,
            "baseline_failures":source_case["reference_full_test_failures"],
            "triggers":source_case["public_trigger_tests"],
            "arms":arms,
        })
    body={
        "schema":"genesis-v21-prospective-all-arms-candidates-frozen-v1",
        "preregistration_digest":prereg["preregistration_digest"],
        "preparation_digest":prepared["preparation_digest"],
        "cases":frozen_cases,
        "candidate_validation_has_not_started":True,
        "source_of_truth":"buggy checkouts and public failing tests only",
        "code_head":prereg["frozen_code_head"],
    }
    sealed={**body,"freeze_digest":digest_of(body)}
    _seal(FROZEN,sealed)
    print("ALL_ARMS_ALL_CASES_FROZEN",sealed["freeze_digest"],flush=True)
    public={
        "schema":"genesis-v21-public-frozen-index-v1",
        "preregistration_digest":prereg["preregistration_digest"],
        "all_candidates_freeze_digest":sealed["freeze_digest"],
        "preparation_digest":prepared["preparation_digest"],
        "code_head":prereg["frozen_code_head"],
        "cases":[{
            "project":case["project"],"bug_id":case["bug_id"],
            "baseline_failures":case["baseline_failures"],
            "arms":{
                arm:{
                    "total_generated":record["candidate_count"],
                    "generator_index_digest":record["candidate_index_digest"],
                    "top_k":[(item["path"],item["candidate_sha256"],
                              item["component_operators"]) for item in record["candidates"]],
                    "new_v21_hypotheses_generated":record["family_activation"].get(
                        "v21_peer_contract",{}).get("accepted",0),
                } for arm,record in case["arms"].items()
            }
        } for case in sealed["cases"]],
        "no_candidate_evaluator_executed_prior_to_freeze":True,
        "no_fixed_version_accessed":True,
    }
    _seal(PUBLIC_INDEX,{**public,"index_digest":digest_of(public)})
    print("PUBLIC_COMMITTABLE_FREEZE",PUBLIC_INDEX,flush=True)


def _verify_validator_inputs(work: Path, item: Mapping) -> tuple[Path,str]:
    source=(work/item["path"]).resolve(strict=True)
    if not source.is_relative_to(work.resolve()) or not source.is_file():
        raise RuntimeError("candidate attempted path traversal")
    original=source.read_text(encoding="utf-8")
    if file_hash(original)!=item["expected_sha256"]:
        raise RuntimeError("candidate source changed after freeze")
    if file_hash(item["content_utf8"])!=item["candidate_sha256"]:
        raise RuntimeError("candidate text differs from sealed hash")
    return source,original


def _validate_one(original_root: Path, item: Mapping, triggers: list[str]) -> dict:
    with tempfile.TemporaryDirectory(prefix="v21-blind-validator-",dir=BENCH) as temp:
        work=Path(temp)/"buggy"
        shutil.copytree(original_root,work,ignore=shutil.ignore_patterns(
            ".git","target","build","*.class","*.log",".gradle"
        ))
        source,_=_verify_validator_inputs(work,item)
        source.write_text(item["content_utf8"],encoding="utf-8")
        try:
            compilation=_run([str(D4J),"compile"],cwd=work,check=False,timeout=180)
        except subprocess.TimeoutExpired:
            return {"compiled":False,"full_suite_pass":False,"error":"compile_timeout"}
        if compilation.returncode!=0:
            return {
                "compiled":False,"full_suite_pass":False,"error":"compile_failed",
                "compile_output_sha256":file_hash(compilation.stdout),
            }
        observed=[]
        for trigger in triggers:
            try:
                probe=_run([str(D4J),"test","-t",trigger],cwd=work,check=False,timeout=120)
                count=_failing_count(probe.stdout)
                outcome={
                    "trigger":trigger,"exit":probe.returncode,
                    "failing_tests":count,"output_sha256":file_hash(probe.stdout),
                }
            except subprocess.TimeoutExpired:
                outcome={"trigger":trigger,"exit":None,
                         "failing_tests":None,"error":"trigger_timeout"}
            observed.append(outcome)
        # Any known failing public trigger rejects the patch.
        if any(x.get("failing_tests") is not None and x["failing_tests"]>0
               for x in observed):
            return {
                "compiled":True,"trigger_results":observed,
                "full_suite_ran":False,"full_suite_pass":False,
                "error":"original_public_trigger_fails",
            }
        # Trigger uncertainty never counts as a pass: full suite is mandatory.
        try:
            full=_run([str(D4J),"test"],cwd=work,check=False,timeout=300)
        except subprocess.TimeoutExpired:
            return {
                "compiled":True,"trigger_results":observed,
                "full_suite_ran":False,"full_suite_pass":False,
                "error":"full_suite_timeout",
            }
        count=_failing_count(full.stdout)
        return {
            "compiled":True,
            "trigger_results":observed,
            "full_suite_ran":True,
            "full_suite_failures":count,
            "test_exit":full.returncode,
            "test_output_sha256":file_hash(full.stdout),
            "full_suite_pass":count==0 and full.returncode==0,
            "error":None if count is not None else "unparseable_full_suite",
        }


def evaluate() -> None:
    prereg=read_locked_manifest()
    prepared=_open_verified(PREPARED,"preparation_digest")
    frozen=_open_verified(FROZEN,"freeze_digest")
    published=_open_verified(PUBLIC_INDEX,"index_digest")
    if OUTCOME.exists():
        raise RuntimeError("trial already evaluated")
    if (frozen["preparation_digest"]!=prepared["preparation_digest"]
            or published["all_candidates_freeze_digest"]!=frozen["freeze_digest"]
            or prereg["preregistration_digest"]!=frozen["preregistration_digest"]):
        raise RuntimeError("scientific freeze digests do not agree")
    case_reports=[]
    for case in frozen["cases"]:
        case_root=Path(case["buggy_root"])
        unique={}
        for arm in prereg["arms"]:
            for candidate in case["arms"][arm]["candidates"]:
                key=(candidate["path"],candidate["candidate_sha256"])
                if key in unique and unique[key]!=candidate:
                    raise RuntimeError("candidate fingerprint collision")
                unique[key]=candidate
        observed={}
        for index,(key,item) in enumerate(sorted(unique.items()),1):
            # Original source never mutated or used as a scratch checkout.
            _verify_validator_inputs(case_root,item)
            result=_validate_one(case_root,item,case["triggers"])
            _verify_validator_inputs(case_root,item)
            observed[key]=result
            print("VALIDATION",case["project"],case["bug_id"],index,"of",len(unique),
                  "compiled",result.get("compiled"),
                  "full_suite_pass",result.get("full_suite_pass"),
                  "status",result.get("error"),flush=True)
        arms={}
        for arm in prereg["arms"]:
            top=case["arms"][arm]["candidates"]
            results=[observed[(c["path"],c["candidate_sha256"])] for c in top]
            successes=[i for i,result in enumerate(results,1)
                       if result.get("full_suite_pass") is True]
            arms[arm]={
                "total_generated":case["arms"][arm]["candidate_count"],
                "tested_rank_count":len(top),
                "compiled":sum(result.get("compiled") is True for result in results),
                "full_suite_pass_count":len(successes),
                "first_successful_rank":successes[0] if successes else None,
                "new_v21_hypotheses_generated":case["arms"][arm]["family_activation"].get(
                    "v21_peer_contract",{}).get("accepted",0),
                "candidate_index_digest":case["arms"][arm]["candidate_index_digest"],
                "top_candidate_operators":[item["component_operators"] for item in top],
            }
        case_reports.append({
            "project":case["project"],"bug_id":case["bug_id"],
            "original_failing_tests":case["baseline_failures"],
            "distinct_candidates_tested":len(unique),
            "actual_passes":sum(r.get("full_suite_pass") is True for r in observed.values()),
            "arms":arms,
            "candidate_evidence":[{
                "path":key[0],"candidate_sha256":key[1],"result":result
            } for key,result in sorted(observed.items())],
        })
    summary={
        arm:sum(x["arms"][arm]["first_successful_rank"] is not None
                for x in case_reports) for arm in prereg["arms"]
    }
    body={
        "schema":"genesis-v21-3project-prospective-result-v1",
        "preregistration_digest":prereg["preregistration_digest"],
        "candidate_freeze_digest":frozen["freeze_digest"],
        "case_count":len(case_reports),
        "cases":case_reports,
        "real_project_full_suite_repairs_by_arm":summary,
        "source_projects_unused_in_prior_experiment":True,
        "candidate_freeze_before_evaluator":True,
        "human_reference_fix_seen":False,
        "code_changes_during_trial":False,
        "not_a_general_RSI_certificate":True,
    }
    _seal(OUTCOME,{**body,"result_digest":digest_of(body)})
    print("COMPLETE_REAL_BLIND_3PROJECT_EVALUATION",
          json.dumps(summary,sort_keys=True),flush=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("prepare","freeze","evaluate"))
    phase=parser.parse_args().phase
    if phase=="prepare":
        prepare()
    elif phase=="freeze":
        freeze()
    else:
        evaluate()

if __name__=="__main__":
    main()
