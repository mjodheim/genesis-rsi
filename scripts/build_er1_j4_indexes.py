from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import java_progress_mutations
from genesis import java_structural_mutations
from genesis import scalar_mutations
from genesis.trust_root import digest_of


def balanced_scalar(root: Path, prefix: str, budget: int) -> list[dict]:
    files=[]; total=0
    for path in scalar_mutations._eligible_files(root, include_prefixes=[prefix]):
        relative=path.relative_to(root).as_posix()
        try:
            text=path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        sites=scalar_mutations._site_alternatives(text)
        if not sites:
            continue
        expected=scalar_mutations._sha256_text(text)
        files.append({
            "path":relative,
            "text":text,
            "expected_sha256":expected,
            "sites":sites,
        })
        total += len(sites)

    out=[]; round_index=0
    while len(out)<budget:
        progress=False
        for fr in files:
            if round_index>=len(fr["sites"]):
                continue
            progress=True
            start,end,replacement,operator=fr["sites"][round_index]
            text=fr["text"]; relative=fr["path"]
            payload={
                "path":relative,"start":start,"end":end,"before":text[start:end],
                "after":replacement,"operator":operator,
                "expected_sha256":fr["expected_sha256"],
            }
            cd=digest_of(payload)
            out.append({
                "index":len(out),
                "id":f"scalar-{cd[:16]}",
                "candidate_digest":cd,
                **payload,
            })
            if len(out)>=budget:
                break
        if not progress:
            break
        round_index += 1
    return out


def predecessor(root: Path, prefix: str, budget: int) -> tuple[list[dict], dict]:
    scalar=balanced_scalar(root,prefix,budget)
    structural=java_structural_mutations.generate(
        root,include_prefixes=[prefix],max_candidates=budget
    )["candidates"]
    out=[]; si=ji=0
    while len(out)<budget and (si<len(scalar) or ji<len(structural)):
        if ji<len(structural) and len(out)<budget:
            out.append({"kind":"java_structural",**dict(structural[ji])}); ji+=1
        if si<len(scalar) and len(out)<budget:
            out.append({"kind":"scalar",**dict(scalar[si])}); si+=1
    for i,r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "scalar_available":len(scalar),
        "structural_available":len(structural),
        "predecessor_structural_count":sum(r["kind"]=="java_structural" for r in out),
        "predecessor_scalar_count":sum(r["kind"]=="scalar" for r in out),
    }


def successor(root: Path, prefix: str, budget: int, predecessor_records: list[dict]) -> tuple[list[dict],dict]:
    progress=java_progress_mutations.generate(
        root,include_prefixes=[prefix],max_candidates=budget
    )["candidates"]
    out=[]; pi=bi=0
    while len(out)<budget and (pi<len(progress) or bi<len(predecessor_records)):
        if pi<len(progress) and len(out)<budget:
            out.append({"kind":"java_progress",**dict(progress[pi])}); pi+=1
        if bi<len(predecessor_records) and len(out)<budget:
            base=dict(predecessor_records[bi]); base.pop("logical_index",None)
            out.append(base); bi+=1
    for i,r in enumerate(out):
        r["logical_index"]=i
    return out,{
        "progress_available":len(progress),
        "successor_progress_count":sum(r["kind"]=="java_progress" for r in out),
        "successor_predecessor_count":sum(r["kind"]!="java_progress" for r in out),
    }


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

    baseline,base_meta=predecessor(a.root,a.prefix,a.budget)
    succ,succ_meta=successor(a.root,a.prefix,a.budget,baseline)

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",succ)
    summary={
        "schema":"genesis-er1-j4-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "baseline_count":len(baseline),
        "successor_count":len(succ),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "successor_schedule":"alternate_java_progress_then_frozen_predecessor_order_until_progress_exhausts_then_fill_from_predecessor",
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
