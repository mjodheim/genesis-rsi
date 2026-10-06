"""Fail-closed epoch runner for L9-OE1 v2."""
from __future__ import annotations
import argparse, json
from pathlib import Path

from experiment.l9_oe1 import coded_native
from experiment.l9_oe1_v2 import bank
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import engine as v36

ARMS=("coded-archive","archive-g7","greedy-g7","cold-g7")

def default_state(arm):
    if arm=="coded-archive":
        return {"kind":"coded","motifs":[],"code_hashes":{},"seen_semantics":{},"position":0}
    return {"kind":"control","history":{},"seen_semantics":{},"position":0}

def default_state_sha256(arm):
    return digest(default_state(arm))

def load_state(path,arm,epoch):
    if epoch==0:
        if path.exists():
            raise ValueError("V2 epoch zero refuses pre-existing state")
        return default_state(arm)
    if not path.exists():
        raise ValueError("V2 continuation missing prior state")
    return json.loads(path.read_text())

def semantic_ledger(state,semantics,position):
    new=rediscovery=0
    for semantic in semantics:
        previous=state["seen_semantics"].get(semantic)
        if previous is None: new+=1
        elif previous < position-1: rediscovery+=1
        state["seen_semantics"][semantic]=position
    return new,rediscovery

def compact_history(history):
    result={}
    for sha,e in history.items():
        result[sha]={
            "genome":e["genome"],"source_sha256":e["source_sha256"],
            "semantic_sha256":e["semantic_sha256"],
            "parent_source_sha256":e.get("parent_source_sha256"),
            "search_parent_source_sha256":e.get("search_parent_source_sha256"),
            "construction":e.get("construction",{}),
            "donor_source_sha256":e.get("donor_source_sha256"),
            "successes":e["successes"],
            "first_success_position":e["first_success_position"],
            "last_success_position":e["last_success_position"],
        }
    return result

def call_receipts(calls,slots):
    rows=[]
    for index,call in enumerate(calls):
        ev=call["evaluation"]; genome=call["genome"]
        rows.append({
            "index":index,
            "kind":call["kind"],
            "source_sha256":native.descriptor(genome)["source_sha256"],
            "genome":genome,
            "evaluation":ev,
            "construction":call.get("construction",{"kind":call["kind"]}),
            "solving_candidate":ev["matched_slots"]==slots,
            "negative_candidate":ev["matched_slots"]<slots,
        })
    return rows

def verify_coded_state(state):
    motifs=[list(x) for x in state["motifs"]]
    if len(motifs)!=4: return
    for key,expected in state["code_hashes"].items():
        code=coded_native.design_code(motifs,int(key))
        if code is None or code["code_sha256"]!=expected:
            raise ValueError("Persisted V2 codebook failed recovery")

def run_coded(tasks,state,*,isolated):
    verify_coded_state(state)
    rows=[]; epoch=tasks[0]["epoch"]; code=None
    if epoch>=3:
        motifs=[list(x) for x in state["motifs"]]
        if len(motifs)==4:
            blocks=tasks[0]["slots"]//coded_native.BLOCK
            code=coded_native.design_code(motifs,blocks)
            if code is not None:
                old=state["code_hashes"].get(str(blocks))
                if old is not None and old!=code["code_sha256"]:
                    raise ValueError("V2 codebook changed after persistence")
                state["code_hashes"][str(blocks)]=code["code_sha256"]

    for task in tasks:
        position=state["position"]
        if epoch<3:
            result=coded_native.acquire(task,isolated=isolated)
        elif code is not None:
            result=coded_native.solve(task,[list(x) for x in state["motifs"]],code,isolated=isolated)
        else:
            result={"solved":False,"genome":None,"calls":[]}
        charged=len(result["calls"])
        if charged>14: raise ValueError("V2 coded arm escaped cap")
        receipts=call_receipts(result["calls"],task["slots"])
        semantics=[]
        if result["solved"] and result["genome"] is not None:
            desc=native.descriptor(result["genome"]); semantics=[desc["semantic_sha256"]]
            if epoch==2 and len(result["genome"]["ops"])==coded_native.BLOCK:
                motif=list(result["genome"]["ops"]); known={tuple(x) for x in state["motifs"]}
                if tuple(motif) not in known:
                    state["motifs"].append(motif); state["motifs"].sort()
        new,rediscovery=semantic_ledger(state,semantics,position)
        rows.append({
            "task_id":task["task_id"],"task_sha256":digest(task),
            "solved":bool(result["solved"]),"charged_evaluations":charged,
            "semantics":semantics,"new_semantics":new,"rediscoveries":rediscovery,
            "candidates":receipts,
        })
        state["position"]=position+1
    return rows,state

