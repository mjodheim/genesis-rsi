from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_empty_segment_parser_mutations
from scripts.build_er1_j8_indexes import inherited_j7, j8_successor


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inherited_j8(root: Path, prefix: str, budget: int) -> tuple[list[dict], dict]:
    j7, _ = inherited_j7(root, prefix, budget)
    j8, meta = j8_successor(root, prefix, budget, j7)
    return j8, meta


def j9_successor(root: Path, prefix: str, budget: int, baseline: list[dict]) -> tuple[list[dict], dict]:
    parser = java_empty_segment_parser_mutations.generate(
        root, include_prefixes=[prefix], max_candidates=budget
    )["candidates"]
    out=[]; pi=bi=0
    while len(out)<budget and (pi<len(parser) or bi<len(baseline)):
        if pi<len(parser) and len(out)<budget:
            out.append({"kind":"java_empty_segment", **dict(parser[pi])}); pi += 1
        if bi<len(baseline) and len(out)<budget:
            rec=dict(baseline[bi]); rec.pop("logical_index",None)
            out.append(rec); bi += 1
    for i,r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "empty_segment_available":len(parser),
        "successor_empty_segment_count":sum(r.get("kind")=="java_empty_segment" for r in out),
        "successor_baseline_count":sum(r.get("kind")!="java_empty_segment" for r in out),
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--prefix",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--budget",type=int,default=10000)
    a=p.parse_args()

    baseline, base_meta=inherited_j8(a.root,a.prefix,a.budget)
    successor, succ_meta=j9_successor(a.root,a.prefix,a.budget,baseline)

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)
    summary={
        "schema":"genesis-er1-j9-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "baseline_count":len(baseline),
        "successor_count":len(successor),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "indexes_byte_identical":bsha==ssha,
        "successor_schedule":"alternate_java_empty_segment_then_frozen_j8_successor_order_until_empty_segment_exhausts_then_fill_from_j8_successor",
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
