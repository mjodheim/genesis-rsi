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

from genesis import candidate_scheduler, exemplar_strategy, patch_templates, scalar_mutations
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
    mutations = list(candidate.get("mutations") or [])
    if not mutations:
        raise RuntimeError("candidate contains no mutations")

    paths = [str(m["path"]) for m in mutations]
    if len(paths) != len(set(paths)):
        raise RuntimeError("candidate contains duplicate mutation paths")

    for mutation in mutations:
        target = workspace / mutation["path"]
        if sha256_file(target) != mutation["expected_sha256"]:
            raise RuntimeError(f"candidate base hash mismatch: {mutation['path']}")

    for mutation in mutations:
        target = workspace / mutation["path"]
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


def build_schedule(
    source: Path,
    memory: dict[str, Any],
    prefixes: list[str],
    *,
    budget: int,
) -> dict[str, Any]:
    learned = candidate_scheduler.filter_target_scope(
        patch_templates.generate(
            source,
            memory.get("learned_line_templates", []),
            max_candidates=10000,
        )["candidates"],
        prefixes,
    )
    retained = candidate_scheduler.filter_target_scope(
        exemplar_strategy.generate_from_acquired(
            source,
            memory.get("acquired_strategies", []),
            max_candidates=10000,
        )["candidates"],
        prefixes,
    )
    exemplar = candidate_scheduler.filter_target_scope(
        exemplar_strategy.generate(source, max_candidates=10000)["candidates"],
        prefixes,
    )

    scalar = scalar_mutations.generate(
        source,
        include_prefixes=prefixes,
        max_candidates=10000,
    )["candidates"]
    counts = memory.get("operator_success_counts", {})
    scalar = [
        c
        for _, c in sorted(
            enumerate(scalar),
            key=lambda pair: (
                -int(counts.get(pair[1]["provenance"]["operator"], 0)),
                pair[0],
            ),
        )
    ]

    learned_coordinated = candidate_scheduler.compose_learned_candidates(
        learned,
        max_sites=2,
        max_candidates=128,
    )["candidates"]

    coordinated = candidate_scheduler.compose_scalar_candidates(
        source,
        scalar,
        max_sites=2,
        max_candidates=512,
    )["candidates"]
    coordinated = [
        c
        for _, c in sorted(
            enumerate(coordinated),
            key=lambda pair: (
                -int(counts.get(pair[1]["provenance"]["operator"], 0)),
                pair[0],
            ),
        )
    ]

    families = {
        "learned_coordinated": learned_coordinated,
        "scalar": scalar,
        "learned": learned,
        "coordinated": coordinated,
        "retained": retained,
        "exemplar": exemplar,
    }
    return candidate_scheduler.fair_schedule(families, budget=budget)


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

    schedule = build_schedule(source, memory, prefixes, budget=budget)
    candidates = list(schedule["candidates"])
    records: list[dict[str, Any]] = []
    winner = None
    winner_candidate = None

    with tempfile.TemporaryDirectory(prefix="genesis-a6b-auto-") as temp:
        root = Path(temp)
        for rank, candidate in enumerate(candidates, start=1):
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
                "coordination_size": candidate["provenance"].get("coordination_size", 1),
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
        with tempfile.TemporaryDirectory(prefix="genesis-a6b-auto-replay-") as temp:
            workspace = Path(temp) / "workspace"
            copy_repo(source, workspace)
            apply_candidate(workspace, winner_candidate)
            replay = run_evaluator(spec["evaluator_argv"], workspace, timeout)

    payload = {
        "schema": "mira-genesis-a6b-autonomous-task-result-v1",
        "task_id": spec["task_id"],
        "carrier": spec["carrier"],
        "baseline": baseline,
        "schedule": {
            "schema": schedule["schema"],
            "weights": schedule["weights"],
            "family_input_counts": schedule["family_input_counts"],
            "family_scheduled_counts": schedule["family_scheduled_counts"],
            "scheduled_count": schedule["scheduled_count"],
            "schedule_digest": schedule["schedule_digest"],
        },
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
    print(
        json.dumps(
            {
                "task_id": spec["task_id"],
                "scheduled_count": schedule["scheduled_count"],
                "family_scheduled_counts": schedule["family_scheduled_counts"],
                "charged": len(records),
                "winner": winner,
                "autonomous_passed": result["autonomous_passed"],
                "report_digest": result["report_digest"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if result["autonomous_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
