from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_calendar_specialist
from scripts.build_er1_j6_indexes import j5_baseline, j6_successor


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("w",encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec,sort_keys=True,separators=(",",":"))+"\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--prefix",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--budget",type=int,default=10000)
    a=p.parse_args()

    j5,_=j5_baseline(a.root,a.prefix,a.budget)
    baseline,_=j6_successor(a.root,a.prefix,a.budget,j5)

    specialist=java_calendar_specialist.generate(
        a.root,include_prefixes=[a.prefix],max_candidates=a.budget
    )["candidates"]

    successor=[]; si=bi=0
    while len(successor)<a.budget and (si<len(specialist) or bi<len(baseline)):
        if si<len(specialist) and len(successor)<a.budget:
            successor.append({"kind":"java_calendar",**dict(specialist[si])}); si+=1
        if bi<len(baseline) and len(successor)<a.budget:
            rec=dict(baseline[bi]); rec.pop("logical_index",None)
            successor.append(rec); bi+=1
    for i,r in enumerate(successor):
        r["logical_index"]=i

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)
    summary={
        "schema":"genesis-er1-j7-index-summary-v1",
        "budget":a.budget,"prefix":a.prefix,
        "baseline_count":len(baseline),"successor_count":len(successor),
        "baseline_index_sha256":bsha,"successor_index_sha256":ssha,
        "calendar_specialist_available":len(specialist),
        "successor_calendar_count":sum(r.get("kind")=="java_calendar" for r in successor),
        "successor_baseline_count":sum(r.get("kind")!="java_calendar" for r in successor),
        "successor_schedule":"alternate_java_calendar_then_frozen_j6_successor_order_until_specialist_exhausts_then_fill_from_j6_successor",
        "external_model_calls":0,
    }
    (a.output_dir/"INDEX_SUMMARY.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n")
    print(json.dumps(summary,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
