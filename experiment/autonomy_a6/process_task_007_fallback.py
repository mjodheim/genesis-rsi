from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from genesis import patch_templates
from genesis.trust_root import digest_of

ROOT = Path("/home/anthony/mira-genesis-autonomy")
HERE = ROOT / "experiment/autonomy_a6"
SOURCE = Path("/home/anthony/experiments/a6v2-c010")
RAW = HERE / "task_007_fallback_raw.json"
RESULT = HERE / "task_007_fallback_result.json"
EVALUATOR = HERE / "task_007_eval_v2.py"
PYTHON = "/home/anthony/mira-genesis-oe1/.venv/bin/python"
AUTO = HERE / "task_007_autonomous_result_v2.json"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def copy_repo(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", ".venv", "venv",
            "node_modules", "target", "bin", "obj", "dist", "build"
        ),
        symlinks=False,
    )


def run_eval(workspace: Path) -> dict:
    started = time.monotonic()
    proc = subprocess.run(
        [PYTHON, str(EVALUATOR), str(workspace)],
        cwd=workspace,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    text = proc.stdout.decode("utf-8", errors="replace")
    parsed = None
    if text.strip():
        try:
            parsed = json.loads(text.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass
    return {
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": text,
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "parsed": parsed,
    }


raw = json.loads(RAW.read_text(encoding="utf-8"))
proposal = raw.get("structured_output")
if not isinstance(proposal, dict):
    raise SystemExit("fallback raw result has no structured_output")

before_after = []
applied = []

with tempfile.TemporaryDirectory(prefix="genesis-a6-task007-fallback-") as temp:
    workspace = Path(temp) / "workspace"
    copy_repo(SOURCE, workspace)

    for edit in proposal.get("edits", []):
        supplied = Path(str(edit["path"]))
        if supplied.is_absolute():
            try:
                rel = supplied.resolve().relative_to(SOURCE.resolve()).as_posix()
            except ValueError as exc:
                raise SystemExit(f"unsafe fallback absolute path: {supplied}") from exc
        else:
            rel = supplied.as_posix()
        path = (workspace / rel).resolve()
        if not str(path).startswith(str(workspace.resolve()) + os.sep):
            raise SystemExit(f"unsafe fallback path: {rel}")
        if not path.is_file():
            raise SystemExit(f"fallback path missing: {rel}")

        old = str(edit["old"])
        new = str(edit["new"])
        before = path.read_text(encoding="utf-8")
        if before.count(old) != 1:
            raise SystemExit(f"old text occurrence count is not one: {rel}")
        after = before.replace(old, new, 1)
        path.write_text(after, encoding="utf-8")
        before_after.append((rel, before, after))
        applied.append({
            "path": rel,
            "supplied_path": str(supplied),
            "old_sha256": sha256_text(before),
            "new_sha256": sha256_text(after),
        })

    evaluation = run_eval(workspace)

patch_payload = {"proposal": proposal, "applied": applied}
patch_digest = digest_of(patch_payload)
learned = []
if evaluation["exit_code"] == 0:
    for _rel, before, after in before_after:
        learned.extend(
            patch_templates.learn_from_texts(
                before,
                after,
                source_digest=patch_digest,
            )
        )

seen = set()
learned_unique = []
for item in learned:
    td = item["template_digest"]
    if td in seen:
        continue
    seen.add(td)
    learned_unique.append(item)

auto = json.loads(AUTO.read_text(encoding="utf-8"))
payload = {
    "schema": "mira-genesis-a6-task007-fallback-result-v1",
    "autonomous_result_digest": auto["report_digest"],
    "model": "claude-sonnet-5-5",
    "model_calls": 1,
    "cost_usd": raw.get("total_cost_usd"),
    "proposal": proposal,
    "applied": applied,
    "patch_digest": patch_digest,
    "evaluation": evaluation,
    "fallback_passed": evaluation["exit_code"] == 0,
    "learned_template_count": len(learned_unique),
    "learned_templates": learned_unique,
    "learned_template_digests": [x["template_digest"] for x in learned_unique],
    "manual_candidate_repair": False,
    "retry_count": 0,
}
result = {**payload, "report_digest": digest_of(payload)}
RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps({
    "fallback_passed": result["fallback_passed"],
    "model_calls": 1,
    "cost_usd": result["cost_usd"],
    "learned_template_count": result["learned_template_count"],
    "report_digest": result["report_digest"],
}, indent=2, sort_keys=True))
raise SystemExit(0 if result["fallback_passed"] else 1)
