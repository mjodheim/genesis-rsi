"""Fresh V26 native two-locus/four-variant tasks; no consumed target is mutated."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps, run_search

HERE=ROOT/"experiment/rsi_v26"
CAPS=Caps()
TASKS=(
 {"task_id":"cellar-product-price-volume","source":"Product.java","harness":"ProductHarness.java","runtime":"java",
  "dependencies":["ProductType.java"],"loci":(
   ("price-fidelity",("this.price = price;","this.price = price.add(BigDecimal.ONE);",
                     "this.price = price.subtract(BigDecimal.ONE);","this.price = price.negate();")),
   ("volume-fidelity",("this.volumeMl = volumeMl;","this.volumeMl = volumeMl * 1000;",
                      "this.volumeMl = volumeMl / 1000;","this.volumeMl = volumeMl + 1;")))},
 {"task_id":"cellar-order-aggregate-preparation","source":"Order.java","harness":"OrderHarness.java","runtime":"java",
  "dependencies":["OrderLine.java","OrderStatus.java"],"loci":(
   ("preparation-transition",("status = OrderStatus.PREPARING;","status = OrderStatus.CONFIRMED;",
                             "status = OrderStatus.DRAFT;","status = OrderStatus.CANCELLED;")),
   ("aggregate-total",("reduce(BigDecimal.ZERO, BigDecimal::add)","reduce(BigDecimal.ONE, BigDecimal::add)",
                       "reduce(BigDecimal.ZERO, BigDecimal::subtract)","reduce(BigDecimal.TEN, BigDecimal::add)")))},
 {"task_id":"arcade-pigeon-target-path-bounds","source":"pigeon.js","harness":"pigeon_harness.js","runtime":"node",
  "dependencies":[],"loci":(
   ("matching-target",("KINDS[kind].target === 'any' || KINDS[kind].target === st.id",
                      "KINDS[kind].target === 'any' && KINDS[kind].target === st.id","true","KINDS[kind].target !== st.id")),
   ("path-bounds",("x:Math.max(-20, Math.min(W + 20, pt.x)), y:Math.max(-20, Math.min(H + 20, pt.y))",
                   "x:Math.max(0, Math.min(W, pt.x)), y:Math.max(0, Math.min(H, pt.y))",
                   "x:Math.max(-40, Math.min(W + 40, pt.x)), y:Math.max(-40, Math.min(H + 40, pt.y))",
                   "x:pt.x, y:pt.y")))},
 {"task_id":"arcade-stack-rotation-board-edge","source":"stack.js","harness":"stack_harness.js","runtime":"node",
  "dependencies":[],"loci":(
   ("matrix-rotation",("matrix[0].map((_,i)=>matrix.map(row=>row[i]).reverse())","matrix",
                      "matrix[0].map((_,i)=>matrix.map(row=>row[i]))",
                      "matrix[0].map((_,i)=>matrix.map(row=>row[matrix[0].length-1-i]))")),
   ("board-edge",("bx>=COLS","bx>COLS","bx>=COLS-1","bx>=COLS+1")))},
)


def render(task,choices):
    if len(choices)!=2 or any(type(x)is not int or x not in range(4) for x in choices):
        raise ValueError("V26 native proposal outside its four-variant grammar")
    source=(HERE/"native_sources"/task["source"]).read_text()
    for (_,variants),choice in zip(task["loci"],choices):
        if source.count(variants[0])!=1:
            raise ValueError("V26 production mutation anchor changed or ambiguous")
        source=source.replace(variants[0],variants[choice])
    return source


def evaluate(task,choices):
    source=render(task,choices);harness=HERE/"native_harnesses"/task["harness"]
    with tempfile.TemporaryDirectory(prefix="v26-native-evaluator-") as tmp:
        directory=Path(tmp);native=directory/task["source"];native.write_text(source)
        if task["runtime"]=="java":
            deps=[str(HERE/"native_sources"/name) for name in task["dependencies"]]
            compiled=subprocess.run(["java","com.sun.tools.javac.Main","-d",str(directory/"classes"),
                                      str(native),*deps,str(harness)],capture_output=True,text=True,timeout=20)
            if compiled.returncode:raise RuntimeError("V26 Java instrument failed: "+compiled.stderr[:2000])
            command=["java","-cp",str(directory/"classes"),harness.stem]
        else:command=["node",str(harness),str(native)]
        completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
        if completed.returncode:raise RuntimeError("V26 native instrument failed: "+completed.stderr[:2000])
        cases=json.loads(completed.stdout)
    if (set(cases)!={"passed","total","failed"} or type(cases["passed"])is not int
        or type(cases["total"])is not int or not 0<=cases["passed"]<=cases["total"] or cases["total"]<=0
        or cases["total"]-cases["passed"]!=len(cases["failed"])):
        raise ValueError("Malformed V26 native evaluator receipt")
    return {"accepted":True,"source_sha256":digest_bytes(source.encode()),"quality_milli":cases["passed"]*1000//cases["total"],
            "cases":cases,"cases_sha256":digest(cases),"task_sha256":digest(task),
            "harness_sha256":digest_bytes(harness.read_bytes()),"native_source_executed":True,"runtime":task["runtime"]}


def calibration():
    rows=[]
    for task in TASKS:
        reference,seeded=evaluate(task,(0,0)),evaluate(task,(1,1))
        if reference["quality_milli"]!=1000 or seeded["quality_milli"]==1000:
            raise ValueError("V26 reference or seed failed semantic calibration")
        rows.append({"task_id":task["task_id"],"reference":reference,"seeded":seeded})
    return {"scope":"REFERENCE_AND_SEEDED_ROOT_CALIBRATION_ONLY","tasks":rows,
            "population_sha256":digest(TASKS),"successor_executed":False}


class Host:
    def __init__(self,task,seeded):
        self.task,self.seeded=task,seeded
        self.forbidden_tokens=[task["task_id"],task["source"],task["harness"]]
    def row(self,choices):
        return {"candidate":{"choices":list(choices)},"source_sha256":digest_bytes(render(self.task,choices).encode())}
    def root(self):
        return {**self.row((1,1)),"quality_milli":self.seeded["quality_milli"]}
    def children(self,candidate,depth):
        if depth>=CAPS.mutation_depth:return ()
        parent=candidate["choices"];result=[]
        for axis in range(2):
            for value in range(4):
                if value!=parent[axis]:
                    child=list(parent);child[axis]=value;result.append(self.row(child))
        return tuple(sorted(result,key=lambda row:row["source_sha256"]))
    def evaluate(self,row):
        return evaluate(self.task,row["candidate"]["choices"])
    def action(self,row):
        choices=row["candidate"]["choices"]
        changed=[name for (name,_),value in zip(self.task["loci"],choices) if value!=1]
        return {"family":"native-production-repair","target_axes":changed,"changed_regions":changed,
                "mechanisms":[f"expression-{i}-{value}" for i,value in enumerate(choices) if value!=1] or ["seeded-root"]}
    def generation(self,row,depth):
        return 0


def run(source,calibration,checkpoint=None):
    roots={row["task_id"]:row["seeded"] for row in calibration["tasks"]};result=[]
    for task in TASKS:
        result.append({"task_id":task["task_id"],**run_search(source,Host(task,roots[task["task_id"]]),caps=CAPS,isolated=True)})
        if checkpoint:checkpoint(result)
    return result
