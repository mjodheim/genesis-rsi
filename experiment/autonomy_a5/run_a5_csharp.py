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

SOURCE = Path("/home/anthony/experiments/autonomy-a5-roslynmcp").resolve()
HERE = Path(__file__).resolve().parent
OBJECTIVE = HERE / "DEPTH_OBJECTIVE.cs"
RESULT = HERE / "RESULT_CSHARP.json"
MEMORY_PATH = Path("/home/anthony/mira-genesis-autonomy/experiment/autonomy_a3/RETAINED_STRATEGY.json")
TARGET_REL = "src/RoslynMcp.Core/Query/Utilities/MetricsCalculator.cs"
TEST_REL = "tests/RoslynMcp.Core.Tests/Query/Utilities/GenesisA5DepthOfInheritanceTests.cs"
TEST_PROJECT = "tests/RoslynMcp.Core.Tests/RoslynMcp.Core.Tests.csproj"
TEST_FILTER = "FullyQualifiedName~GenesisA5DepthOfInheritanceTests"
BUDGET = 256


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run_cmd(argv: list[str], *, cwd: Path, timeout: int, network_offline: bool) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(
        {
            "DOTNET_NOLOGO": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            "NUGET_XMLDOC_MODE": "skip",
        }
    )
    if network_offline:
        env["NUGET_CERT_REVOCATION_MODE"] = "offline"
    started = time.monotonic()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return {
        "argv": argv,
        "exit_code": int(proc.returncode),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
        "stdout": proc.stdout.decode("utf-8", errors="replace"),
        "stderr": proc.stderr.decode("utf-8", errors="replace"),
        "stdout_sha256": hashlib.sha256(proc.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr).hexdigest(),
    }


def copy_repo(source: Path, dest: Path) -> None:
    ignored = {".git", "bin", "obj"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored}

    shutil.copytree(source, dest, ignore=ignore, symlinks=False)
    test_target = dest / TEST_REL
    test_target.parent.mkdir(parents=True, exist_ok=True)
    test_target.write_text(OBJECTIVE.read_text(encoding="utf-8"), encoding="utf-8")


def run_test(workspace: Path) -> dict[str, Any]:
    return run_cmd(
        [
            "dotnet",
            "test",
            TEST_PROJECT,
            "--no-restore",
            "--filter",
            TEST_FILTER,
            "--verbosity",
            "quiet",
        ],
        cwd=workspace,
        timeout=120,
        network_offline=True,
    )


def apply_candidate(target: Path, candidate: dict[str, Any]) -> None:
    mutations = candidate["mutations"]
    if len(mutations) != 1:
        raise RuntimeError("A5 C# expects exactly one mutation")
    mutation = mutations[0]
    if mutation["path"] != TARGET_REL:
        raise RuntimeError(f"unexpected mutation path: {mutation['path']}")
    if sha256_file(target) != mutation["expected_sha256"]:
        raise RuntimeError("candidate base hash mismatch")
    target.write_text(mutation["content_utf8"], encoding="utf-8")


def main() -> int:
    memory = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    generated = generate(SOURCE, include_prefixes=[TARGET_REL], max_candidates=10000)
    candidates = list(generated["candidates"])
    ranked = rank_candidates(candidates, memory)
    order = [int(row["base_index"]) for row in ranked["records"]]

    with tempfile.TemporaryDirectory(prefix="genesis-a5-csharp-") as temp:
        workspace = Path(temp) / "workspace"
        copy_repo(SOURCE, workspace)

        restore = run_cmd(
            ["dotnet", "restore", TEST_PROJECT, "--verbosity", "quiet"],
            cwd=workspace,
            timeout=300,
            network_offline=False,
        )
        if restore["exit_code"] != 0:
            payload = {
                "schema": "mira-genesis-autonomy-a5-csharp-result-v1",
                "classification": "APPARATUS_ABORT_RESTORE",
                "restore": restore,
                "external_model_calls": 0,
                "passed": False,
            }
            result = {**payload, "report_digest": digest_of(payload)}
            RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            print(json.dumps({"passed": False, "classification": payload["classification"]}, indent=2))
            return 2

        target = workspace / TARGET_REL
        original_text = target.read_text(encoding="utf-8")
        original_sha = sha256_file(target)

        baseline = run_test(workspace)
        if baseline["exit_code"] == 0:
            raise SystemExit("baseline unexpectedly passes")

        records: list[dict[str, Any]] = []
        winner: dict[str, Any] | None = None
        winner_candidate: dict[str, Any] | None = None

        for rank, base_index in enumerate(order[:BUDGET], start=1):
            target.write_text(original_text, encoding="utf-8")
            if sha256_file(target) != original_sha:
                raise RuntimeError("failed to reset frozen source")
            candidate = candidates[base_index]
            apply_candidate(target, candidate)
            outcome = run_test(workspace)
            record = {
                "rank": rank,
                "base_index": base_index,
                "id": candidate["id"],
                "label": candidate["label"],
                "operator": candidate["provenance"]["operator"],
                "candidate_digest": candidate["candidate_digest"],
                "passed": outcome["exit_code"] == 0,
                "test": outcome,
            }
            records.append(record)
            if record["passed"]:
                winner = record
                winner_candidate = candidate
                break

        replay = None
        if winner_candidate is not None:
            target.write_text(original_text, encoding="utf-8")
            apply_candidate(target, winner_candidate)
            replay = run_test(workspace)

    passed = bool(
        winner is not None
        and winner["operator"] == "integer_delta"
        and replay is not None
        and replay["exit_code"] == 0
    )

    payload: dict[str, Any] = {
        "schema": "mira-genesis-autonomy-a5-csharp-result-v1",
        "carrier_commit": "46f6fe0bc96e845d5b5cae2318cbf8d335d9b4e3",
        "issue_number": 724,
        "target_language": "csharp",
        "candidate_generation": {
            "schema": generated["schema"],
            "candidate_count": generated["candidate_count"],
            "truncated": generated["truncated"],
            "external_model_calls": generated["external_model_calls"],
        },
        "memory_digest": memory["memory_digest"],
        "memory_ranking_digest": ranked["ranking_digest"],
        "restore": restore,
        "baseline": baseline,
        "search_budget": BUDGET,
        "charged_candidate_executions": len(records),
        "records": records,
        "winner": winner,
        "winner_replay": replay,
        "external_model_calls": 0,
        "manual_candidate_repair": False,
        "retry_count": 0,
        "language_transfer_chain": ["javascript", "python", "csharp"],
        "passed": passed,
        "claim": "A5_THREE_LANGUAGE_RETAINED_STRATEGY_TRANSFER",
    }
    result = {**payload, "report_digest": digest_of(payload)}
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "candidate_count": generated["candidate_count"],
                "baseline_exit": baseline["exit_code"],
                "charged_candidate_executions": len(records),
                "winner": None if winner is None else winner["label"],
                "winner_operator": None if winner is None else winner["operator"],
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
