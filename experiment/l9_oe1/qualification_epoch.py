"""Fresh-process epoch runner for the prospective L9-OE1 programme."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiment.l9_oe1 import coded_native, qualification_bank
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import engine as v36

ARMS = ("coded-archive", "archive-g7", "greedy-g7", "cold-g7")


def _default_state(arm):
    if arm == "coded-archive":
        return {
            "kind": "coded",
            "motifs": [],
            "code_hashes": {},
            "seen_semantics": {},
            "position": 0,
        }
    return {
        "kind": "control",
        "history": {},
        "seen_semantics": {},
        "position": 0,
    }


def _load_state(path, arm):
    if path.exists():
        return json.loads(path.read_text())
    return _default_state(arm)


def _semantic_ledger(state, semantics, position):
    new = 0
    rediscovery = 0
    for semantic in semantics:
        previous = state["seen_semantics"].get(semantic)
        if previous is None:
            new += 1
        elif previous < position - 1:
            rediscovery += 1
        state["seen_semantics"][semantic] = position
    return new, rediscovery


def _compact_history(history):
    result = {}
    for sha, entry in history.items():
        result[sha] = {
            "genome": entry["genome"],
            "source_sha256": entry["source_sha256"],
            "semantic_sha256": entry["semantic_sha256"],
            "parent_source_sha256": entry.get("parent_source_sha256"),
            "search_parent_source_sha256": entry.get("search_parent_source_sha256"),
            "construction": entry.get("construction", {}),
            "donor_source_sha256": entry.get("donor_source_sha256"),
            "successes": entry["successes"],
            "first_success_position": entry["first_success_position"],
            "last_success_position": entry["last_success_position"],
        }
    return result


def _verify_coded_state(state):
    motifs = [list(row) for row in state["motifs"]]
    if len(motifs) != 4:
        return
    for key, expected in state["code_hashes"].items():
        code = coded_native.design_code(motifs, int(key))
        if code is None or code["code_sha256"] != expected:
            raise ValueError("Persisted coded constructor failed recovery")


def _run_coded(tasks, state, *, isolated):
    _verify_coded_state(state)
    rows = []
    epoch = tasks[0]["epoch"]
    code = None

    if epoch >= 3:
        motifs = [list(row) for row in state["motifs"]]
        if len(motifs) == 4:
            blocks = tasks[0]["slots"] // coded_native.BLOCK
            code = coded_native.design_code(motifs, blocks)
            if code is not None:
                old = state["code_hashes"].get(str(blocks))
                if old is not None and old != code["code_sha256"]:
                    raise ValueError("Codebook changed after persistence")
                state["code_hashes"][str(blocks)] = code["code_sha256"]

    for task in tasks:
        position = state["position"]
        if epoch < 3:
            result = coded_native.acquire(task, isolated=isolated)
        elif code is not None:
            result = coded_native.solve(
                task,
                [list(row) for row in state["motifs"]],
                code,
                isolated=isolated,
            )
        else:
            result = {"solved": False, "genome": None, "calls": []}

        charged = len(result["calls"])
        if charged > coded_native.MAX_CALLS:
            raise ValueError("Qualification coded arm escaped cap")

        semantics = []
        if result["solved"] and result["genome"] is not None:
            descriptor = native.descriptor(result["genome"])
            semantics = [descriptor["semantic_sha256"]]
            if epoch == 2 and len(result["genome"]["ops"]) == coded_native.BLOCK:
                motif = list(result["genome"]["ops"])
                known = {tuple(row) for row in state["motifs"]}
                if tuple(motif) not in known:
                    state["motifs"].append(motif)
                    state["motifs"].sort()

        new, rediscovery = _semantic_ledger(state, semantics, position)
        rows.append({
            "task_id": task["task_id"],
            "solved": bool(result["solved"]),
            "charged_evaluations": charged,
            "semantics": semantics,
            "new_semantics": new,
            "rediscoveries": rediscovery,
        })
        state["position"] = position + 1

    return rows, state


def _run_control(tasks, state, arm, *, isolated):
    control_arm = {
        "archive-g7": "archive",
        "greedy-g7": "greedy",
        "cold-g7": "cold",
    }[arm]
    history = state.get("history", {})
    rows = []

    for task in tasks:
        position = state["position"]
        actor_history = {} if control_arm == "cold" else history
        result = v36.episode(
            task,
            position,
            actor_history,
            control_arm,
            isolated=isolated,
        )
        if result["charged_evaluations"] > v36.MAX_EVALUATIONS:
            raise ValueError("Qualification control escaped cap")

        semantics = sorted({
            program["semantic_sha256"]
            for program in result["programs"]
            if program["evaluation"]["matched_slots"] == task["slots"]
        })
        new, rediscovery = _semantic_ledger(state, semantics, position)

        rows.append({
            "task_id": task["task_id"],
            "solved": bool(result["solved"]),
            "charged_evaluations": result["charged_evaluations"],
            "semantics": semantics,
            "new_semantics": new,
            "rediscoveries": rediscovery,
        })

        if control_arm != "cold":
            history = v36.history_from([result], history)
        state["position"] = position + 1

    state["history"] = _compact_history(history)
    return rows, state


def run_epoch(tasks, arm, state=None, *, isolated=True):
    if arm not in ARMS:
        raise ValueError("Unknown qualification arm")
    if not tasks:
        raise ValueError("Empty qualification epoch")

    state = _default_state(arm) if state is None else state
    before = digest(state)

    if arm == "coded-archive":
        rows, state = _run_coded(tasks, state, isolated=isolated)
    else:
        rows, state = _run_control(tasks, state, arm, isolated=isolated)

    after = digest(state)
    summary = {
        "arm": arm,
        "domain": tasks[0]["domain"],
        "epoch": tasks[0]["epoch"],
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "evaluations": sum(row["charged_evaluations"] for row in rows),
        "max_task_evaluations": max(row["charged_evaluations"] for row in rows),
        "first_solving_semantics": sum(row["new_semantics"] for row in rows),
        "rediscoveries": sum(row["rediscoveries"] for row in rows),
        "failures": [row["task_id"] for row in rows if not row["solved"]],
        "state_before_sha256": before,
        "state_after_sha256": after,
        "motif_parents": len(state.get("motifs", [])),
        "codebook_descendants": len(state.get("code_hashes", {})),
        "code_hashes": dict(state.get("code_hashes", {})),
    }
    return summary, state


def _epoch_tasks(domain, epoch):
    return [
        task
        for task in qualification_bank.stream(domain)
        if task["epoch"] == epoch
    ]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--domain", choices=native.DOMAINS, required=True)
    parser.add_argument("--epoch", type=int, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-nonisolated", action="store_true")
    args = parser.parse_args(argv)

    if not 0 <= args.epoch < qualification_bank.EPOCHS:
        raise ValueError("Qualification epoch outside frozen schedule")

    state = _load_state(args.state, args.arm)
    summary, state = run_epoch(
        _epoch_tasks(args.domain, args.epoch),
        args.arm,
        state,
        isolated=not args.development_nonisolated,
    )

    args.state.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.state.write_text(
        json.dumps(state, sort_keys=True, separators=(",", ":")) + "\n"
    )
    args.output.write_text(
        json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n"
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
