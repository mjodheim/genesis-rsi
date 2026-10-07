from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_symbol_mutations
from scripts.build_er1_j4_indexes import predecessor, successor as j4_successor


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

    pred,_=predecessor(a.root,a.prefix,a.budget)
    baseline,base_meta=j4_successor(a.root,a.prefix,a.budget,pred)

    symbols=java_symbol_mutations.generate(
        a.root,include_prefixes=[a.prefix],max_candidates=a.budget
    )["candidates"]

    succ=[]; si=bi=0
    while len(succ)<a.budget and (si<len(symbols) or bi<len(baseline)):
        if si<len(symbols) and len(succ)<a.budget:
            succ.append({"kind":"java_symbol",**dict(symbols[si])}); si+=1
        if bi<len(baseline) and len(succ)<a.budget:
            rec=dict(baseline[bi]); rec.pop("logical_index",None)
            succ.append(rec); bi+=1
    for i,r in enumerate(succ):
        r["logical_index"]=i

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",succ)
    summary={
        "schema":"genesis-er1-j5-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "baseline_count":len(baseline),
        "successor_count":len(succ),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "baseline_progress_count":sum(r.get("kind")=="java_progress" for r in baseline),
        "symbol_available":len(symbols),
        "successor_symbol_count":sum(r.get("kind")=="java_symbol" for r in succ),
        "successor_baseline_count":sum(r.get("kind")!="java_symbol" for r in succ),
        "successor_schedule":"alternate_java_symbol_then_frozen_j4_successor_order_until_symbol_exhausts_then_fill_from_j4_successor",
        "external_model_calls":0,
        "inherited_j4_meta":base_meta,
    }
    (a.output_dir/"INDEX_SUMMARY.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    print(json.dumps(summary,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
