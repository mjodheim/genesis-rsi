"""Single frozen V26 campaign and independent retained-receipt verification."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT,digest,digest_bytes,write_json
from experiment.rsi_v25.executable_family import predecessor_source
from experiment.rsi_v25.search_engine import run_search,global_utility,SANDBOX
from experiment.rsi_v25.l4_history_retention import check_l4
from experiment.rsi_v25.scientific_freeze import runtime_versions
from experiment.rsi_v26 import meta,native_bank,freeze
from experiment.rsi_v26.family import ROOT_PARAMS,render,components,ablations

ATTEMPT=ROOT/"results/rsi-v26/frontier-20261001/V26_ATTEMPT.json"
VERDICT=ATTEMPT.parent/"V26_FINAL_ADJUDICATION.json"


def witness(selected):
    observed=selected["parent_choice_witness"]
    if not observed:return {"accepted":False,"reason":"missing-exploration-witness"}
    with tempfile.TemporaryDirectory(prefix="v26-witness-") as tmp:
        original=Path(tmp)/"control.py";candidate=Path(tmp)/"candidate.py"
        original.write_text(render(observed["control_params"]));candidate.write_text(render(selected["params"]))
        if digest_bytes(original.read_bytes())!=observed["control_source_sha256"]:
            raise ValueError("V26 behavioral control identity changed")
        control_meta=SANDBOX.metadata(original,[]);candidate_meta=SANDBOX.metadata(candidate,[])
        first=SANDBOX.execute(original,observed["view"],min(2,control_meta["metadata"][7]),[])
        second=SANDBOX.execute(candidate,observed["view"],min(2,candidate_meta["metadata"][7]),[])
    accepted=bool(first.get("accepted")and second.get("accepted")
                  and first["selected_parent_ids"]and second["selected_parent_ids"]
                  and first["selected_parent_ids"]!=second["selected_parent_ids"]
                  and first["selected_parent_ids"]==observed["control_parent_ids"]
                  and second["selected_parent_ids"]==observed["successor_parent_ids"])
    return {"accepted":accepted,"control":first,"candidate":second,"view_sha256":observed["view_sha256"]}


def meta_utility(arm):
    s,r=arm["selected"],arm["search"]
    return (int(s["qualified_discovery"]),*s["utility"][:2],-r["represented_requests"],-r["rounds"])


def pre_gates(record,calibration):
    for arm in meta.ARMS:
        saved=record["meta"][arm]
        replay=run_search(meta.CONTROLS[arm],meta.Host(calibration),caps=meta.CAPS,isolated=True)
        if digest(saved["search"])!=digest(replay) or digest(saved["selected"])!=digest(meta.choose(replay,calibration)):
            raise ValueError("V26 meta receipt or selected descendant differs from deterministic replay")
    chosen=record["meta"]["g2_meta"]["selected"];source=render(chosen["params"])
    if digest(record["retention"])!=digest(check_l4(source)) or digest(record["witness"])!=digest(witness(chosen)):
        raise ValueError("V26 retention or witness flags differ from isolated replay")
    root=next(x for x in calibration["candidates"] if x["params"]==ROOT_PARAMS)
    lineage=[x for x in record["meta"]["g2_meta"]["search"]["nodes"].values()
             if x["source_sha256"]==chosen["source_sha256"]]
    return {"qualified_parent_selected_descent":bool(chosen["qualified_discovery"]and lineage and lineage[0]["lineage_depth"]>0),
            "composed_exploration_and_full_quality_stop":chosen["params"]["strategy"]!="inherited"and chosen["params"]["stop_quality"]==1000,
            "strict_development_gain":tuple(chosen["utility"])>tuple(root["utility"]),
            "strict_every_development_ablation":bool(chosen["component_ablations"]and all(
                tuple(chosen["utility"])>tuple(x["utility"])for x in chosen["component_ablations"])),
            "isolated_parent_choice_witness":record["witness"]["accepted"],
            "l4_zero_loss":record["retention"]["zero_tolerance_retention"],
            "meta_advantage_over_acquired_g2_ablation":meta_utility(record["meta"]["g2_meta"])>meta_utility(record["meta"]["g2_ablation"])}


def policies(record):
    chosen=record["meta"]["g2_meta"]["selected"]
    result={"g3":render(chosen["params"]),"g2":predecessor_source(),
            "g1_meta_successor":render(record["meta"]["g1_meta"]["selected"]["params"])}
    result.update({"ablation_"+axis:render(params)for axis,params in zip(components(chosen["params"]),ablations(chosen["params"]))})
    return result


def verify_native(search,task,source,seeded):
    receipts={}
    for node_id,node in search["nodes"].items():
        if node_id=="root":continue
        receipt=node["evaluation"];cases=receipt["cases"]
        if (receipt["source_sha256"]!=digest_bytes(native_bank.render(task,node["candidate"]["choices"]).encode())
            or receipt["cases_sha256"]!=digest(cases) or type(cases["passed"])is not int or type(cases["total"])is not int
            or not 0<=cases["passed"]<=cases["total"] or cases["total"]<=0
            or len(cases["failed"])!=cases["total"]-cases["passed"]
            or receipt["quality_milli"]!=cases["passed"]*1000//cases["total"]
            or not receipt["native_source_executed"]or receipt["task_sha256"]!=digest(task)
            or receipt["harness_sha256"]!=digest_bytes((native_bank.HERE/"native_harnesses"/task["harness"]).read_bytes())):
            raise ValueError("V26 native evaluator receipt was changed or forged")
        if node["source_sha256"]in receipts:raise ValueError("Duplicate V26 proposal charged twice")
        receipts[node["source_sha256"]]=receipt
    class ReceiptHost(native_bank.Host):
        def evaluate(self,row):
            if row["source_sha256"]not in receipts:raise ValueError("Replay requests an unobserved native proposal")
            return receipts[row["source_sha256"]]
    replay=run_search(source,ReceiptHost(task,seeded),caps=native_bank.CAPS,isolated=True)
    if digest(replay)!=digest({k:v for k,v in search.items()if k!="task_id"}):
        raise ValueError("V26 native trace, budget or policy differs from retained-receipt replay")


def adjudicate(record,frozen,calibration,native):
    gates=pre_gates(record,calibration)
    selected=record["meta"]["g2_meta"]["selected"]
    identities=(record["freeze_sha256"]==frozen["freeze_sha256"]and record["track"]=="A"
                and record["scientific_external_model_calls"]==0 and record["canonical_attempts"]==1
                and record["runtime_versions"]==frozen["runtime_versions"])
    predicates={**gates,"frozen_identities_track_and_one_attempt":identities,
                "fresh_transfer_completed":bool(record.get("transfer"))}
    utilities={};expected=policies(record)
    if record.get("transfer"):
        if not all(gates.values())or set(record["transfer"])!=set(expected):
            raise ValueError("V26 bank consumed with a failed pre-gate or omitted comparator")
        roots={x["task_id"]:x["seeded"]for x in native["tasks"]}
        for arm,rows in record["transfer"].items():
            if [x["task_id"]for x in rows]!=[x["task_id"]for x in native_bank.TASKS]:
                raise ValueError("V26 native task identities changed")
            for task,search in zip(native_bank.TASKS,rows):
                verify_native(search,task,expected[arm],roots[task["task_id"]])
            utilities[arm]=global_utility(rows)
        predicates.update(strict_fresh_gain_over_g2=utilities["g3"]>utilities["g2"],
                          strict_fresh_gain_over_g1_meta=utilities["g3"]>utilities["g1_meta_successor"],
                          strict_every_fresh_ablation=all(utilities["g3"]>u for arm,u in utilities.items()if arm.startswith("ablation_")))
    else:predicates.update(strict_fresh_gain_over_g2=False,strict_fresh_gain_over_g1_meta=False,strict_every_fresh_ablation=False)
    positive=all(predicates.values())
    return {"schema":"mira-genesis-rsi-v26-frontier-l5-adjudication-v1","v26_l5_positive":positive,
            "verdict":"POSITIVE_BOUNDED_L5"if positive else"VALID_NEGATIVE_FRESH_TRANSFER"if record.get("transfer")else"NEGATIVE_PRE_TRANSFER",
            "predicates":predicates,"fresh_global_utilities":utilities,
            "meta_utilities":{arm:meta_utility(record["meta"][arm])for arm in meta.ARMS},
            "freeze_sha256":frozen["freeze_sha256"],"holdout_consumed":bool(record.get("transfer")),
            "scope":"BOUNDED_NATIVE_REPAIR_TRANSFER_ON_FOUR_PROJECT_AUTHORED_FRESH_TASKS"}


def run():
    frozen=json.loads(freeze.PATH.read_text());freeze.verify(frozen)
    if frozen["runtime_versions"]!=runtime_versions():raise ValueError("V26 canonical runtime differs from its freeze")
    calibration=json.loads((native_bank.HERE/"PUBLIC_CALIBRATION.json").read_text())
    native=json.loads((native_bank.HERE/"NATIVE_CALIBRATION.json").read_text())
    ATTEMPT.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(ATTEMPT,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
    record={"schema":"mira-genesis-rsi-v26-canonical-attempt-v1","status":"STARTED","canonical_attempts":1,
            "track":"A","scientific_external_model_calls":0,"runtime_versions":frozen["runtime_versions"],
            "freeze_sha256":frozen["freeze_sha256"],"transfer":{},"negative_preservation_required":True}
    with os.fdopen(descriptor,"w")as f:json.dump(record,f,indent=2,sort_keys=True);f.write("\n")
    try:
        def save_meta(rows):record["meta"]=rows;write_json(ATTEMPT,record)
        record["meta"]=meta.run(calibration,checkpoint=save_meta)
        chosen=record["meta"]["g2_meta"]["selected"]
        record["retention"]=check_l4(render(chosen["params"]));record["witness"]=witness(chosen)
        record["pre_gates"]=pre_gates(record,calibration);write_json(ATTEMPT,record)
        if all(record["pre_gates"].values()):
            record["status"]="TRANSFER_STARTED";write_json(ATTEMPT,record)
            for arm,source in policies(record).items():
                def save_native(rows):record["transfer"][arm]=rows;write_json(ATTEMPT,record)
                record["transfer"][arm]=native_bank.run(source,native,checkpoint=save_native)
                print("Preserved V26 native arm: "+arm,flush=True)
        record["status"]="COMPLETED";result=adjudicate(record,frozen,calibration,native)
        write_json(ATTEMPT,record);write_json(VERDICT,result)
        for arm,data in record["meta"].items():
            (ATTEMPT.parent/(arm.upper()+"_SELECTED_POLICY.py")).write_text(render(data["selected"]["params"]))
        print(json.dumps(result,indent=2),flush=True);return result
    except BaseException as error:
        record["status"]="INSTRUMENT_ABORTED";record["instrument_error"]={"type":type(error).__name__,"message":str(error)}
        write_json(ATTEMPT,record);write_json(VERDICT,{"verdict":"PRESERVED_INSTRUMENT_ABORT","v26_l5_positive":False,
                                                   "freeze_sha256":frozen["freeze_sha256"],"partial_evidence_preserved":True})
        raise


def check(require_result=False):
    if not freeze.PATH.exists():
        if ATTEMPT.exists()or require_result:raise ValueError("V26 evidence has no committed freeze")
        return {"status":"APPARATUS_PREPARATION","v26_l5_positive":False}
    frozen=json.loads(freeze.PATH.read_text());freeze.verify(frozen)
    if not ATTEMPT.exists():
        if require_result:raise ValueError("V26 canonical evidence missing")
        return {"status":"PREREGISTERED_UNCONSUMED","v26_l5_positive":False}
    for path in (ATTEMPT,VERDICT):
        if freeze.git("show","HEAD:"+path.relative_to(ROOT).as_posix())!=path.read_bytes():
            raise ValueError("V26 canonical evidence is not committed exactly")
    record=json.loads(ATTEMPT.read_text());verdict=json.loads(VERDICT.read_text())
    if record["status"]=="INSTRUMENT_ABORTED":
        if verdict["v26_l5_positive"]or verdict["verdict"]!="PRESERVED_INSTRUMENT_ABORT":
            raise ValueError("V26 instrument failure relabeled positive")
        return verdict
    if record["status"]!="COMPLETED":raise ValueError("V26 partial attempt cannot supply a final verdict")
    replay=adjudicate(record,frozen,json.loads((native_bank.HERE/"PUBLIC_CALIBRATION.json").read_text()),
                     json.loads((native_bank.HERE/"NATIVE_CALIBRATION.json").read_text()))
    if digest(verdict)!=digest(replay):raise ValueError("V26 verdict disagrees with raw evidence replay")
    return replay


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--check",action="store_true");parser.add_argument("--require-result",action="store_true")
    args=parser.parse_args()
    if args.check:print(json.dumps(check(args.require_result),indent=2))
    else:run()
