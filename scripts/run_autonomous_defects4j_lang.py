#!/usr/bin/env python3
"""Run a persistent autonomous Defects4J Lang repair campaign.

The trusted adapter owns benchmark selection, hidden trigger execution and
solution reveal timing. Genesis owns repair generation plus retained
self-extension capability. No user interaction is required between cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genesis import external_repair_campaign as campaign
from genesis import external_repair_learning as learning
from genesis import failure_driven_self_extension as self_extension
from genesis import repair_strategist
from genesis.trust_root import digest_of
from scripts.build_er1_j9_indexes import inherited_j8, j9_successor


HOME = Path("/home/anthony")
BENCH = HOME / "benchmarks"
D4J_ROOT = BENCH / "defects4j-er1"
D4J = D4J_ROOT / "framework/bin/defects4j"
JDK = HOME / "tools/jdk11"
JAVA = JDK / "bin/java"
JAVAC = JDK / "bin/javac"
JUNIT = D4J_ROOT / "framework/projects/lib/junit-4.12-hamcrest-1.3.jar"
LANG_META = D4J_ROOT / "framework/projects/Lang"


def _sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _d4j_env() -> dict[str, str]:
    env = dict(os.environ)
    env["JAVA_HOME"] = str(JDK)
    env["PERL5LIB"] = str(HOME / "perl5/lib/perl5")
    env["PATH"] = ":".join(
        [
            str(HOME / "tools/bin"),
            str(JDK / "bin"),
            str(D4J_ROOT / "framework/bin"),
            env.get("PATH", ""),
        ]
    )
    env["TZ"] = "America/Los_Angeles"
    env["LANG"] = "C.UTF-8"
    env["LC_ALL"] = "C.UTF-8"
    return env


def _run(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
    timeout: int = 300,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=None if cwd is None else str(cwd),
        env=dict(env or _d4j_env()),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout[-4000:]}"
        )
    return result


def _d4j_export(root: Path, prop: str) -> list[str]:
    result = _run([str(D4J), "export", "-p", prop], cwd=root)
    values: list[str] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("Running ant "):
            continue
        values.append(line)
    return values


def _failing_count(output: str) -> int | None:
    matches = re.findall(r"Failing tests:\s*(\d+)", output)
    return int(matches[-1]) if matches else None


def _test_reference(root: Path) -> dict[str, Any]:
    compile_run = _run([str(D4J), "compile"], cwd=root, check=False, timeout=300)
    test_run = _run([str(D4J), "test"], cwd=root, check=False, timeout=300)
    return {
        "compile_exit": compile_run.returncode,
        "test_exit": test_run.returncode,
        "failing_tests": _failing_count(test_run.stdout),
        "compile_output_sha256": _sha_bytes(compile_run.stdout.encode()),
        "test_output_sha256": _sha_bytes(test_run.stdout.encode()),
    }


def _active_bug_ids() -> list[int]:
    result = _run([str(D4J), "bids", "-p", "Lang"])
    return [int(line.strip()) for line in result.stdout.splitlines() if line.strip().isdigit()]


def _triggers(bug_id: int) -> list[str]:
    path = LANG_META / "trigger_tests" / str(bug_id)
    result: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("--- "):
            result.append(line[4:].strip())
    if not result:
        raise RuntimeError(f"no trigger tests for Lang-{bug_id}")
    return result


def _focus_paths(bug_id: int, root: Path, source_prefix: str) -> list[str]:
    loaded = LANG_META / "loaded_classes" / f"{bug_id}.src"
    paths: set[str] = set()
    if loaded.is_file():
        for raw in loaded.read_text(encoding="utf-8").splitlines():
            name = raw.strip().split("$", 1)[0]
            if not name:
                continue
            rel = f"{source_prefix.strip('/')}/{name.replace('.', '/')}.java"
            if (root / rel).is_file():
                paths.add(rel)
    if not paths:
        # Fail closed to the source tree rather than guessing a particular file.
        for path in (root / source_prefix).rglob("*.java"):
            paths.add(path.relative_to(root).as_posix())
    return sorted(paths)


def _checkout(bug_id: int, suffix: str, destination: Path) -> None:
    shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            str(D4J),
            "checkout",
            "-p",
            "Lang",
            "-v",
            f"{bug_id}{suffix}",
            "-w",
            str(destination),
        ],
        timeout=300,
    )


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    return _sha_file(path)


def _build_index(
    buggy: Path,
    *,
    source_prefix: str,
    focus_paths: list[str],
    retained_memory: Mapping[str, Any],
    output: Path,
    budget: int,
    planner_front_budget: int,
) -> dict[str, Any]:
    inherited, _ = inherited_j8(buggy, source_prefix, budget)
    fallback, fallback_meta = j9_successor(buggy, source_prefix, budget, inherited)

    planner = repair_strategist.generate(
        buggy,
        include_prefixes=[source_prefix],
        focus_paths=focus_paths,
        max_candidates=min(planner_front_budget, budget),
        composition_fraction=0.40,
        retained_memory=retained_memory,
    )

    records: list[dict[str, Any]] = []
    for raw in planner["candidates"]:
        rec = dict(raw)
        rec.pop("logical_index", None)
        records.append(rec)
        if len(records) >= budget:
            break
    if len(records) < budget:
        for raw in fallback:
            rec = dict(raw)
            rec.pop("logical_index", None)
            records.append(rec)
            if len(records) >= budget:
                break
    for i, rec in enumerate(records):
        rec["logical_index"] = i

    index_sha = _write_jsonl(output, records)
    summary = {
        "schema": "genesis-autonomous-lang-index-v1",
        "candidate_budget": budget,
        "candidate_count": len(records),
        "index_sha256": index_sha,
        "source_prefix": source_prefix,
        "focus_paths": focus_paths,
        "planner_front_count": len(planner["candidates"]),
        "planner_summary": {k: v for k, v in planner.items() if k != "candidates"},
        "fallback_meta": fallback_meta,
        "external_model_calls": 0,
    }
    return summary


def _java_quote(value: str) -> str:
    return json.dumps(value)


def _oracle_source(
    *,
    class_name: str,
    source_prefix: str,
    bin_classes: str,
    bin_tests: str,
    triggers: list[str],
) -> str:
    pairs: list[tuple[str, str]] = []
    for trigger in triggers:
        klass, method = trigger.split("::", 1)
        pairs.append((klass, method))
    test_rows = ",\n        ".join(
        "{" + _java_quote(klass) + "," + _java_quote(method) + "}"
        for klass, method in pairs
    )
    return f"""import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.Permission;
