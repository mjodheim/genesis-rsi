"""Auditable sustained native engine for the OE1 L9 qualification candidate."""
from __future__ import annotations

from experiment.l9_oe1.mastermind import MAX_CALLS, State, solve
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank as v36_bank

ARMS = ("archive", "greedy", "cold")
PROBE_SALT = "mira-genesis-l9-oe1-information-gain-v1"


def _probe_seed(task, global_position):
    return int(
        digest([
            PROBE_SALT,
            task["domain"],
            global_position,
            task["slots"],
        ])[:16],
        16,
    )


class QualificationState:
    def __init__(self, arm):
        if arm not in ARMS:
            raise ValueError("Unknown OE1 qualification arm")
        self.arm = arm
        self.solver = State(retention=arm)
        self.seen_semantics = set()
        self.seen_sources = set()
        self.negative_sources = set()
        self.last_success_position = {}
        self.max_solved_slots = 0

    def snapshot(self):
        return {
            "arm": self.arm,
            "solver": self.solver.snapshot(),
            "seen_semantics": sorted(self.seen_semantics),
            "seen_sources": sorted(self.seen_sources),
            "negative_sources": sorted(self.negative_sources),
            "last_success_position": {
                key: self.last_success_position[key]
                for key in sorted(self.last_success_position)
            },
            "max_solved_slots": self.max_solved_slots,
        }

    @classmethod
    def restore(cls, value):
        state = cls(value["arm"])
        state.solver = State.restore(value["solver"])
        state.seen_semantics = set(value["seen_semantics"])
        state.seen_sources = set(value["seen_sources"])
        state.negative_sources = set(value["negative_sources"])
        state.last_success_position = {
            key: int(position)
            for key, position in value["last_success_position"].items()
        }
        state.max_solved_slots = int(value["max_solved_slots"])
        return state


def _branches(snapshot):
    return sum(
        len(values)
        for values in snapshot["solver"]["solutions_by_slots"].values()
    )


def episode(
    task,
    global_position,
    state,
    *,
    isolated=True,
    replay=None,
):
    v36_bank.validate_task(task)
    if state.arm not in ARMS:
        raise ValueError("Invalid OE1 state arm")

    before = state.snapshot()
    old_semantics = set(state.seen_semantics)
    old_sources = set(state.seen_sources)
    old_last = dict(state.last_success_position)

    result = solve(
        task,
        state.solver,
        seed=_probe_seed(task, global_position),
        isolated=isolated,
        replay=replay,
    )
    calls = result["calls"]
    if len(calls) > MAX_CALLS:
        raise ValueError("OE1 sustained task escaped fourteen-call cap")

    programs = []
    unique_sources = set()
    for call in calls:
        genome = call["genome"]
        descriptor = native.descriptor(genome)
        source = descriptor["source_sha256"]
        if source in unique_sources:
            continue
        unique_sources.add(source)
        evaluation = call["evaluation"]
        programs.append({
            "genome": genome,
            "source_sha256": source,
            "semantic_sha256": descriptor["semantic_sha256"],
            "evaluation": evaluation,
            "kind": call["kind"],
            "previously_observed": source in old_sources,
        })
        state.seen_sources.add(source)
        if evaluation["matched_slots"] < task["slots"]:
            state.negative_sources.add(source)

    new_semantics = []
    new_sources = []
    rediscovered = []
    solved_semantic = None
    solved_source = None

    if result["solved"]:
        final = native.genome(task["domain"], result["final_ops"])
        descriptor = native.descriptor(final)
        solved_semantic = descriptor["semantic_sha256"]
        solved_source = descriptor["source_sha256"]

        if solved_semantic not in old_semantics:
            new_semantics.append(solved_semantic)
        if solved_source not in old_sources:
            new_sources.append(solved_source)
        if (
            solved_semantic in old_semantics
            and old_last.get(solved_semantic, -1) < global_position - 1
        ):
            rediscovered.append(solved_semantic)

        state.seen_semantics.add(solved_semantic)
        state.seen_sources.add(solved_source)
        state.last_success_position[solved_semantic] = global_position
        state.max_solved_slots = max(state.max_solved_slots, task["slots"])

    after = state.snapshot()
    current_branches = len(
        state.solver.solutions_by_slots.get(task["slots"], ())
    )

    return {
        "schema": "mira-genesis-l9-oe1-episode-v1",
        "task_sha256": digest(task),
        "global_position": global_position,
        "epoch": task["epoch"],
        "domain": task["domain"],
        "slots": task["slots"],
        "arm": state.arm,
        "probe_seed": _probe_seed(task, global_position),
        "calls": calls,
        "programs": programs,
        "charged_evaluations": len(calls),
        "policy_calls": sum(call["kind"] != "verify" for call in calls),
        "solved": result["solved"],
        "solved_semantic_sha256": solved_semantic,
        "solved_source_sha256": solved_source,
        "new_first_solving_semantics": new_semantics,
        "new_source_solves": new_sources,
        "rediscovered": rediscovered,
        "mode": result["mode"],
        "remaining_hypotheses": result["remaining_hypotheses"],
        "state_before_sha256": digest(before),
        "state_after": after,
        "state_after_sha256": digest(after),
        "evaluated_archive_size": len(after["seen_sources"]),
        "negative_archive_size": len(after["negative_sources"]),
        "solved_semantic_size": len(after["seen_semantics"]),
        "branches": _branches(after),
        "active_branches_current_slots": current_branches,
        "motifs": len(after["solver"]["motifs"]),
        "max_solved_length": after["max_solved_slots"],
    }


