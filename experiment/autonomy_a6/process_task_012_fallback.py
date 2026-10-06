from __future__ import annotations
import hashlib, json, os, shutil, subprocess, tempfile, time
from pathlib import Path
from genesis import patch_templates
from genesis.trust_root import digest_of

ROOT=Path("/home/anthony/mira-genesis-autonomy")
HERE=ROOT/"experiment/autonomy_a6"
SOURCE=Path("/home/anthony/experiments/a6v2-c016")
RAW=HERE/"task_012_fallback_raw.json"
RESULT=HERE/"task_012_fallback_result.json"
EVALUATOR=HERE/"task_012_eval.cjs"
AUTO=HERE/"task_012_autonomous_result.json"

def sha(t:str)->str: return hashlib.sha256(t.encode()).hexdigest()
def copy_repo(src,dst):
    shutil.copytree(src,dst,ignore=shutil.ignore_patterns(".git","node_modules","dist","build","coverage"),symlinks=False)
def run_eval(ws):
    st=time.monotonic()
    p=subprocess.run(["node",str(EVALUATOR),str(ws)],cwd=ws,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,check=False)
    out=p.stdout.decode(errors="replace"); parsed=None
    if out.strip():
        try: parsed=json.loads(out.strip().splitlines()[-1])
        except json.JSONDecodeError: pass
    return {"exit_code":p.returncode,"elapsed_ms":int((time.monotonic()-st)*1000),"stdout":out,"stderr":p.stderr.decode(errors="replace"),"parsed":parsed}

raw=json.loads(RAW.read_text()); proposal=raw.get("structured_output")
if not isinstance(proposal,dict): raise SystemExit("no structured output")
pairs=[]; applied=[]
with tempfile.TemporaryDirectory(prefix="genesis-a6-t12-fb-") as td:
    ws=Path(td)/"workspace"; copy_repo(SOURCE,ws)
    for e in proposal["edits"]:
        supplied=Path(e["path"])
        rel=supplied.resolve().relative_to(SOURCE.resolve()).as_posix() if supplied.is_absolute() else supplied.as_posix()
        p=(ws/rel).resolve()
        if not str(p).startswith(str(ws.resolve())+os.sep) or not p.is_file(): raise SystemExit(f"unsafe/missing path {rel}")
        old,new=str(e["old"]),str(e["new"]); before=p.read_text()
        if before.count(old)!=1: raise SystemExit(f"old count !=1: {rel}")
        after=before.replace(old,new,1); p.write_text(after)
        pairs.append((before,after)); applied.append({"path":rel,"old_sha256":sha(before),"new_sha256":sha(after)})
    evaluation=run_eval(ws)
patch_digest=digest_of({"proposal":proposal,"applied":applied})
learned=[]
if evaluation["exit_code"]==0:
    for before,after in pairs: learned.extend(patch_templates.learn_from_texts(before,after,source_digest=patch_digest))
uniq={x["template_digest"]:x for x in learned}; learned=list(uniq.values())
auto=json.loads(AUTO.read_text())
payload={"schema":"mira-genesis-a6-task012-fallback-result-v1","autonomous_result_digest":auto["report_digest"],"model":"claude-sonnet-5-5","model_calls":1,"cost_usd":raw.get("total_cost_usd"),"proposal":proposal,"applied":applied,"patch_digest":patch_digest,"evaluation":evaluation,"fallback_passed":evaluation["exit_code"]==0,"learned_template_count":len(learned),"learned_templates":learned,"learned_template_digests":[x["template_digest"] for x in learned],"manual_candidate_repair":False,"retry_count":0}
res={**payload,"report_digest":digest_of(payload)}
RESULT.write_text(json.dumps(res,indent=2,sort_keys=True)+"\n")
print(json.dumps({"fallback_passed":res["fallback_passed"],"cost_usd":res["cost_usd"],"learned_template_count":len(learned),"report_digest":res["report_digest"]},indent=2))
raise SystemExit(0 if res["fallback_passed"] else 1)