import java.util.*;
import java.util.concurrent.*;
import javax.tools.*;
import org.junit.runner.*;

public final class {class_name} {{
    private static final String SOURCE_PREFIX={_java_quote(source_prefix)};
    private static final String BIN_CLASSES={_java_quote(bin_classes)};
    private static final String BIN_TESTS={_java_quote(bin_tests)};
    private static final String[][] TESTS={{
        {test_rows}
    }};
    private static final int MAX_REQUESTS=128;
    private final Path root;
    private final JavaCompiler compiler;
    private final String compileCp;
    private final List<URL> urls;

    static final class NoExitSecurityManager extends SecurityManager {{
        public void checkPermission(Permission p) {{}}
        public void checkPermission(Permission p, Object c) {{}}
        public void checkExit(int status) {{ throw new SecurityException("candidate exit blocked"); }}
    }}

    {class_name}(Path root, String compileCp, List<Path> deps) throws Exception {{
        this.root=root;
        this.compileCp=compileCp;
        this.compiler=ToolProvider.getSystemJavaCompiler();
        if (compiler==null) throw new IllegalStateException("no system compiler");
        this.urls=new ArrayList<>();
        urls.add(root.resolve(BIN_CLASSES).toUri().toURL());
        urls.add(root.resolve(BIN_TESTS).toUri().toURL());
        for (Path p:deps) urls.add(p.toUri().toURL());
    }}

