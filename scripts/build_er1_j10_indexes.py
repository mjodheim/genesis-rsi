from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

from genesis import repair_strategist
from scripts.build_er1_j9_indexes import inherited_j8, j9_successor


def write_jsonl(path: Path, records: list[dict]) -> str:
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inherited_j9(root: Path, prefix: str, budget: int) -> tuple[list[dict], dict]:
    j8, _ = inherited_j8(root, prefix, budget)
    j9, meta = j9_successor(root, prefix, budget, j8)
    return j9, meta


def main() -> int:
    p=argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--focus-paths-json", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--budget", type=int, default=10000)
    p.add_argument("--planner-front-budget", type=int, default=1200)
    a=p.parse_args()

    focus=json.loads(a.focus_paths_json.read_text())
    baseline, base_meta=inherited_j9(a.root,a.prefix,a.budget)

    planner=repair_strategist.generate(
        a.root,
        include_prefixes=[a.prefix],
        focus_paths=focus,
        max_candidates=min(a.planner_front_budget,a.budget),
        composition_fraction=0.40,
    )
    front=[dict(x) for x in planner["candidates"]]
    for x in front:
        x.pop("logical_index",None)

    successor=[]
    for rec in front:
        if len(successor)>=a.budget: break
        successor.append(rec)
    for rec in baseline:
        if len(successor)>=a.budget: break
        item=dict(rec); item.pop("logical_index",None)
        successor.append(item)
    for i,r in enumerate(baseline):
        r["logical_index"]=i
    for i,r in enumerate(successor):
        r["logical_index"]=i

    a.output_dir.mkdir(parents=True,exist_ok=True)
    bsha=write_jsonl(a.output_dir/"BASELINE_INDEX.jsonl",baseline)
    ssha=write_jsonl(a.output_dir/"SUCCESSOR_INDEX.jsonl",successor)

    planner_summary={k:v for k,v in planner.items() if k!="candidates"}
    summary={
        "schema":"genesis-er1-j10-index-summary-v1",
        "budget":a.budget,
        "prefix":a.prefix,
        "focus_paths":focus,
        "baseline_count":len(baseline),
        "successor_count":len(successor),
        "baseline_index_sha256":bsha,
        "successor_index_sha256":ssha,
        "indexes_byte_identical":bsha==ssha,
        "baseline_description":"frozen J9 successor machinery",
        "successor_description":"frozen ER2 planner front then frozen J9 successor fallback",
        "planner_front_count":len(front),
        "fallback_count":max(0,len(successor)-len(front)),
        "planner_summary":planner_summary,
        "external_model_calls":0,
        **base_meta,
    }
    (a.output_dir/"INDEX_SUMMARY.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8"
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
