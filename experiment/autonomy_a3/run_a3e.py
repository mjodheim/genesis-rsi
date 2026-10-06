from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any

from genesis.scalar_mutations import generate
from genesis.strategy_memory import rank_candidates
from genesis.trust_root import digest_of

SOURCE = Path("/home/anthony/experiments/autonomy-a3-mm-truncate").resolve()
HERE = Path(__file__).resolve().parent
MEMORY_PATH = HERE / "RETAINED_STRATEGY.json"
RESULT_PATH = HERE / "RESULT_E.json"
PYTHON = "/home/anthony/mira-genesis-oe1/.venv/bin/python"
BUDGET = 16


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_repo(source: Path, dest: Path) -> None:
    ignored = {".git", ".pytest_cache", "__pycache__", ".venv", "venv"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(source, dest, ignore=ignore, symlinks=False)


def run_tests(workspace: Path) -> dict[str, Any]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP"}
    }
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        }
    )
    started = time.monotonic()
    proc = subprocess.run(
        [PYTHON, "-m", "pytest", "-q"],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    return {
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "stdout_sha256": hashlib.sha256(proc.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr).hexdigest(),
    }


def apply_candidate(workspace: Path, candidate: dict[str, Any]) -> None:
    mutations = candidate["mutations"]
    if len(mutations) != 1:
        raise RuntimeError("A3E expects one mutation per candidate")
    mutation = mutations[0]
    target = workspace / mutation["path"]
    if sha256_file(target) != mutation["expected_sha256"]:
        raise RuntimeError(f"candidate base mismatch: {mutation['path']}")
    target.write_text(mutation["content_utf8"], encoding="utf-8")


def evaluate_order(
    source: Path,
    candidates: list[dict[str, Any]],
    ordered_indices: list[int],
    arm: str,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    first_pass: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix=f"genesis-a3e-{arm}-") as temp:
        root = Path(temp)
        for rank, base_index in enumerate(ordered_indices[:BUDGET], start=1):
            candidate = candidates[base_index]
            workspace = root / f"candidate-{rank:03d}"
            copy_repo(source, workspace)
            apply_candidate(workspace, candidate)
            outcome = run_tests(workspace)
            record = {
                "rank": rank,
                "base_index": base_index,
                "id": candidate["id"],
                "label": candidate["label"],
                "candidate_digest": candidate["candidate_digest"],
                "operator": candidate["provenance"]["operator"],
                "passed": outcome["exit_code"] == 0,
                "tests": outcome,
            }
            records.append(record)
            shutil.rmtree(workspace)
            if record["passed"]:
                first_pass = record
                break

    return {
        "arm": arm,
        "budget": BUDGET,
        "charged_candidate_executions": len(records),
        "first_pass": first_pass,
        "records": records,
    }


def replay(source: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="genesis-a3e-replay-") as temp:
        workspace = Path(temp) / "workspace"
        copy_repo(source, workspace)
        apply_candidate(workspace, candidate)
        return run_tests(workspace)


def main() -> int:
    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="genesis-a3e-baseline-") as temp:
        workspace = Path(temp) / "workspace"
        copy_repo(SOURCE, workspace)
        baseline = run_tests(workspace)

    if baseline["exit_code"] == 0:
        raise SystemExit("baseline unexpectedly passes")

    generated = generate(SOURCE, max_candidates=10000)
    candidates = list(generated["candidates"])
    base_order = list(range(len(candidates)))
    ranked = rank_candidates(candidates, memory)
    memory_order = [int(item["base_index"]) for item in ranked["records"]]

    control = evaluate_order(SOURCE, candidates, base_order, "control_no_memory")
    treatment = evaluate_order(SOURCE, candidates, memory_order, "retained_memory")

    replay_result = None
    same_candidate_control_rank = None
    if treatment["first_pass"] is not None:
        winner_id = treatment["first_pass"]["id"]
        winner_index = next(i for i, c in enumerate(candidates) if c["id"] == winner_id)
        same_candidate_control_rank = winner_index + 1
        replay_result = replay(SOURCE, candidates[winner_index])

    control_first_rank = (
        None if control["first_pass"] is None else int(control["first_pass"]["rank"])
    )
    treatment_first_rank = (
        None if treatment["first_pass"] is None else int(treatment["first_pass"]["rank"])
    )

    passed = bool(
        treatment_first_rank is not None
        and treatment_first_rank <= BUDGET
        and replay_result is not None
        and replay_result["exit_code"] == 0
        and same_candidate_control_rank is not None
        and treatment_first_rank < same_candidate_control_rank
        and (
            control_first_rank is None
            or treatment_first_rank < control_first_rank
        )
    )

    payload: dict[str, Any] = {
        "schema": "mira-genesis-autonomy-a3e-result-v1",
        "carrier_commit": "53bdc652b0e8c5879158b9cc3927e9bddbba3a00",
        "issue_number": 1,
        "baseline": baseline,
        "candidate_generation": {
            "schema": generated["schema"],
            "candidate_count": generated["candidate_count"],
            "truncated": generated["truncated"],
            "external_model_calls": generated["external_model_calls"],
        },
        "memory_digest": memory["memory_digest"],
        "memory_ranking_digest": ranked["ranking_digest"],
        "control": control,
        "retained_memory": treatment,
        "same_treatment_winner_control_rank": same_candidate_control_rank,
        "winner_replay": replay_result,
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
        "passed": passed,
        "claim": "A3_CAUSAL_RETAINED_STRATEGY_REUSE",
    }
    result = {**payload, "report_digest": digest_of(payload)}
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "baseline_exit": baseline["exit_code"],
                "candidate_count": generated["candidate_count"],
                "control_first_pass_rank": control_first_rank,
                "memory_first_pass_rank": treatment_first_rank,
                "same_winner_control_rank": same_candidate_control_rank,
                "winner": None if treatment["first_pass"] is None else treatment["first_pass"]["label"],
                "winner_replay_exit": None if replay_result is None else replay_result["exit_code"],
                "passed": passed,
                "report_digest": result["report_digest"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
