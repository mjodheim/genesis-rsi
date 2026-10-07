from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_calendar_specialist, java_test_switch_mutations
from scripts.build_er1_j6_indexes import j5_baseline, j6_successor


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inherited_j7(root: Path, prefix: str, budget: int) -> tuple[list[dict], dict]:
    j5, _ = j5_baseline(root, prefix, budget)
    j6, _ = j6_successor(root, prefix, budget, j5)
    calendar = java_calendar_specialist.generate(
        root, include_prefixes=[prefix], max_candidates=budget
    )["candidates"]

    out=[]; ci=bi=0
    while len(out)<budget and (ci<len(calendar) or bi<len(j6)):
        if ci<len(calendar) and len(out)<budget:
            out.append({"kind":"java_calendar", **dict(calendar[ci])}); ci += 1
        if bi<len(j6) and len(out)<budget:
            rec=dict(j6[bi]); rec.pop("logical_index",None)
            out.append(rec); bi += 1
    for i,r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "calendar_available":len(calendar),
        "inherited_calendar_count":sum(r.get("kind")=="java_calendar" for r in out),
    }


def j8_successor(root: Path, prefix: str, budget: int, baseline: list[dict]) -> tuple[list[dict], dict]:
    guided = java_test_switch_mutations.generate(
        root, include_prefixes=[prefix], max_candidates=budget
    )["candidates"]

    out=[]; gi=bi=0
    while len(out)<budget and (gi<len(guided) or bi<len(baseline)):
        if gi<len(guided) and len(out)<budget:
            out.append({"kind":"java_test_switch", **dict(guided[gi])}); gi += 1
        if bi<len(baseline) and len(out)<budget:
            rec=dict(baseline[bi]); rec.pop("logical_index",None)
            out.append(rec); bi += 1
    for i,r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "test_switch_available":len(guided),
        "successor_test_switch_count":sum(r.get("kind")=="java_test_switch" for r in out),
        "successor_baseline_count":sum(r.get("kind")!="java_test_switch" for r in out),
    }


def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--root",type=Path,required=True)
    p.add_argument("--prefix",required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    p.add_argument("--budget",type=int,default=10000)
    a=p.parse_args()

    baseline, base_meta=inherited_j7(a.root,a.prefix,a.budget)
    successor, succ_meta=j8_successor(a.root,a.prefix,a.budget,baseline)

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)
    summary={
        "schema":"genesis-er1-j8-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "baseline_count":len(baseline),
        "successor_count":len(successor),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "indexes_byte_identical":bsha==ssha,
        "successor_schedule":"alternate_java_test_switch_then_frozen_j7_successor_order_until_test_switch_exhausts_then_fill_from_j7_successor",
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
