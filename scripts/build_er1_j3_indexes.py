from __future__ import annotations
import argparse,json
from pathlib import Path
from genesis import java_structural_mutations, scalar_mutations

def write_jsonl(path:Path, records:list[dict]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec,sort_keys=True,separators=(",",":"))+"\n")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--budget",type=int,default=10000)
    a=p.parse_args()

    scalar=scalar_mutations.generate_balanced_index(
        a.root,include_prefixes=["src/java"],max_candidates=a.budget
    )
    structural=java_structural_mutations.generate(
        a.root,include_prefixes=["src/java"],max_candidates=a.budget
    )
    baseline=[{"kind":"scalar",**dict(r)} for r in scalar["candidates"]]
    successor=[]
    si=ji=0
    while len(successor)<a.budget and (si<len(scalar["candidates"]) or ji<len(structural["candidates"])):
        if ji<len(structural["candidates"]) and len(successor)<a.budget:
            successor.append({"kind":"java_structural",**dict(structural["candidates"][ji])}); ji+=1
        if si<len(scalar["candidates"]) and len(successor)<a.budget:
            successor.append({"kind":"scalar",**dict(scalar["candidates"][si])}); si+=1
    for i,r in enumerate(baseline): r["logical_index"]=i
    for i,r in enumerate(successor): r["logical_index"]=i

    a.output_dir.mkdir(parents=True,exist_ok=True)
    write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)
    summary={
      "schema":"genesis-er1-j3-index-summary-v1",
      "budget":a.budget,
      "baseline_count":len(baseline),
      "successor_count":len(successor),
      "successor_structural_count":sum(r["kind"]=="java_structural" for r in successor),
      "successor_scalar_count":sum(r["kind"]=="scalar" for r in successor),
      "structural_available":structural["candidate_count"],
      "scalar_available":scalar["candidate_count"],
      "successor_schedule":"alternate_java_structural_then_scalar_until_one_exhausts_then_fill_from_remaining",
      "external_model_calls":0,
    }
    (a.output_dir/"INDEX_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True))
    return 0
if __name__=="__main__":
    raise SystemExit(main())