def verify_episode(task, global_position, state, row, *, isolated=True):
    if (
        row["task_sha256"] != digest(task)
        or row["global_position"] != global_position
        or row["arm"] != state.arm
        or row["state_before_sha256"] != digest(state.snapshot())
    ):
        raise ValueError("Substituted OE1 task, position, arm or state")

    for call in row["calls"]:
        genome = call["genome"]
        outputs = native.execute(
            genome,
            task["inputs"],
            task["slots"],
            isolated=False,
        )
        expected = native.receipt(
            task,
            genome,
            outputs,
            isolated=isolated,
        )
        if expected != call["evaluation"]:
            raise ValueError("Altered OE1 native output or evaluator receipt")

    clone = QualificationState.restore(state.snapshot())
    rebuilt = episode(
        task,
        global_position,
        clone,
        isolated=isolated,
        replay=row["calls"],
    )
    if digest(rebuilt) != digest(row):
        raise ValueError("Altered OE1 policy, archive, replay or accounting")
    return True


def apply_verified_row(state, row):
    if row["state_before_sha256"] != digest(state.snapshot()):
        raise ValueError("OE1 state chain does not match episode predecessor")
    restored = QualificationState.restore(row["state_after"])
    if restored.arm != state.arm:
        raise ValueError("OE1 episode changed archive arm")
    return restored


def summary(rows):
    if not rows:
        return {
            "tasks": 0,
            "solved": 0,
            "evaluations": 0,
            "policy_calls": 0,
            "first_solving_semantics": 0,
            "new_source_solves": 0,
            "rediscoveries": 0,
            "evaluated_archive_size": 0,
            "negative_archive_size": 0,
            "solved_semantic_size": 0,
            "branches": 0,
            "active_branches_current_slots": 0,
            "motifs": 0,
            "max_solved_length": 0,
            "discovery_per_1000_evaluations": 0,
        }

    last = rows[-1]
    evaluations = sum(row["charged_evaluations"] for row in rows)
    discoveries = sum(
        len(row["new_first_solving_semantics"]) for row in rows
    )
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "evaluations": evaluations,
        "policy_calls": sum(row["policy_calls"] for row in rows),
        "first_solving_semantics": discoveries,
        "new_source_solves": sum(
            len(row["new_source_solves"]) for row in rows
        ),
        "rediscoveries": sum(len(row["rediscovered"]) for row in rows),
        "evaluated_archive_size": last["evaluated_archive_size"],
        "negative_archive_size": last["negative_archive_size"],
        "solved_semantic_size": last["solved_semantic_size"],
        "branches": last["branches"],
        "active_branches_current_slots": last[
            "active_branches_current_slots"
        ],
        "motifs": last["motifs"],
        "max_solved_length": last["max_solved_length"],
        "discovery_per_1000_evaluations": (
            discoveries * 1000 // evaluations if evaluations else 0
        ),
    }