    int compile(String rel) {{
        Path src=root.resolve(rel).normalize();
        Path allowed=root.resolve(SOURCE_PREFIX).normalize();
        if (!src.startsWith(allowed) || !Files.isRegularFile(src)) return 90;
        return compiler.run(null, null, new ByteArrayOutputStream(),
            "-proc:none","-encoding","UTF-8",
            "-cp",compileCp,
            "-d",root.resolve(BIN_CLASSES).toString(),
            src.toString());
    }}

    int test() throws Exception {{
        ThreadFactory factory=r -> {{ Thread t=new Thread(r,"candidate-test"); t.setDaemon(true); return t; }};
        ExecutorService executor=Executors.newSingleThreadExecutor(factory);
        Future<Integer> f=executor.submit(() -> {{
            try (URLClassLoader loader=new URLClassLoader(urls.toArray(new URL[0]), {class_name}.class.getClassLoader())) {{
                for (String[] spec : TESTS) {{
                    Class<?> klass=Class.forName(spec[0],true,loader);
                    Result result=new JUnitCore().run(Request.method(klass,spec[1]));
                    if (!result.wasSuccessful()) return 1;
                }}
                return 0;
            }}
        }});
        try {{ return f.get(30,TimeUnit.SECONDS); }}
        catch (TimeoutException e) {{ f.cancel(true); return 124; }}
        catch (ExecutionException e) {{ return 2; }}
        finally {{ executor.shutdownNow(); }}
    }}

