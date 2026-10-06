"""Prospective L9-OE1 v2 campaign with fail-closed state and full receipts."""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from experiment.l9_oe1_v2 import bank, epoch as epoch_runner
from experiment.rsi_v25.commitments import ROOT
from experiment.rsi_v35 import native

ARMS=epoch_runner.ARMS
TRANSFER_EPOCHS=tuple(range(3,bank.EPOCHS))

def run_stream(arm,domain,directory):
    stream_dir=directory/arm/domain
    if stream_dir.exists():
        raise ValueError("V2 stream directory must not pre-exist")
    stream_dir.mkdir(parents=True)
    state_path=stream_dir/"state.json"; records=[]; previous=None
    for epoch in range(bank.EPOCHS):
        output=stream_dir/f"epoch-{epoch:02d}.json"
        cmd=[sys.executable,"-m","experiment.l9_oe1_v2.epoch","--arm",arm,"--domain",domain,
             "--epoch",str(epoch),"--state",str(state_path),"--output",str(output)]
        env={**os.environ,"PYTHONHASHSEED":"0","LC_ALL":"C"}
        result=subprocess.run(cmd,cwd=ROOT,env=env,text=True,capture_output=True,timeout=900)
        if result.returncode:
            raise RuntimeError(f"V2 epoch failed {arm}/{domain}/{epoch}: "+result.stderr[-1500:])
        row=json.loads(output.read_text())
        if epoch==0 and row["state_before_sha256"]!=epoch_runner.default_state_sha256(arm):
            raise ValueError("V2 epoch zero did not start from default state")
        if previous is not None and row["state_before_sha256"]!=previous:
            raise ValueError("V2 state digest chain mismatch")
        previous=row["state_after_sha256"]; records.append(row)
    return {"arm":arm,"domain":domain,"epochs":records}

def transfer_rows(stream):
    return [r for r in stream["epochs"] if r["epoch"] in TRANSFER_EPOCHS]

def solve_rate(rows):
    n=sum(r["tasks"] for r in rows)
    return sum(r["solved"] for r in rows)/n if n else 0.0

def evals(rows): return sum(r["evaluations"] for r in rows)

