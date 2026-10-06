from __future__ import annotations

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

SOURCE = Path("/home/anthony/experiments/a6v2-c001").resolve()
ROOT = Path("/home/anthony/mira-genesis-autonomy").resolve()
HERE = ROOT / "experiment" / "autonomy_a6"
MEMORY = HERE / "MEMORY_000.json"
EVALUATOR = HERE / "task_001_eval.py"
RESULT = HERE / "task_001_autonomous_result.json"
TARGET = "canoe_commercial/weather_mapping.py"
PYTHON = "/home/anthony/mira-genesis-oe1/.venv/bin/python"
BUDGET = 256


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_repo(source: Path, dest: Path) -> None:
    shutil.copytree(
        source,
        dest,
        ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache", ".venv", "venv"),
        symlinks=False,
    )


def apply_candidate(workspace: Path, candidate: dict[str, Any]) -> None:
    muts = candidate["mutations"]
    if len(muts) != 1:
        raise RuntimeError("A6 task 001 requires single-site candidate records")
    m = muts[0]
    target = workspace / m["path"]
    if sha256_file(target) != m["expected_sha256"]:
        raise RuntimeError("candidate base hash mismatch")
    target.write_text(m["content_utf8"], encoding="utf-8")


def evaluate(workspace: Path) -> dict[str, Any]:
    started = time.monotonic()
    proc = subprocess.run(
        [PYTHON, str(EVALUATOR), str(workspace)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    parsed = None
    try:
        parsed = json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
    except Exception:
        pass
    return {
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "parsed": parsed,
    }


def build_candidates(memory: dict[str, Any]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    ordered.extend(
        patch_templates.generate(
            SOURCE, memory.get("learned_line_templates", []), max_candidates=10000
        )["candidates"]
    )
    ordered.extend(
        exemplar_strategy.generate_from_acquired(
            SOURCE, memory.get("acquired_strategies", []), max_candidates=10000
        )["candidates"]
    )
    ordered.extend(exemplar_strategy.generate(SOURCE, max_candidates=10000)["candidates"])

    scalar = scalar_mutations.generate(
        SOURCE, include_prefixes=[TARGET], max_candidates=10000
    )["candidates"]
    counts = memory.get("operator_success_counts", {})
    scalar = sorted(
        enumerate(scalar),
        key=lambda pair: (
            -int(counts.get(pair[1]["provenance"]["operator"], 0)),
            pair[0],
        ),
    )
    ordered.extend(candidate for _, candidate in scalar)

    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in ordered:
        mutation = candidate["mutations"][0]
        fingerprint = digest_of(
            {
                "path": mutation["path"],
                "content_utf8": mutation["content_utf8"],
            }
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(candidate)
    return unique


def main() -> int:
    memory = json.loads(MEMORY.read_text(encoding="utf-8"))
    baseline = evaluate(SOURCE)
    if baseline["exit_code"] == 0:
        raise SystemExit("baseline unexpectedly passes")

    candidates = build_candidates(memory)
    records: list[dict[str, Any]] = []
    winner = None
    winner_candidate = None

    with tempfile.TemporaryDirectory(prefix="genesis-a6-task001-") as temp:
        root = Path(temp)
        for rank, candidate in enumerate(candidates[:BUDGET], start=1):
            workspace = root / f"c-{rank:03d}"
            copy_repo(SOURCE, workspace)
            apply_candidate(workspace, candidate)
            outcome = evaluate(workspace)
            rec = {
                "rank": rank,
                "id": candidate["id"],
                "label": candidate["label"],
                "operator": candidate["provenance"].get("operator"),
                "generator": candidate["provenance"].get("generator"),
                "candidate_digest": candidate["candidate_digest"],
                "passed": outcome["exit_code"] == 0,
                "evaluation": outcome,
            }
            records.append(rec)
            shutil.rmtree(workspace)
            if rec["passed"]:
                winner = rec
                winner_candidate = candidate
                break

    replay = None
    if winner_candidate is not None:
        with tempfile.TemporaryDirectory(prefix="genesis-a6-task001-replay-") as temp:
            workspace = Path(temp) / "workspace"
            copy_repo(SOURCE, workspace)
            apply_candidate(workspace, winner_candidate)
            replay = evaluate(workspace)

    payload = {
        "schema": "mira-genesis-a6-task001-autonomous-result-v1",
        "baseline": baseline,
        "candidate_pool_size": len(candidates),
        "candidate_budget": BUDGET,
        "charged_candidate_executions": len(records),
        "records": records,
        "winner": winner,
        "winner_replay": replay,
        "autonomous_passed": bool(
            winner is not None and replay is not None and replay["exit_code"] == 0
        ),
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
    }
    result = {**payload, "report_digest": digest_of(payload)}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "candidate_pool_size": len(candidates),
        "charged": len(records),
        "winner": winner,
        "autonomous_passed": result["autonomous_passed"],
        "report_digest": result["report_digest"],
    }, indent=2, sort_keys=True))
    return 0 if result["autonomous_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
