from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from genesis.scalar_mutations import generate
from genesis.trust_root import digest_of

ROOT = Path(__file__).resolve().parents[2]
OBJECTIVE = Path(__file__).with_name("OBJECTIVE.mjs")
RESULT = Path(__file__).with_name("RESULT.json")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_repo(source: Path, dest: Path) -> None:
    ignored = {".git", "node_modules", "dist", "build", "coverage", "__pycache__"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(source, dest, ignore=ignore, symlinks=False)


def run_objective(workspace: Path) -> dict:
    started = time.monotonic()
    proc = subprocess.run(
        ["node", str(OBJECTIVE), str(workspace)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    return {
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "stdout_sha256": hashlib.sha256(proc.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr).hexdigest(),
    }


def apply_candidate(workspace: Path, candidate: dict) -> None:
    mutations = candidate["mutations"]
    if len(mutations) != 1:
        raise RuntimeError("A2 runner expects one mutation per candidate")
    mutation = mutations[0]
    target = workspace / mutation["path"]
    if sha256_file(target) != mutation["expected_sha256"]:
        raise RuntimeError(f"candidate base mismatch: {mutation['path']}")
    target.write_text(mutation["content_utf8"], encoding="utf-8")


def main() -> int:
    source = Path("/home/anthony/experiments/autonomy-a2-os-club").resolve()
    baseline = run_objective(source)
    if baseline["exit_code"] == 0:
        raise SystemExit("baseline unexpectedly passes")

    generated = generate(source, include_prefixes=["frontend/src"], max_candidates=10000)
    candidates = generated["candidates"]
    records: list[dict] = []
    winners: list[dict] = []

    with tempfile.TemporaryDirectory(prefix="genesis-a2-search-") as temp:
        root = Path(temp)
        for index, candidate in enumerate(candidates):
            workspace = root / f"candidate-{index:04d}"
            copy_repo(source, workspace)
            apply_candidate(workspace, candidate)
            outcome = run_objective(workspace)
            record = {
                "index": index,
                "id": candidate["id"],
                "label": candidate["label"],
                "candidate_digest": candidate["candidate_digest"],
                "mutation_path": candidate["mutations"][0]["path"],
                "objective": outcome,
                "passed": outcome["exit_code"] == 0,
            }
            records.append(record)
            if record["passed"]:
                winners.append(record)
            shutil.rmtree(workspace)

    replay = None
    if len(winners) == 1:
        winner_record = winners[0]
        winner = candidates[winner_record["index"]]
        with tempfile.TemporaryDirectory(prefix="genesis-a2-replay-") as temp:
            workspace = Path(temp) / "workspace"
            copy_repo(source, workspace)
            apply_candidate(workspace, winner)
            replay = run_objective(workspace)

    payload = {
        "schema": "mira-genesis-autonomy-a2-result-v1",
        "carrier_commit": "a4a8a4173aaf4afd77da5f748b5be5a25353faab",
        "issue_number": 5,
        "objective_sha256": sha256_file(OBJECTIVE),
        "baseline": baseline,
        "candidate_generation": {
            "schema": generated["schema"],
            "candidate_count": generated["candidate_count"],
            "truncated": generated["truncated"],
            "external_model_calls": generated["external_model_calls"],
        },
        "charged_candidate_executions": len(records),
        "passing_candidate_count": len(winners),
        "passing_candidates": winners,
        "winner_replay": replay,
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
        "passed": (
            baseline["exit_code"] != 0
            and len(winners) == 1
            and replay is not None
            and replay["exit_code"] == 0
        ),
        "claim": "A2_ZERO_LLM_REAL_EXTERNAL_BUG_FAMILY",
    }
    result = {**payload, "report_digest": digest_of(payload)}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "baseline_exit": baseline["exit_code"],
        "candidate_count": len(records),
        "passing_candidate_count": len(winners),
        "winner": winners[0] if len(winners) == 1 else None,
        "replay_exit": None if replay is None else replay["exit_code"],
        "passed": result["passed"],
        "report_digest": result["report_digest"],
    }, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
