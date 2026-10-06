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

from genesis.exemplar_strategy import acquire_strategy, generate as generate_exemplars
from genesis.scalar_mutations import generate as generate_scalars
from genesis.trust_root import digest_of

SOURCE = Path("/home/anthony/experiments/autonomy-a3-tictactoe").resolve()
HERE = Path(__file__).resolve().parent
DIRECT_EVALUATOR = HERE / "DIRECT_EVALUATOR.mjs"
RESULT_PATH = HERE / "RESULT_V2.json"
STRATEGY_PATH = HERE / "ACQUIRED_STRATEGY.json"
CANDIDATE_LIMIT = 256


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def copy_repo(source: Path, dest: Path) -> None:
    ignored = {".git", "node_modules", "build", "coverage"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(source, dest, ignore=ignore, symlinks=False)


def run_evaluator(workspace: Path) -> dict[str, Any]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key in {"PATH", "HOME", "TMPDIR", "TEMP", "TMP"}
    }
    started = time.monotonic()
    proc = subprocess.run(
        ["node", str(DIRECT_EVALUATOR), str(workspace / "src" / "GridState.js")],
        cwd=workspace,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    parsed = None
    if stdout.strip():
        try:
            parsed = json.loads(stdout.strip().splitlines()[-1])
        except json.JSONDecodeError:
            parsed = None
    return {
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": stdout,
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "stdout_sha256": hashlib.sha256(proc.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr).hexdigest(),
        "parsed": parsed,
    }


def apply_candidate(workspace: Path, candidate: dict[str, Any]) -> None:
    mutations = candidate["mutations"]
    if len(mutations) != 1:
        raise RuntimeError("A4 expects one mutation per candidate")
    mutation = mutations[0]
    target = workspace / mutation["path"]
    if sha256_file(target) != mutation["expected_sha256"]:
        raise RuntimeError(f"candidate base mismatch: {mutation['path']}")
    target.write_text(mutation["content_utf8"], encoding="utf-8")


def scalar_can_express_required_edit() -> dict[str, Any]:
    generated = generate_scalars(SOURCE, max_candidates=10000)
    matching: list[str] = []
    for candidate in generated["candidates"]:
        for mutation in candidate["mutations"]:
            if mutation["path"] != "src/GridState.js":
                continue
            if "currentArray[xPos - 1]" in mutation["content_utf8"]:
                matching.append(candidate["id"])
    return {
        "candidate_count": generated["candidate_count"],
        "matching_required_edit_ids": matching,
        "can_express_required_edit": bool(matching),
        "external_model_calls": generated["external_model_calls"],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="genesis-a4v2-baseline-") as temp:
        workspace = Path(temp) / "workspace"
        copy_repo(SOURCE, workspace)
        baseline = run_evaluator(workspace)

    baseline_parsed = baseline.get("parsed") or {}
    if baseline["exit_code"] == 0 or baseline_parsed.get("objective_ok") is not False:
        raise SystemExit("A4 V2 baseline did not reproduce the primary objective failure")

    old_ablation = scalar_can_express_required_edit()
    generated = generate_exemplars(SOURCE, max_candidates=CANDIDATE_LIMIT)
    candidates = list(generated["candidates"])

    records: list[dict[str, Any]] = []
    winner: dict[str, Any] | None = None
    winner_candidate: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="genesis-a4v2-search-") as temp:
        root = Path(temp)
        for rank, candidate in enumerate(candidates, start=1):
            workspace = root / f"candidate-{rank:03d}"
            copy_repo(SOURCE, workspace)
            apply_candidate(workspace, candidate)
            outcome = run_evaluator(workspace)
            parsed = outcome.get("parsed") or {}
            passed = bool(
                outcome["exit_code"] == 0
                and parsed.get("objective_ok") is True
                and parsed.get("regression_ok") is True
            )
            record = {
                "rank": rank,
                "id": candidate["id"],
                "label": candidate["label"],
                "candidate_digest": candidate["candidate_digest"],
                "provenance": candidate["provenance"],
                "passed": passed,
                "evaluation": outcome,
            }
            records.append(record)
            shutil.rmtree(workspace)
            if passed:
                winner = record
                winner_candidate = candidate
                break

    acquired = None
    replay = None
    if winner is not None and winner_candidate is not None:
        acquisition_evidence = {
            "candidate_id": winner["id"],
            "candidate_digest": winner["candidate_digest"],
            "evaluation_stdout_sha256": winner["evaluation"]["stdout_sha256"],
            "evaluation_stderr_sha256": winner["evaluation"]["stderr_sha256"],
            "carrier_commit": "27a43cee5087decc8bab2d349a223ce9b70c2d20",
        }
        evidence_digest = digest_of(acquisition_evidence)
        acquired = acquire_strategy(winner_candidate, result_digest=evidence_digest)
        STRATEGY_PATH.write_text(
            json.dumps(acquired, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        with tempfile.TemporaryDirectory(prefix="genesis-a4v2-replay-") as temp:
            workspace = Path(temp) / "workspace"
            copy_repo(SOURCE, workspace)
            apply_candidate(workspace, winner_candidate)
            replay = run_evaluator(workspace)

    replay_parsed = {} if replay is None else (replay.get("parsed") or {})
    passed = bool(
        baseline["exit_code"] != 0
        and baseline_parsed.get("objective_ok") is False
        and not old_ablation["can_express_required_edit"]
        and winner is not None
        and acquired is not None
        and acquired["host_issue_specific_recipe"] is False
        and replay is not None
        and replay["exit_code"] == 0
        and replay_parsed.get("objective_ok") is True
        and replay_parsed.get("regression_ok") is True
    )

    payload: dict[str, Any] = {
        "schema": "mira-genesis-autonomy-a4-result-v2",
        "carrier_commit": "27a43cee5087decc8bab2d349a223ce9b70c2d20",
        "seed": "A3A primary one-based-index expressivity failure",
        "v1_apparatus_abort": "experiment/autonomy_a4/ABORTED_RUN_1.json",
        "baseline": baseline,
        "old_scalar_grammar_ablation": old_ablation,
        "exemplar_generation": {
            "schema": generated["schema"],
            "target_site_count": generated["target_site_count"],
            "candidate_count": generated["candidate_count"],
            "truncated": generated["truncated"],
            "external_model_calls": generated["external_model_calls"],
        },
        "charged_candidate_executions": len(records),
        "records": records,
        "winner": winner,
        "acquired_strategy": acquired,
        "winner_replay": replay,
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
        "passed": passed,
        "claim": "A4_REPOSITORY_EVIDENCE_STRATEGY_ACQUISITION",
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
                "baseline_objective_ok": baseline_parsed.get("objective_ok"),
                "old_scalar_can_express_required_edit": old_ablation["can_express_required_edit"],
                "exemplar_candidate_count": generated["candidate_count"],
                "charged_candidate_executions": len(records),
                "winner": None if winner is None else winner["label"],
                "acquired_strategy": None if acquired is None else acquired["template_after"],
                "replay_exit": None if replay is None else replay["exit_code"],
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
