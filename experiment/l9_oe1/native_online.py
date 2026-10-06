"""OE1 best-first search over V36 native recombination tasks.

The external native execution cap remains fourteen. Unlike V36's fixed depth-three G7,
OE1 lets observed quality guide a branch deeper while budget remains. Candidate
generation itself is target-blind and every selected candidate is fully charged.
"""
from __future__ import annotations

from experiment.l9_oe1.improver import ImproverGenome
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v35 import native
from experiment.rsi_v36 import bank as v36_bank
from experiment.rsi_v36 import engine as v36

MAX_EVALUATIONS = v36.MAX_EVALUATIONS


def _native_distance(left, right, slots):
    a = left["ops"] + [0] * (slots - len(left["ops"]))
    b = right["ops"] + [0] * (slots - len(right["ops"]))
    return sum(x != y for x, y in zip(a, b)) / max(1, slots)


def _novelty(candidate, evaluated, slots):
    if not evaluated:
        return 1.0
    distances = sorted(
        _native_distance(candidate, row["genome"], slots)
        for row in evaluated.values()
    )
    nearest = distances[: min(3, len(distances))]
    return sum(nearest) / len(nearest)


def _children(host, genome):
    """Generate the V36 proposal grammar without V36's depth-three cutoff."""
    current = genome["ops"] + [0] * (host.task["slots"] - len(genome["ops"]))
    rows = {}

    def admit(ops, construction):
        row = host.row(native.genome(host.task["domain"], ops))
        if row["candidate"] == genome:
            return
        row["construction"] = construction
        rows.setdefault(row["source_sha256"], row)

    for index in range(0, len(current) - v36_bank.BLOCK + 1, v36_bank.BLOCK):
        for fragment in host.learned:
            admit(
                [
                    *current[:index],
                    *fragment["ops"],
                    *current[index + v36_bank.BLOCK:],
                ],
                {
                    "kind": "learned-splice",
                    "block_start": index,
                    **fragment,
                },
            )

    for index in range(len(current)):
        for op in range(5):
            if op != current[index]:
                admit(
                    [*current[:index], op, *current[index + 1:]],
                    {"kind": "point", "slot": index, "operator": op},
                )

    return tuple(rows.values())