def adjudicate(streams):
    by={(s["arm"],s["domain"]):s for s in streams}
    def rows(arm,domain,transfer=False):
        values=by[(arm,domain)]["epochs"]; return transfer_rows(by[(arm,domain)]) if transfer else values
    coded=[r for d in native.DOMAINS for r in rows("coded-archive",d,True)]
    archive=[r for d in native.DOMAINS for r in rows("archive-g7",d,True)]
    greedy=[r for d in native.DOMAINS for r in rows("greedy-g7",d,True)]
    cold=[r for d in native.DOMAINS for r in rows("cold-g7",d,True)]

    expected=bank.EPOCHS*bank.TASKS_PER_EPOCH
    all_records=all(len(s["epochs"])==bank.EPOCHS and sum(r["tasks"] for r in s["epochs"])==expected for s in streams)
    initial_exact=all(s["epochs"][0]["state_before_sha256"]==epoch_runner.default_state_sha256(s["arm"]) for s in streams)
    recovery=all(all(s["epochs"][i]["state_before_sha256"]==s["epochs"][i-1]["state_after_sha256"] for i in range(1,len(s["epochs"]))) for s in streams)
    caps=all(r["max_task_evaluations"]<=14 for s in streams for r in s["epochs"])

    receipts_exact=True; failures_retained=True; zero_windows_retained=True
    negative_total=0
    for s in streams:
        for row in s["epochs"]:
            if len(row["records"])!=row["tasks"]: receipts_exact=False
            if sum(len(x["candidates"]) for x in row["records"])!=row["evaluations"]: receipts_exact=False
            if row["candidate_receipts"]!=row["evaluations"]: receipts_exact=False
            computed_failures=[x["task_id"] for x in row["records"] if not x["solved"]]
            if computed_failures!=row["failures"]: failures_retained=False
            computed_negative=sum(sum(c["negative_candidate"] for c in x["candidates"]) for x in row["records"])
            if computed_negative!=row["negative_candidate_receipts"]: receipts_exact=False
            negative_total+=computed_negative
            if "first_solving_semantics" not in row: zero_windows_retained=False

    coded_epoch=all(r["solved"]/r["tasks"]>=0.90 and r["first_solving_semantics"]>=4 for d in native.DOMAINS for r in rows("coded-archive",d,True))
    cr,ar,gr,xr=map(solve_rate,(coded,archive,greedy,cold))
    domain_margin=all(solve_rate(rows("coded-archive",d,True))-solve_rate(rows("archive-g7",d,True))>=0.05 for d in native.DOMAINS)
    branch=all(rows("coded-archive",d)[-1]["motif_parents"]==4
               and rows("coded-archive",d)[-1]["codebook_descendants"]==9
               and set(rows("coded-archive",d)[-1]["code_hashes"])=={str(b) for b in range(2,11)}
               for d in native.DOMAINS)
    rediscovery=all(r["rediscoveries"]>=1 for d in native.DOMAINS for r in rows("coded-archive",d,True))

    predicates={
      "all_materialized_tasks_retained":all_records,
      "epoch_zero_exact_default_and_recovery_chain_exact":initial_exact and recovery,
      "all_task_caps_respected":caps,
      "every_charged_candidate_receipt_retained":receipts_exact,
      "coded_transfer_solve_rate_at_least_95pct":cr>=0.95,
      "coded_each_transfer_epoch_domain_at_least_90pct_and_four_discoveries":coded_epoch,
      "coded_beats_archive_g7_by_15pp_aggregate":cr-ar>=0.15,
      "coded_beats_archive_g7_by_5pp_each_domain":domain_margin,
      "coded_beats_greedy_by_20pp_aggregate":cr-gr>=0.20,
      "coded_beats_cold_by_20pp_aggregate":cr-xr>=0.20,
      "coded_cost_no_more_than_archive_g7":sum(evals(rows("coded-archive",d)) for d in native.DOMAINS)<=sum(evals(rows("archive-g7",d)) for d in native.DOMAINS),
      "four_branch_motif_archive_and_nine_codebook_descendants":branch,
      "rediscovery_in_every_transfer_epoch_domain":rediscovery,
      "failures_zero_windows_and_negative_candidates_retained":failures_retained and zero_windows_retained and negative_total>0,
    }
    metrics={
      "coded_transfer_solve_rate":cr,"archive_g7_transfer_solve_rate":ar,
      "greedy_g7_transfer_solve_rate":gr,"cold_g7_transfer_solve_rate":xr,
      "coded_transfer_evaluations":evals(coded),"archive_g7_transfer_evaluations":evals(archive),
      "greedy_g7_transfer_evaluations":evals(greedy),"cold_g7_transfer_evaluations":evals(cold),
      "coded_first_solving_semantics":sum(r["first_solving_semantics"] for r in coded),
      "coded_rediscoveries":sum(r["rediscoveries"] for r in coded),
      "negative_candidate_receipts_retained":negative_total,
    }
    passed=all(predicates.values())
    return {"schema":"mira-genesis-l9-oe1-v2-adjudication-v1","predicates":predicates,"metrics":metrics,
            "operational_l9_passed":passed,
            "verdict":"L9_OPERATIONAL_GATE_PASSED" if passed else "VALID_NEGATIVE_L9_OPERATIONAL_QUALIFICATION_V2",
            "l10_independent_passed":False,
            "claim_boundary":"FINITE_PROSPECTIVE_L9_EVIDENCE_NOT_ASYMPTOTIC_THEOREM_NOT_L10"}

def run(directory,workers=4):
    from experiment.l9_oe1_v2 import freeze
    freeze.verify()
    if directory.exists():
        raise ValueError("V2 qualification output directory must not pre-exist")
    directory.mkdir(parents=True)
    jobs=[(a,d) for a in ARMS for d in native.DOMAINS]; streams=[]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fs={pool.submit(run_stream,a,d,directory):(a,d) for a,d in jobs}
        for f in as_completed(fs): streams.append(f.result())
    streams.sort(key=lambda x:(x["arm"],x["domain"]))
    return {"schema":"mira-genesis-l9-oe1-v2-report-v1",
            "population_file_sha256":bank.population_file_sha256(),
            "streams":streams,"adjudication":adjudicate(streams)}

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("--output",type=Path,required=True); p.add_argument("--workers",type=int,default=4)
    args=p.parse_args(argv)
    report=run(args.output.parent,args.workers)
    args.output.write_text(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n")
    print(json.dumps(report["adjudication"],sort_keys=True))

if __name__=="__main__": main()
