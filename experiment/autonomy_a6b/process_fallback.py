from __future__ import annotations

import argparse
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


def run_eval(argv_template: list[str], workspace: Path, timeout: int) -> dict:
    argv = [part.replace("{workspace}", str(workspace)) for part in argv_template]
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=workspace,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    parsed = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            pass
    return {
        "argv": argv,
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": stdout,
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "parsed": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    args = parser.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    source = Path(spec["source_root"]).resolve()
    raw_path = Path(spec["raw_result"]).resolve()
    result_path = Path(spec["result_path"]).resolve()
    auto = json.loads(Path(spec["autonomous_result"]).read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    proposal = raw.get("structured_output")
    if not isinstance(proposal, dict):
        raise SystemExit("fallback raw result has no structured_output")

    before_after: list[tuple[str, str, str]] = []
    applied = []

    with tempfile.TemporaryDirectory(prefix="genesis-a6b-fallback-") as temp:
        workspace = Path(temp) / "workspace"
        copy_repo(source, workspace)

        for edit in proposal.get("edits", []):
            supplied = Path(str(edit["path"]))
            if supplied.is_absolute():
                try:
                    rel = supplied.resolve().relative_to(source).as_posix()
                except ValueError as exc:
                    raise SystemExit(f"unsafe fallback absolute path: {supplied}") from exc
            else:
                rel = supplied.as_posix()

            target = (workspace / rel).resolve()
            if not str(target).startswith(str(workspace.resolve()) + os.sep):
                raise SystemExit(f"unsafe fallback path: {rel}")
            if not target.is_file():
                raise SystemExit(f"fallback path missing: {rel}")

            old = str(edit["old"])
            new = str(edit["new"])
            before = target.read_text(encoding="utf-8")
            if not old or before.count(old) != 1:
                raise SystemExit(f"old text occurrence count is not one: {rel}")
            after = before.replace(old, new, 1)
            target.write_text(after, encoding="utf-8")
            before_after.append((rel, before, after))
            applied.append({
                "path": rel,
                "old_sha256": sha256_text(before),
                "new_sha256": sha256_text(after),
            })

        evaluation = run_eval(
            list(spec["evaluator_argv"]),
            workspace,
            int(spec.get("evaluator_timeout_seconds", 30)),
        )

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
    for template in learned:
        td = template["template_digest"]
        if td in seen:
            continue
        seen.add(td)
        learned_unique.append(template)

    payload = {
        "schema": "mira-genesis-a6b-fallback-result-v1",
        "task_id": spec["task_id"],
        "carrier": spec["carrier"],
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
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "task_id": result["task_id"],
        "fallback_passed": result["fallback_passed"],
        "cost_usd": result["cost_usd"],
        "learned_template_count": result["learned_template_count"],
        "report_digest": result["report_digest"],
    }, indent=2, sort_keys=True))
    return 0 if result["fallback_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
