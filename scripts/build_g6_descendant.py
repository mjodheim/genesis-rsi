"""Generate and freeze a G6 descendant from prior G5 evidence only."""
from __future__ import annotations
import argparse, json, hashlib
from pathlib import Path
from genesis.evolution import component_evolution
from genesis.trust_root import digest_of

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--repository-root",type=Path,required=True)
    p.add_argument("--preregistration",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--source-output",type=Path,required=True)
    a=p.parse_args()
    root=a.repository_root.resolve()
    prereg=json.loads(a.preregistration.read_text())
    parent=(root/"genesis/operators/universal.py").read_text()
    if hashlib.sha256(parent.encode()).hexdigest()!=prereg["parent_component"]["source_sha256"]:
        raise SystemExit("parent source differs from preregistration")
    g5pre=json.loads((root/"experiment/g5_qualification/PREREGISTRATION.json").read_text())
    g5hold=json.loads((root/"experiment/g5_qualification/HOLDOUT_REVEALED.json").read_text())
    op=g5pre["source_capability"]["universal_operator"]
    examples=[]
    failed=None
    for case in g5hold["cases"]:
        ex=component_evolution.TrainingExample(case["id"],"Program.cs",case["files"]["Program.cs"],True)
        examples.append(ex)
        if case["id"]=="method-call": failed=ex
    examples.extend([
      component_evolution.TrainingExample("decoy-equality","Program.cs","class P { static bool F(int x)=>x==1; }\n",False),
      component_evolution.TrainingExample("decoy-call","Program.cs","class P { static int G(int x)=>x; static int F()=>G(1); }\n",False),
      component_evolution.TrainingExample("decoy-literal","Program.cs","class P { static int F()=>1; }\n",False),
    ])
    if failed is None: raise SystemExit("missing G5 failed example")
    result=component_evolution.evolve_component(parent,operator=op,failed_example=failed,training_examples=examples)
    selected=result["selected_descendant"]
    payload={"schema":"genesis-g6-lineage-descendant-v1","preregistration_digest":prereg["preregistration_digest"],"selection":result,"selected_source_sha256":selected["source_sha256"],"parent_source_sha256":selected["parent_source_sha256"],"hidden_holdout_visible":False,"external_model_calls":0}
    payload["descendant_record_digest"]=digest_of(payload)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    a.source_output.parent.mkdir(parents=True,exist_ok=True)
    a.source_output.write_text(selected["source_utf8"])
    return 0
if __name__=="__main__": raise SystemExit(main())