def run_control(tasks,state,arm,*,isolated):
    control={"archive-g7":"archive","greedy-g7":"greedy","cold-g7":"cold"}[arm]
    history=state.get("history",{}); rows=[]
    for task in tasks:
        position=state["position"]; actor={} if control=="cold" else history
        result=v36.episode(task,position,actor,control,isolated=isolated)
        if result["charged_evaluations"]>14: raise ValueError("V2 control escaped cap")
        semantics=sorted({p["semantic_sha256"] for p in result["programs"]
                          if p["evaluation"]["matched_slots"]==task["slots"]})
        new,rediscovery=semantic_ledger(state,semantics,position)
        rows.append({
            "task_id":task["task_id"],"task_sha256":digest(task),
            "solved":bool(result["solved"]),
            "charged_evaluations":result["charged_evaluations"],
            "semantics":semantics,"new_semantics":new,"rediscoveries":rediscovery,
            "candidates":call_receipts(result["calls"],task["slots"]),
        })
        if control!="cold": history=v36.history_from([result],history)
        state["position"]=position+1
    state["history"]=compact_history(history)
    return rows,state

def run_epoch(tasks,arm,state=None,*,isolated=True):
    if arm not in ARMS or not tasks: raise ValueError("Invalid V2 epoch request")
    state=default_state(arm) if state is None else state
    before=digest(state)
    rows,state=(run_coded(tasks,state,isolated=isolated) if arm=="coded-archive"
                else run_control(tasks,state,arm,isolated=isolated))
    after=digest(state)
    candidate_count=sum(len(r["candidates"]) for r in rows)
    negative_count=sum(sum(c["negative_candidate"] for c in r["candidates"]) for r in rows)
    summary={
        "arm":arm,"domain":tasks[0]["domain"],"epoch":tasks[0]["epoch"],
        "tasks":len(rows),"solved":sum(r["solved"] for r in rows),
        "evaluations":sum(r["charged_evaluations"] for r in rows),
        "max_task_evaluations":max(r["charged_evaluations"] for r in rows),
        "candidate_receipts":candidate_count,"negative_candidate_receipts":negative_count,
        "first_solving_semantics":sum(r["new_semantics"] for r in rows),
        "rediscoveries":sum(r["rediscoveries"] for r in rows),
        "failures":[r["task_id"] for r in rows if not r["solved"]],
        "state_before_sha256":before,"state_after_sha256":after,
        "motif_parents":len(state.get("motifs",[])),
        "codebook_descendants":len(state.get("code_hashes",{})),
        "code_hashes":dict(state.get("code_hashes",{})),
        "records":rows,
    }
    return summary,state

def epoch_tasks(domain,epoch):
    return [t for t in bank.stream(domain) if t["epoch"]==epoch]

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--arm",choices=ARMS,required=True); p.add_argument("--domain",choices=native.DOMAINS,required=True)
    p.add_argument("--epoch",type=int,required=True); p.add_argument("--state",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    args=p.parse_args(argv)
    if not 0<=args.epoch<bank.EPOCHS: raise ValueError("V2 epoch outside frozen schedule")
    if args.output.exists(): raise ValueError("V2 refuses pre-existing epoch output")
    state=load_state(args.state,args.arm,args.epoch)
    summary,state=run_epoch(epoch_tasks(args.domain,args.epoch),args.arm,state,isolated=True)
    args.state.parent.mkdir(parents=True,exist_ok=True); args.output.parent.mkdir(parents=True,exist_ok=True)
    args.state.write_text(json.dumps(state,sort_keys=True,separators=(",",":"))+"\n")
    args.output.write_text(json.dumps(summary,sort_keys=True,separators=(",",":"))+"\n")
    print(json.dumps({k:v for k,v in summary.items() if k!="records"},sort_keys=True))

if __name__=="__main__": main()
