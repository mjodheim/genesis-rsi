from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from genesis import exemplar_strategy, patch_templates, scalar_mutations
from genesis.trust_root import digest_of


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def copy_repo(source: Path, dest: Path) -> None:
    shutil.copytree(
        source,
        dest,
        ignore=shutil.ignore_patterns(
            ".git", "__pycache__", ".pytest_cache", ".venv", "venv",
            "node_modules", "target", "bin", "obj", "dist", "build"
        ),
        symlinks=False,
    )


def apply_candidate(workspace: Path, candidate: dict[str, Any]) -> None:
    mutations = candidate["mutations"]
    if len(mutations) != 1:
        raise RuntimeError("campaign autonomous candidates must contain exactly one mutation")
    mutation = mutations[0]
    target = workspace / mutation["path"]
    if sha256_file(target) != mutation["expected_sha256"]:
        raise RuntimeError(f"candidate base hash mismatch: {mutation['path']}")
    target.write_text(mutation["content_utf8"], encoding="utf-8")


def run_evaluator(argv_template: list[str], workspace: Path, timeout: int) -> dict[str, Any]:
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
    parsed = None
    text = proc.stdout.decode("utf-8", errors="replace")
    if text.strip():
        try:
            parsed = json.loads(text.strip().splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "argv": argv,
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": text,
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "parsed": parsed,
    }


def build_candidates(source: Path, memory: dict[str, Any], prefixes: list[str]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []

    ordered.extend(
        patch_templates.generate(
            source,
            memory.get("learned_line_templates", []),
            max_candidates=10000,
        )["candidates"]
    )
    ordered.extend(
        exemplar_strategy.generate_from_acquired(
            source,
            memory.get("acquired_strategies", []),
            max_candidates=10000,
        )["candidates"]
    )
    ordered.extend(exemplar_strategy.generate(source, max_candidates=10000)["candidates"])

    scalar = scalar_mutations.generate(
        source,
        include_prefixes=prefixes,
        max_candidates=10000,
    )["candidates"]
    counts = memory.get("operator_success_counts", {})
    scalar = [
        c for _, c in sorted(
            enumerate(scalar),
            key=lambda pair: (
                -int(counts.get(pair[1]["provenance"]["operator"], 0)),
                pair[0],
            ),
        )
    ]
    ordered.extend(scalar)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in ordered:
        mutation = candidate["mutations"][0]
        fingerprint = digest_of(
            {"path": mutation["path"], "content_utf8": mutation["content_utf8"]}
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(candidate)
    return unique


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    args = parser.parse_args()

    spec_path = Path(args.spec).resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    source = Path(spec["source_root"]).resolve()
    memory = json.loads(Path(spec["memory_path"]).read_text(encoding="utf-8"))
    result_path = Path(spec["result_path"]).resolve()
    budget = int(spec.get("candidate_budget", 256))
    timeout = int(spec.get("evaluator_timeout_seconds", 30))
    prefixes = list(spec.get("target_prefixes") or [])

    baseline = run_evaluator(spec["evaluator_argv"], source, timeout)
    if baseline["exit_code"] == 0:
        raise SystemExit("baseline unexpectedly passes")

    candidates = build_candidates(source, memory, prefixes)
    records: list[dict[str, Any]] = []
    winner = None
    winner_candidate = None

    with tempfile.TemporaryDirectory(prefix="genesis-a6-auto-") as temp:
        root = Path(temp)
        for rank, candidate in enumerate(candidates[:budget], start=1):
            workspace = root / f"candidate-{rank:03d}"
            copy_repo(source, workspace)
            apply_candidate(workspace, candidate)
            outcome = run_evaluator(spec["evaluator_argv"], workspace, timeout)
            record = {
                "rank": rank,
                "id": candidate["id"],
                "label": candidate["label"],
                "operator": candidate["provenance"].get("operator"),
                "generator": candidate["provenance"].get("generator"),
                "candidate_digest": candidate["candidate_digest"],
                "passed": outcome["exit_code"] == 0,
                "evaluation": outcome,
            }
            records.append(record)
            shutil.rmtree(workspace)
            if record["passed"]:
                winner = record
                winner_candidate = candidate
                break

    replay = None
    if winner_candidate is not None:
        with tempfile.TemporaryDirectory(prefix="genesis-a6-auto-replay-") as temp:
            workspace = Path(temp) / "workspace"
            copy_repo(source, workspace)
            apply_candidate(workspace, winner_candidate)
            replay = run_evaluator(spec["evaluator_argv"], workspace, timeout)

    payload = {
        "schema": "mira-genesis-a6-autonomous-task-result-v1",
        "task_id": spec["task_id"],
        "carrier": spec["carrier"],
        "baseline": baseline,
        "candidate_pool_size": len(candidates),
        "candidate_budget": budget,
        "charged_candidate_executions": len(records),
        "records": records,
        "winner": winner,
        "winner_replay": replay,
        "autonomous_passed": bool(
            winner is not None and replay is not None and replay["exit_code"] == 0
        ),
        "memory_generation": memory.get("generation"),
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
    }
    result = {**payload, "report_digest": digest_of(payload)}
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "task_id": spec["task_id"],
        "candidate_pool_size": len(candidates),
        "charged": len(records),
        "winner": winner,
        "autonomous_passed": result["autonomous_passed"],
        "report_digest": result["report_digest"],
    }, indent=2, sort_keys=True))
    return 0 if result["autonomous_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