    public static void main(String[] args) throws Exception {{
        if (args.length<2) return;
        Path root=Paths.get(args[0]).toAbsolutePath().normalize();
        String compileCp=args[1];
        List<Path> deps=new ArrayList<>();
        for (int i=2;i<args.length;i++) deps.add(Paths.get(args[i]));
        {class_name} o=new {class_name}(root,compileCp,deps);

        PrintWriter control=new PrintWriter(new OutputStreamWriter(new FileOutputStream(FileDescriptor.out),StandardCharsets.UTF_8),true);
        System.setOut(new PrintStream(new OutputStream(){{public void write(int b){{}}}},true,"UTF-8"));
        System.setErr(new PrintStream(new OutputStream(){{public void write(int b){{}}}},true,"UTF-8"));
        System.setSecurityManager(new NoExitSecurityManager());

        BufferedReader br=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8));
        String line;
        int requests=0;
        while (requests<MAX_REQUESTS && (line=br.readLine())!=null) {{
            requests++;
            String[] p=line.split("\\t",2);
            if (p.length!=2) {{ control.println("ERR\t64"); continue; }}
            long s=System.nanoTime();
            try {{
                int crc=0, trc=-1;
                if (p[0].equals("R")) trc=o.test();
                else {{
                    crc=o.compile(p[1]);
                    if (crc==0 && p[0].equals("T")) trc=o.test();
                }}
                long ms=(System.nanoTime()-s)/1_000_000L;
                control.println("OK\t"+crc+"\t"+trc+"\t"+ms);
            }} catch (Throwable t) {{
                long ms=(System.nanoTime()-s)/1_000_000L;
                control.println("ERR\t"+ms);
            }}
        }}
    }}
}}
"""


def _relative_or_absolute_cp(entries: list[str], base: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for raw in entries:
        if not raw:
            continue
        p = Path(raw)
        try:
            rel = p.resolve().relative_to(base.resolve()).as_posix()
            out.append({"relative": rel})
        except ValueError:
            out.append({"absolute": str(p)})
    return out


def _evaluator_source(config_path: Path) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations
import argparse, concurrent.futures, hashlib, json, os, shutil, subprocess, time
from pathlib import Path

CFG=json.loads(Path({str(config_path)!r}).read_text())
BASE=Path(CFG["buggy_root"])
WORK_ROOT=Path(CFG["workers_root"])
HARNESS=Path(CFG["harness_root"])
JAVA=CFG["java"]
CLASS_NAME=CFG["oracle_class"]
SOURCE_PREFIX=CFG["source_prefix"]
RELEVANT_PATHS=set(CFG["focus_paths"])
_worker=None
_oracle=None
_last_source=None

class OracleError(RuntimeError): pass

def _map_cp(item):
    if "relative" in item:
        return str(_worker/item["relative"])
    return item["absolute"]

def _start_oracle():
    global _oracle
    external=[_map_cp(x) for x in CFG["test_cp"] if "absolute" in x]
    process_cp=os.pathsep.join([str(HARNESS),*external])
    compile_cp=os.pathsep.join(_map_cp(x) for x in CFG["compile_cp"])
    _oracle=subprocess.Popen(
        [JAVA,"-Xmx64m","-cp",process_cp,CLASS_NAME,str(_worker),compile_cp,*external],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        text=True,bufsize=1,
    )

def init_worker():
    global _worker,_last_source
    WORK_ROOT.mkdir(parents=True,exist_ok=True)
    _worker=WORK_ROOT/f"w-{{os.getpid()}}"
    if _worker.exists(): shutil.rmtree(_worker)
    shutil.copytree(BASE,_worker,symlinks=False)
    _last_source=None
    _start_oracle()

def _ask_once(mode,relative):
    global _oracle
    if _oracle is None or _oracle.poll() is not None: _start_oracle()
    _oracle.stdin.write(f"{{mode}}\t{{relative}}\\n"); _oracle.stdin.flush()
    line=_oracle.stdout.readline().strip()
    if not line: raise OracleError("oracle_eof")
    parts=line.split("\t")
    if len(parts)==4 and parts[0]=="OK":
        return int(parts[1]),int(parts[2]),int(parts[3])
    raise OracleError("oracle_protocol")

def _ask(mode,relative):
    try: return _ask_once(mode,relative)
    except Exception:
        _start_oracle()
        return _ask_once(mode,relative)

def _restore(relative):
    global _last_source
    if _last_source is None:
        return None
    source=BASE/_last_source
    target=_worker/_last_source
    target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
    try:
        crc,_,_=_ask("C",_last_source)
    except Exception:
        return "baseline_restore_oracle"
    _last_source=None
    return None if crc==0 else "baseline_restore_compile"

def evaluate(rec):
    global _last_source
    idx=int(rec["logical_index"])
    relative=str(rec.get("path") or "")
    kind=str(rec.get("kind") or "")
    base={{"index":idx,"id":str(rec.get("id") or ""),"kind":kind}}
    if not relative.startswith(SOURCE_PREFIX.rstrip("/")+"/") or ".." in Path(relative).parts:
        return {{**base,"valid":False,"reason":"path_policy"}}
    if relative not in RELEVANT_PATHS:
        return {{**base,"candidate_digest":str(rec.get("candidate_digest") or ""),
          "path_sha256":hashlib.sha256(relative.encode()).hexdigest(),
          "operator":str(rec.get("operator") or ""),"valid":True,
          "compile_exit_code":None,"test_exit_code":None,"evaluator_error":None,
          "passed_trigger":False,"coverage_pruned":True,"elapsed_ms":0}}

    restore_error=_restore(relative)
    if restore_error:
        return {{**base,"valid":False,"reason":restore_error,"evaluator_error":restore_error}}
    target=_worker/relative
    text=target.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest()!=str(rec.get("expected_sha256") or ""):
        return {{**base,"valid":False,"reason":"base_hash"}}

    if kind=="scalar":
        start,end=int(rec["start"]),int(rec["end"])
        if start<0 or end<start or text[start:end]!=str(rec["before"]):
            return {{**base,"valid":False,"reason":"site_mismatch"}}
        mutated=text[:start]+str(rec["after"])+text[end:]
        operator=str(rec["operator"])
    elif "content_utf8" in rec:
        mutated=str(rec["content_utf8"])
        operator=str(rec.get("operator") or kind)
    else:
        return {{**base,"valid":False,"reason":"kind_policy"}}

    target.write_text(mutated,encoding="utf-8")
    started=time.monotonic()
    try:
        crc,trc,elapsed_ms=_ask("T",relative); err=None
    except Exception as exc:
        crc=None; trc=None; elapsed_ms=int((time.monotonic()-started)*1000); err=str(exc)
    _last_source=relative
    return {{**base,"candidate_digest":str(rec.get("candidate_digest") or ""),
      "path_sha256":hashlib.sha256(relative.encode()).hexdigest(),
      "operator":operator,"valid":True,"compile_exit_code":crc,"test_exit_code":trc,
      "evaluator_error":err,"passed_trigger":err is None and crc==0 and trc==0,
      "coverage_pruned":False,"elapsed_ms":elapsed_ms}}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--index",type=Path,required=True); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--workers",type=int,default=8); p.add_argument("--batch-size",type=int,default=32); p.add_argument("--max-candidates",type=int,default=10000)
    a=p.parse_args()
    records=[json.loads(x) for x in a.index.read_text().splitlines() if x.strip()][:a.max_candidates]
    shutil.rmtree(WORK_ROOT,ignore_errors=True)
    results=[]; winner=None
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,initializer=init_worker) as pool:
        for start in range(0,len(records),a.batch_size):
            current=list(pool.map(evaluate,records[start:start+a.batch_size]))
            current.sort(key=lambda x:x["index"]); results.extend(current)
            passing=[x for x in current if x.get("passed_trigger")]
            if passing:
                winner=min(passing,key=lambda x:x["index"]); break
    payload={{
      "schema":"genesis-autonomous-lang-discovery-result-v1",
      "candidate_budget":a.max_candidates,"workers":a.workers,"batch_size":a.batch_size,
      "evaluated_count":len(results),"winner":winner,"results":results,
      "coverage_pruned_count":sum(bool(x.get("coverage_pruned")) for x in results),
      "relevant_source_file_count":len(RELEVANT_PATHS),
      "evaluator_error_count":sum(bool(x.get("evaluator_error")) for x in results),
      "external_model_calls":0,
    }}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(payload,indent=2,sort_keys=True)+"\\n")
    print(json.dumps({{k:payload[k] for k in ("evaluated_count","winner","coverage_pruned_count","evaluator_error_count","external_model_calls")}},sort_keys=True))
    return 0 if winner else 3
if __name__=="__main__": raise SystemExit(main())
'''


def _record_at(index_path: Path, index: int) -> dict[str, Any]:
    with index_path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == index:
                return json.loads(line)
    raise IndexError(index)


def _apply_candidate(root: Path, rec: Mapping[str, Any]) -> None:
    rel = str(rec["path"])
    target = root / rel
    text = target.read_text(encoding="utf-8")
    if hashlib.sha256(text.encode()).hexdigest() != str(rec.get("expected_sha256") or ""):
        raise RuntimeError("winner baseline hash mismatch")
    if rec.get("kind") == "scalar":
        start, end = int(rec["start"]), int(rec["end"])
        if text[start:end] != str(rec["before"]):
            raise RuntimeError("winner scalar site mismatch")
        mutated = text[:start] + str(rec["after"]) + text[end:]
    else:
        mutated = str(rec["content_utf8"])
    target.write_text(mutated, encoding="utf-8")


def _machinery(
    memory: Mapping[str, Any],
    *,
    parent_digest: str = "",
    planner_front_budget: int = 1200,
    candidate_budget: int = 10_000,
) -> dict[str, Any]:
    payload = {
        "planner_schema": repair_strategist.SCHEMA,
        "retained_memory": dict(memory),
        "memory_digest": str(memory["memory_digest"]),
        "fallback": "er1-j9",
        "planner_front_budget": int(planner_front_budget),
        "candidate_budget": int(candidate_budget),
    }
    digest = digest_of(payload)
    return {
        **payload,
        "machinery_digest": digest,
        "parent_machinery_digest": str(parent_digest),
    }


class LangDefects4JAdapter:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _case_root(self, state: Mapping[str, Any]) -> Path:
        return self.workspace / f"lang-{state['current_case']['case_id']}"

    def _paths(self, state: Mapping[str, Any]) -> dict[str, Path]:
        root = self._case_root(state)
        return {
            "root": root,
            "buggy": root / "buggy",
            "fixed": root / "fixed-sealed",
            "harness": root / "harness",
            "indexes": root / "indexes",
            "evidence": root / "evidence",
            "workers": root / "workers",
        }

    def _cleanup_attempted(self, state: Mapping[str, Any]) -> None:
        for cid in state.get("attempted_case_ids") or []:
            shutil.rmtree(self.workspace / f"lang-{cid}", ignore_errors=True)

    def select_case(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        self._cleanup_attempted(state)
        attempted = {int(x) for x in state["attempted_case_ids"]}
        remaining = [x for x in _active_bug_ids() if x not in attempted]
        if not remaining:
            raise RuntimeError("Defects4J Lang has no unattempted active bugs")
        seed = (
            f"{state['campaign_id']}|{state['generation']}|"
            f"{state['machinery']['machinery_digest']}"
        )
        selector = hashlib.sha256(seed.encode()).hexdigest()
        index = int(selector, 16) % len(remaining)
        bug_id = remaining[index]
        payload = {
            "case_id": str(bug_id),
            "project": "Lang",
            "selector_sha256": selector,
            "selected_index": index,
            "eligible_count": len(remaining),
        }
        return {**payload, "selection_digest": digest_of(payload)}

    def prepare_blind(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        bug_id = int(state["current_case"]["case_id"])
        paths = self._paths(state)
        shutil.rmtree(paths["root"], ignore_errors=True)
        paths["root"].mkdir(parents=True)
        _checkout(bug_id, "b", paths["buggy"])
        _checkout(bug_id, "f", paths["fixed"])

        buggy_ref = _test_reference(paths["buggy"])
        fixed_ref = _test_reference(paths["fixed"])
        if buggy_ref["compile_exit"] != 0 or buggy_ref["failing_tests"] in {None, 0}:
            raise RuntimeError("buggy reference does not reproduce a failing trigger")
        if fixed_ref["compile_exit"] != 0 or fixed_ref["failing_tests"] != 0:
            raise RuntimeError("fixed sealed reference does not pass")

        source_prefix = _d4j_export(paths["buggy"], "dir.src.classes")[-1]
        bin_classes = _d4j_export(paths["buggy"], "dir.bin.classes")[-1]
        bin_tests = _d4j_export(paths["buggy"], "dir.bin.tests")[-1]
        cp_compile = _d4j_export(paths["buggy"], "cp.compile")[-1].split(os.pathsep)
        cp_test = _d4j_export(paths["buggy"], "cp.test")[-1].split(os.pathsep)
        triggers = _triggers(bug_id)
        focus = _focus_paths(bug_id, paths["buggy"], source_prefix)

        paths["indexes"].mkdir()
        index_path = paths["indexes"] / "CANDIDATE_INDEX.jsonl"
        summary = _build_index(
            paths["buggy"],
            source_prefix=source_prefix,
            focus_paths=focus,
            retained_memory=state["machinery"]["retained_memory"],
            output=index_path,
            budget=int(state["machinery"]["candidate_budget"]),
            planner_front_budget=int(state["machinery"]["planner_front_budget"]),
        )
        _write_json(paths["indexes"] / "INDEX_SUMMARY.json", summary)

        paths["harness"].mkdir()
        relevant_path = paths["harness"] / "relevant_paths.json"
        relevant_path.write_text(json.dumps(focus, indent=2) + "\n", encoding="utf-8")
        class_name = "PersistentOracleAuto"
        java_path = paths["harness"] / f"{class_name}.java"
        java_path.write_text(
            _oracle_source(
                class_name=class_name,
                source_prefix=source_prefix,
                bin_classes=bin_classes,
                bin_tests=bin_tests,
                triggers=triggers,
            ),
            encoding="utf-8",
        )
        _run(
            [str(JAVAC), "-cp", str(JUNIT), java_path.name],
            cwd=paths["harness"],
            timeout=120,
        )

        config = {
            "buggy_root": str(paths["buggy"]),
            "workers_root": str(paths["workers"]),
            "harness_root": str(paths["harness"]),
            "java": str(JAVA),
            "oracle_class": class_name,
            "source_prefix": source_prefix,
            "focus_paths": focus,
            "compile_cp": _relative_or_absolute_cp(cp_compile, paths["buggy"]),
            "test_cp": _relative_or_absolute_cp(cp_test, paths["buggy"]),
        }
        config_path = paths["harness"] / "CONFIG.json"
        _write_json(config_path, config)
        evaluator = paths["harness"] / "evaluate_candidates.py"
        evaluator.write_text(_evaluator_source(config_path), encoding="utf-8")
        evaluator.chmod(0o755)

        freeze_payload = {
            "schema": "genesis-autonomous-lang-freeze-v1",
            "case_id": str(bug_id),
            "machinery_digest": state["machinery"]["machinery_digest"],
            "candidate_budget": state["machinery"]["candidate_budget"],
            "index_sha256": summary["index_sha256"],
            "planner_summary": summary["planner_summary"],
            "source_prefix": source_prefix,
            "focus_paths": focus,
            "triggers": triggers,
            "trigger_digest": digest_of(triggers),
            "evaluator_sha256": _sha_file(evaluator),
            "oracle_source_sha256": _sha_file(java_path),
            "adapter_source_sha256": _sha_file(Path(__file__).resolve()),
            "campaign_controller_source_sha256": _sha_file(ROOT / "genesis/external_repair_campaign.py"),
            "buggy_reference": buggy_ref,
            "fixed_reference_pass_digest": digest_of(fixed_ref),
            "human_fix_inspected": False,
            "issue_text_inspected": False,
            "external_model_calls": 0,
        }
        return {**freeze_payload, "freeze_digest": digest_of(freeze_payload)}

    def evaluate_blind(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        output = paths["evidence"] / "BLIND_RESULT.json"
        evaluator = paths["harness"] / "evaluate_candidates.py"
        run = _run(
            [
                str(evaluator),
                "--index",
                str(paths["indexes"] / "CANDIDATE_INDEX.jsonl"),
                "--output",
                str(output),
                "--workers",
                "8",
                "--batch-size",
                "32",
                "--max-candidates",
                str(state["machinery"]["candidate_budget"]),
            ],
            check=False,
            timeout=900,
        )
        if run.returncode not in {0, 3}:
            raise RuntimeError(f"candidate evaluator failed: {run.stdout[-4000:]}")
        result = json.loads(output.read_text(encoding="utf-8"))
        result["scientific_gate_passed"] = result.get("winner") is not None
        result["human_fix_inspected"] = False
        result["issue_text_inspected"] = False
        result["result_digest"] = digest_of({k: v for k, v in result.items() if k != "results"})
        return result

    def validate_success(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        winner = dict(state["blind_result"]["winner"])
        index_path = paths["indexes"] / "CANDIDATE_INDEX.jsonl"
        rec = _record_at(index_path, int(winner["index"]))
        validation_root = paths["root"] / "positive-validation"
        shutil.rmtree(validation_root, ignore_errors=True)
        shutil.copytree(paths["buggy"], validation_root, symlinks=False)
        _apply_candidate(validation_root, rec)
        result = _test_reference(validation_root)
        passed = result["compile_exit"] == 0 and result["failing_tests"] == 0
        payload = {
            "passed": passed,
            "case_id": state["current_case"]["case_id"],
            "winner_index": winner["index"],
            "winner_candidate_digest": winner.get("candidate_digest"),
            "reference": result,
            "human_fix_inspected": False,
            "issue_text_inspected": False,
        }
        return {**payload, "validation_digest": digest_of(payload)}

    def diagnose_and_retain(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        normalized = learning.blind_result_for_gap(
            state["blind_result"],
            family_activation=state["blind_freeze"]["planner_summary"]["family_activation"],
            candidate_budget=int(state["machinery"]["candidate_budget"]),
        )
        retained = learning.diagnose_and_retain(
            state["machinery"]["retained_memory"],
            paths["buggy"],
            normalized,
            target_prefixes=[state["blind_freeze"]["source_prefix"]],
        )
        machinery = _machinery(
            retained["memory"],
            parent_digest=state["machinery"]["machinery_digest"],
            planner_front_budget=int(state["machinery"]["planner_front_budget"]),
            candidate_budget=int(state["machinery"]["candidate_budget"]),
        )
        payload = {
            "solution_visible": False,
            "diagnosis": retained["diagnosis"],
            "learning_digest": retained["learning_digest"],
            "machinery": machinery,
        }
        return payload

    def reveal_solution(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        candidate = learning.solution_candidate_from_roots(
            paths["buggy"],
            paths["fixed"],
            include_prefixes=[state["blind_freeze"]["source_prefix"]],
        )
        if not candidate["mutations"]:
            raise RuntimeError("sealed fixed reference contains no supported source mutation")
        payload = {
            "solution_digest": candidate["candidate_digest"],
            "mutation_count": len(candidate["mutations"]),
            "modified_paths": [m["path"] for m in candidate["mutations"]],
            "fixed_reference_pass_digest": state["blind_freeze"]["fixed_reference_pass_digest"],
        }
        return payload

    def learn_from_solution(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        pre = state["pre_reveal_learning"]
        acquired = learning.acquire_from_revealed_solution(
            state["machinery"]["retained_memory"],
            paths["buggy"],
            paths["fixed"],
            diagnosis=pre["diagnosis"],
            passing_result_digest=state["blind_freeze"]["fixed_reference_pass_digest"],
            target_prefixes=[state["blind_freeze"]["source_prefix"]],
            context_lines=1,
        )
        machinery = _machinery(
            acquired["memory"],
            parent_digest=state["machinery"]["machinery_digest"],
            planner_front_budget=int(state["machinery"]["planner_front_budget"]),
            candidate_budget=int(state["machinery"]["candidate_budget"]),
        )
        payload = {
            "machinery": machinery,
            "learning_digest": acquired["learning_digest"],
            "added_operator_digests": acquired["added_operator_digests"],
        }
        return payload

    def validate_machinery(self, state: Mapping[str, Any]) -> Mapping[str, Any]:
        paths = self._paths(state)
        learned = state["learned_machinery"]
        memory = learned["machinery"]["retained_memory"]
        reuse = learning.retained_variants(
            memory,
            paths["buggy"],
            include_prefixes=[state["blind_freeze"]["source_prefix"]],
            max_candidates=96,
        )
        added = list(learned.get("added_operator_digests") or [])
        passed = bool(added) and int(reuse["candidate_count"]) > 0
        payload = {
            "passed": passed,
            "added_operator_count": len(added),
            "replay_candidate_count": reuse["candidate_count"],
            "memory_digest": memory["memory_digest"],
            "external_model_calls": 0,
        }
        return {**payload, "validation_digest": digest_of(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument("--stop-after-successes", type=int, default=0)
    parser.add_argument("--max-transitions", type=int, default=1000)
    parser.add_argument("--seed-attempted", default="")
    args = parser.parse_args()

    store = campaign.CampaignStore(args.state)
    initial = None
    if not store.exists():
        memory = self_extension.empty_memory()
        machinery = _machinery(memory)
        attempted = tuple(x.strip() for x in args.seed_attempted.split(",") if x.strip())
        initial = campaign.create_state(
            campaign_id="defects4j-lang-autonomous-er",
            machinery=machinery,
            max_cases=args.max_cases,
            stop_after_successes=args.stop_after_successes,
            attempted_case_ids=attempted,
        )

    adapter = LangDefects4JAdapter(args.workspace)
    final = campaign.run(
        store,
        adapter,
        initial_state=initial,
        max_transitions=args.max_transitions,
    )
    print(
        json.dumps(
            {
                "phase": final["phase"],
                "generation": final["generation"],
                "attempted_case_ids": final["attempted_case_ids"],
                "success_count": final["success_count"],
                "machinery_digest": final["machinery"]["machinery_digest"],
                "memory_generation": final["machinery"]["retained_memory"]["generation"],
                "state_digest": final["state_digest"],
            },
            sort_keys=True,
        )
    )
    return 0 if final["phase"] == "complete" else 2 if final["phase"] == "halted" else 0


if __name__ == "__main__":
    raise SystemExit(main())
