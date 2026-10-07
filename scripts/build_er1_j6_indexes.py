from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_range_mutations, java_symbol_mutations
from scripts.build_er1_j4_indexes import predecessor, successor as j4_successor


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def j5_baseline(root: Path, prefix: str, budget: int) -> tuple[list[dict], dict]:
    pred, _ = predecessor(root, prefix, budget)
    j4, _ = j4_successor(root, prefix, budget, pred)

    symbols = java_symbol_mutations.generate(
        root, include_prefixes=[prefix], max_candidates=budget
    )["candidates"]
    out=[]; si=bi=0
    while len(out)<budget and (si<len(symbols) or bi<len(j4)):
        if si<len(symbols) and len(out)<budget:
            out.append({"kind":"java_symbol", **dict(symbols[si])}); si += 1
        if bi<len(j4) and len(out)<budget:
            rec=dict(j4[bi]); rec.pop("logical_index", None)
            out.append(rec); bi += 1
    for i, r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "symbol_available":len(symbols),
        "baseline_symbol_count":sum(r.get("kind")=="java_symbol" for r in out),
        "baseline_inherited_count":sum(r.get("kind")!="java_symbol" for r in out),
    }


def j6_successor(root: Path, prefix: str, budget: int, baseline: list[dict]) -> tuple[list[dict], dict]:
    ranges = java_range_mutations.generate(
        root, include_prefixes=[prefix], max_candidates=budget
    )["candidates"]
    out=[]; ri=bi=0
    while len(out)<budget and (ri<len(ranges) or bi<len(baseline)):
        if ri<len(ranges) and len(out)<budget:
            out.append({"kind":"java_range", **dict(ranges[ri])}); ri += 1
        if bi<len(baseline) and len(out)<budget:
            rec=dict(baseline[bi]); rec.pop("logical_index",None)
            out.append(rec); bi += 1
    for i, r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "range_available":len(ranges),
        "successor_range_count":sum(r.get("kind")=="java_range" for r in out),
        "successor_baseline_count":sum(r.get("kind")!="java_range" for r in out),
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--budget", type=int, default=10000)
    a=p.parse_args()

    baseline, base_meta=j5_baseline(a.root,a.prefix,a.budget)
    successor, succ_meta=j6_successor(a.root,a.prefix,a.budget,baseline)

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)
    summary={
        "schema":"genesis-er1-j6-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "baseline_count":len(baseline),
        "successor_count":len(successor),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "successor_schedule":"alternate_java_range_then_frozen_j5_successor_order_until_range_exhausts_then_fill_from_j5_successor",
        "external_model_calls":0,
        **base_meta,
        **succ_meta,
    }
    (a.output_dir/"INDEX_SUMMARY.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    print(json.dumps(summary,sort_keys=True))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
