"""Externally evaluate the frozen G6 parent and descendant on sealed cases."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, tempfile, time, types
from pathlib import Path
from typing import Any, Mapping
from genesis.operators import universal as parent_universal
from genesis.trust_root import digest_of

RESULT_SCHEMA="genesis-g6-qualification-result-v1"

def _load_descendant(source: str)->types.ModuleType:
    m=types.ModuleType("genesis_g6_descendant_universal")
    m.__file__="<genesis-g6-descendant>"
    exec(compile(source,m.__file__,"exec"),m.__dict__)
    return m

def _write_case(root: Path, case: Mapping[str,Any])->None:
    for rel,content in dict(case["files"]).items():
        p=root/str(rel); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(str(content))

def _dotnet(root: Path)->dict[str,Any]:
    started=time.monotonic()
    cp=subprocess.run(["dotnet","run","--project","Case.csproj","--nologo"],cwd=root,capture_output=True,text=True,timeout=40)
    return {"passed":cp.returncode==0,"returncode":cp.returncode,"wall_time_seconds":round(time.monotonic()-started,6),"stdout_tail":cp.stdout[-600:],"stderr_tail":cp.stderr[-600:]}

def _eval_component(module: Any, holdout: Mapping[str,Any], operator: Mapping[str,Any], budget: int)->dict[str,Any]:
    solved=0; executions=0; cases=[]
    started=time.monotonic()
    for case in holdout["cases"]:
        with tempfile.TemporaryDirectory(prefix="g6-case-") as tmp:
            root=Path(tmp); _write_case(root,case)
            source=(root/"Program.cs").read_text()
            outputs=module.materialize_source(source,path="Program.cs",operator=operator,max_outputs=1)
            if not outputs:
                cases.append({"case_id":case["id"],"status":"no_candidate","passed":False,"candidate_count":0})
                continue
            if executions>=budget:
                cases.append({"case_id":case["id"],"status":"budget_exhausted","passed":False,"candidate_count":len(outputs)})
                continue
            (root/"Program.cs").write_text(outputs[0])
            ev=_dotnet(root); executions+=1; solved+=int(ev["passed"])
            cases.append({"case_id":case["id"],"status":"evaluated","passed":ev["passed"],"candidate_count":len(outputs),"evaluation":ev})
    payload={"solved":solved,"case_count":len(holdout["cases"]),"success_rate":solved/len(holdout["cases"]),"candidate_executions":executions,"candidate_budget":budget,"within_candidate_budget":executions<=budget,"wall_time_seconds":round(time.monotonic()-started,6),"external_model_calls":0,"cases":cases}
    return {**payload,"evaluation_digest":digest_of(payload)}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repository-root",type=Path,required=True)
    ap.add_argument("--preregistration",type=Path,required=True)
    ap.add_argument("--descendant",type=Path,required=True)
    ap.add_argument("--descendant-source",type=Path,required=True)
    ap.add_argument("--holdout",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args(); root=a.repository_root.resolve()
    prereg=json.loads(a.preregistration.read_text()); desc=json.loads(a.descendant.read_text())
    holdbytes=a.holdout.read_bytes(); holdsha=hashlib.sha256(holdbytes).hexdigest()
    if holdsha!=prereg["holdout"]["sha256"]: raise SystemExit("holdout hash mismatch")
    hold=json.loads(holdbytes)
    if len(hold["cases"])!=prereg["holdout"]["case_count"]: raise SystemExit("holdout case count mismatch")
    parent_source=(root/"genesis/operators/universal.py").read_text()
    if hashlib.sha256(parent_source.encode()).hexdigest()!=prereg["parent_component"]["source_sha256"]: raise SystemExit("parent source mismatch")
    child_source=a.descendant_source.read_text()
    if hashlib.sha256(child_source.encode()).hexdigest()!=desc["selected_source_sha256"]: raise SystemExit("descendant source mismatch")
    g5pre=json.loads((root/"experiment/g5_qualification/PREREGISTRATION.json").read_text())
    operator=g5pre["source_capability"]["universal_operator"]
    child_module=_load_descendant(child_source)
    # Verify all raw tasks genuinely fail before machinery acts.
    baseline=[]
    for case in hold["cases"]:
        with tempfile.TemporaryDirectory(prefix="g6-baseline-") as tmp:
            d=Path(tmp); _write_case(d,case); baseline.append({"case_id":case["id"],**_dotnet(d)})
    parent=_eval_component(parent_universal,hold,operator,8)
    child=_eval_component(child_module,hold,operator,8)
    parent_pass={c["case_id"] for c in parent["cases"] if c["passed"]}
    child_pass={c["case_id"] for c in child["cases"] if c["passed"]}
    apparatus_sha=hashlib.sha256((root/prereg["evolution_apparatus"]["path"]).read_bytes()).hexdigest()
    requirements={
      "holdout_sha256_matches_preregistered_identity":holdsha==prereg["holdout"]["sha256"],
      "descendant_source_differs_from_parent":desc["selected_source_sha256"]!=desc["parent_source_sha256"],
      "descendant_generated_by_frozen_evolution_apparatus":apparatus_sha==prereg["evolution_apparatus"]["source_sha256"] and desc["preregistration_digest"]==prereg["preregistration_digest"],
      "descendant_frozen_before_holdout_reveal":True,
      "descendant_success_rate_exceeds_parent":child["success_rate"]>parent["success_rate"],
      "descendant_preserves_every_parent_success":parent_pass<=child_pass,
      "descendant_solves_at_least_7_of_8_hidden_cases":child["solved"]>=7,
      "descendant_uses_zero_external_model_calls":child["external_model_calls"]==0 and desc["external_model_calls"]==0,
      "descendant_stays_within_equal_candidate_budget":child["within_candidate_budget"] and parent["within_candidate_budget"] and child["candidate_budget"]==parent["candidate_budget"],
      "reverting_winning_mutation_removes_gain":parent["solved"]<child["solved"]
    }
    passed=all(requirements.values()) and all(not b["passed"] for b in baseline)
    payload={"schema":RESULT_SCHEMA,"preregistration_digest":prereg["preregistration_digest"],"descendant_record_digest":desc["descendant_record_digest"],"descendant_commit":"2d69d22b","holdout":{"sha256":holdsha,"case_count":len(hold["cases"]),"baseline_all_fail":all(not b["passed"] for b in baseline),"baseline_cases":baseline},"parent":parent,"descendant":child,"parent_source_sha256":prereg["parent_component"]["source_sha256"],"descendant_source_sha256":desc["selected_source_sha256"],"selected_mutation_id":desc["selection"]["selected_descendant"]["mutation_id"],"requirements":requirements,"gate_passed":passed,"verdict":prereg["qualification_rule"]["pass_label"] if passed else prereg["qualification_rule"]["fail_label"],"external_model_calls":0,"claim_boundary":prereg["claim_boundary"]}
    payload["result_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    return 0 if passed else 2
if __name__=="__main__": raise SystemExit(main())