def episode(
    task,
    global_position,
    history,
    arm="archive",
    *,
    improver=None,
    isolated=False,
    max_depth=None,
):
    improver = improver or ImproverGenome(replay_budget=12)
    host = v36.Host(task, history, arm, isolated=isolated)

    selected = host.selected["candidate"]
    selected_sha = host.selected["source_sha256"]
    max_depth = improver.replay_budget if max_depth is None else int(max_depth)

    paid_before_search = len(host.calls)
    search_budget = max(
        0,
        MAX_EVALUATIONS - paid_before_search - 1,  # reserve confirmation
    )

    evaluated = {
        selected_sha: {
            "genome": selected,
            "quality_milli": host.initial["quality_milli"],
            "depth": 0,
            "parent_sha": None,
            "construction": {"kind": "selected-root"},
        }
    }
    frontier = {}

    def offer(row, parent_sha, depth):
        sha = row["source_sha256"]
        if sha in evaluated:
            return
        item = frontier.setdefault(
            sha,
            {
                "row": row,
                "genome": row["candidate"],
                "parents": set(),
                "depth": depth,
                "construction_by_parent": {},
            },
        )
        item["parents"].add(parent_sha)
        item["depth"] = min(item["depth"], depth)
        item["construction_by_parent"][parent_sha] = row.get(
            "construction", {"kind": "search"}
        )

    if max_depth > 0:
        for child in _children(host, selected):
            offer(child, selected_sha, 1)

    spent = 0
    solved_call = next(
        (
            call
            for call in host.calls
            if call["evaluation"]["matched_slots"] == task["slots"]
        ),
        None,
    )

    while spent < search_budget and frontier and solved_call is None:
        scored = []
        for sha, item in frontier.items():
            parents = [
                parent for parent in item["parents"] if parent in evaluated
            ]
            if not parents:
                continue

            best_parent = max(
                parents,
                key=lambda parent: (
                    evaluated[parent]["quality_milli"],
                    parent,
                ),
            )
            parent_quality = evaluated[best_parent]["quality_milli"]
            novelty = _novelty(item["genome"], evaluated, task["slots"])
            score = (
                improver.replay_parent_quality_weight
                * (parent_quality / 1000.0)
                - improver.replay_depth_penalty * item["depth"]
                + improver.replay_candidate_novelty_weight * novelty
            )
            scored.append((score, sha, best_parent))

        if not scored:
            break

        scored.sort(key=lambda row: (-row[0], row[1]))
        _, chosen_sha, parent_sha = scored[0]
        item = frontier.pop(chosen_sha)
        row = dict(item["row"])
        construction = item["construction_by_parent"][parent_sha]
        row["construction"] = construction

        evaluation = host.evaluate(row)
        spent += 1
        evaluated[chosen_sha] = {
            "genome": row["candidate"],
            "quality_milli": evaluation["quality_milli"],
            "depth": item["depth"],
            "parent_sha": parent_sha,
            "construction": construction,
        }

        if evaluation["matched_slots"] == task["slots"]:
            solved_call = host.calls[-1]
            break

        if item["depth"] < max_depth:
            for child in _children(host, row["candidate"]):
                offer(child, chosen_sha, item["depth"] + 1)

    if solved_call is not None:
        host.kind = "verify"
        verification = host.evaluate(host.row(solved_call["genome"]))
        if verification != solved_call["evaluation"]:
            raise ValueError("OE1 native solution failed independent re-execution")

    if len(host.calls) > MAX_EVALUATIONS:
        raise ValueError("OE1 native search escaped fourteen-evaluation cap")

    programs = {}
    for call in host.calls:
        genome = call["genome"]
        sha = native.descriptor(genome)["source_sha256"]
        if sha in programs:
            continue

        old = history.get(sha)
        search_row = evaluated.get(sha)
        parent_sha = search_row["parent_sha"] if search_row else None
        construction = (
            search_row["construction"]
            if search_row
            else call.get("construction", {"kind": call["kind"]})
        )
        programs[sha] = {
            "genome": genome,
            "source_sha256": sha,
            "semantic_sha256": native.descriptor(genome)["semantic_sha256"],
            "parent_source_sha256": (
                old["parent_source_sha256"] if old else parent_sha
            ),
            "search_parent_source_sha256": parent_sha,
            "evaluation": call["evaluation"],
            "previously_observed": old is not None,
            "construction": construction,
            "donor_source_sha256": construction.get("donor_source_sha256"),
        }

    solved = [
        p for p in programs.values()
        if p["evaluation"]["matched_slots"] == task["slots"]
    ]
    old_solved = {
        entry["semantic_sha256"]
        for entry in history.values()
        if entry["successes"]
    }

    return {
        "task_sha256": digest(task),
        "global_position": global_position,
        "epoch": task["epoch"],
        "domain": task["domain"],
        "slots": task["slots"],
        "calls": host.calls,
        "search": {
            "represented_requests": spent,
            "best_quality_milli": max(
                p["evaluation"]["quality_milli"]
                for p in programs.values()
            ),
        },
        "programs": list(programs.values()),
        "selected_root_sha256": selected_sha,
        "screen_calls": host.screen_calls,
        "learned_fragments": host.learned,
        "charged_evaluations": len(host.calls),
        "policy_calls": spent,
        "solved": bool(solved),
        "archive_size_before": len(history),
        "new_first_solving_semantics": [
            p["semantic_sha256"]
            for p in solved
            if p["semantic_sha256"] not in old_solved
        ],
        "new_source_solves": [
            p["source_sha256"]
            for p in solved
            if p["source_sha256"] not in history
        ],
        "rediscovered": [
            p["semantic_sha256"]
            for p in solved
            if p["source_sha256"] in history
            and history[p["source_sha256"]]["successes"]
            and history[p["source_sha256"]]["last_success_position"]
            < global_position - 1
        ],
        "oe1": {
            "improver_sha256": improver.sha256(),
            "max_depth": max_depth,
            "search_budget": search_budget,
            "search_evaluations": spent,
        },
    }


def summary(rows, history_before=None):
    previous = {} if history_before is None else history_before
    full = v36.history_from(rows, previous)
    solved_entries = [entry for entry in full.values() if entry["successes"]]
    cost = sum(row["charged_evaluations"] for row in rows)
    new = sum(len(row["new_first_solving_semantics"]) for row in rows)
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "evaluations": cost,
        "first_solving_semantics": new,
        "discovery_per_1000_evaluations": new * 1000 // cost if cost else 0,
        "archive_size": len(full),
        "solved_semantic_size": len({
            entry["semantic_sha256"] for entry in solved_entries
        }),
        "rediscoveries": sum(len(row["rediscovered"]) for row in rows),
        "max_solved_length": max(
            (len(entry["genome"]["ops"]) for entry in solved_entries),
            default=0,
        ),
    }
