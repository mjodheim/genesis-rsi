"""V38 native macro search controlled by executable G7/G8 policy source."""
from __future__ import annotations

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v35 import native
from experiment.rsi_v36 import engine as v36
from experiment.rsi_v38 import bank as v38_bank
from experiment.rsi_v38 import engine as v38

CAP = 26


class Host:
    def __init__(self, task, history, *, isolated=False, call_cap=CAP):
        v38_bank.validate_task(task)
        self.task = task
        self.history = history
        self.isolated = isolated
        self.call_cap = int(call_cap)
        if self.call_cap < 3 or self.call_cap > CAP:
            raise ValueError("Invalid externally governed G8 call cap")
        self.calls = []
        self.forbidden_tokens = [task["task_id"], task["domain"]]
        self.width = max(1, task["slots"] // 2)
        self.learned = v38.fragments(
            history, task["domain"], "archive", task["slots"], self.width
        )
        root = self.row(native.genome(task["domain"], []), {
            "kind": "root",
            "start": 0,
            "width": 0,
            "mechanism_rank": 0,
        })
        self.initial = self.evaluate(root)
        self.root_row = root

    def row(self, genome, construction):
        genome = native.validate(genome)
        desc = native.descriptor(genome)
        return {
            "candidate": genome,
            **desc,
            "construction": construction,
        }

    def root(self):
        return {
            **self.root_row,
            "quality_milli": self.initial["quality_milli"],
        }

    def action(self, row):
        c = row.get("construction", {})
        start = int(c.get("start", 0))
        width = int(c.get("width", 0))
        return {
            "family": "native-recursive-macro",
            "structure_sha256": row["structure_sha256"],
            "target_axes": [f"slot-{i}" for i in range(start, start + width)],
            "mechanisms": [c.get("kind", "unknown")],
            "mechanism_rank": int(c.get("mechanism_rank", 0)),
        }

    def _body(self, genome, start, values):
        ops = genome["ops"] + [0] * (self.task["slots"] - len(genome["ops"]))
        return native.genome(
            self.task["domain"],
            ops[:start] + list(values) + ops[start + len(values):],
        )

    def children(self, genome, depth):
        if depth >= 2:
            return ()
        rows = {}
        if self.task["slots"] == 1 or not self.learned:
            for op in range(1, 5):
                candidate = self._body(genome, 0, [op])
                row = self.row(candidate, {
                    "kind": "point",
                    "start": 0,
                    "width": 1,
                    "operator": op,
                    "mechanism_rank": 1,
                })
                if candidate != genome:
                    rows.setdefault(row["source_sha256"], row)
            return tuple(rows.values())

        for start in (0, self.width):
            for fragment in self.learned:
                candidate = self._body(genome, start, fragment["ops"])
                row = self.row(candidate, {
                    "kind": "macro",
                    "start": start,
                    "width": self.width,
                    "mechanism_rank": 2,
                    "donor_source_sha256": fragment["donor_source_sha256"],
                    "acquired_position": fragment["acquired_position"],
                })
                if candidate != genome:
                    rows.setdefault(row["source_sha256"], row)
        return tuple(rows.values())

    def evaluate(self, row):
        if len(self.calls) >= self.call_cap - 1:
            raise ValueError("G8 macro search exhausted verification reserve")
        value = native.evaluate(
            self.task, row["candidate"], isolated=self.isolated
        )
        self.calls.append({
            "genome": row["candidate"],
            "construction": row["construction"],
            "evaluation": value,
        })
        return value


def episode(task, position, history, policy_source, *, isolated=False, call_cap=CAP):
    host = Host(task, history, isolated=isolated, call_cap=call_cap)
    caps = Caps(
        requests=call_cap - 2,
        rounds=12,
        parallelism=2,
        mutation_depth=2,
    )
    search = run_search(
        policy_source,
        host,
        caps=caps,
        isolated=isolated,
    )
    successes = [
        node for node in search["nodes"].values()
        if node.get("evaluation", {}).get("matched_slots") == task["slots"]
    ]
    if host.initial["matched_slots"] == task["slots"]:
        successes.append({
            "candidate": host.root_row["candidate"],
            "source_sha256": host.root_row["source_sha256"],
            "evaluation": host.initial,
            "parent_node_id": None,
            "node_id": "root",
        })

    verification = None
    if successes:
        winner = successes[0]
        value = native.evaluate(task, winner["candidate"], isolated=isolated)
        host.calls.append({
            "genome": winner["candidate"],
            "construction": {"kind": "verify"},
            "evaluation": value,
        })
        if value != winner["evaluation"]:
            raise ValueError("G8 macro winner failed independent confirmation")
        verification = value

    if len(host.calls) > call_cap:
        raise ValueError("G8 macro policy escaped fixed call cap")

    node_by_source = {
        node["source_sha256"]: node
        for node in search["nodes"].values()
    }
    programs = {}
    for call in host.calls:
        genome = call["genome"]
        desc = native.descriptor(genome)
        sha = desc["source_sha256"]
        if sha in programs:
            continue
        old = history.get(sha)
        node = node_by_source.get(sha)
        parent_id = node.get("parent_node_id") if node else None
        parent_sha = (
            search["nodes"][parent_id]["source_sha256"]
            if parent_id else None
        )
        programs[sha] = {
            "genome": genome,
            "source_sha256": sha,
            "semantic_sha256": desc["semantic_sha256"],
            "parent_source_sha256": (
                old["parent_source_sha256"] if old else parent_sha
            ),
            "search_parent_source_sha256": parent_sha,
            "evaluation": call["evaluation"],
            "previously_observed": old is not None,
            "construction": call["construction"],
            "donor_source_sha256": call["construction"].get(
                "donor_source_sha256"
            ),
        }

    solved = [
        p for p in programs.values()
        if p["evaluation"]["matched_slots"] == task["slots"]
    ]
    old_solved = {
        e["semantic_sha256"] for e in history.values() if e["successes"]
    }
    return {
        "task_sha256": digest(task),
        "global_position": position,
        "epoch": task["epoch"],
        "domain": task["domain"],
        "slots": task["slots"],
        "policy_sha256": search["policy_sha256"],
        "search": search,
        "programs": list(programs.values()),
        "calls": host.calls,
        "charged_evaluations": len(host.calls),
        "call_cap": call_cap,
        "solved": bool(solved),
        "new_first_solving_semantics": [
            p["semantic_sha256"]
            for p in solved
            if p["semantic_sha256"] not in old_solved
        ],
        "rediscovered": [
            p["semantic_sha256"]
            for p in solved
            if p["source_sha256"] in history
            and history[p["source_sha256"]]["successes"]
            and history[p["source_sha256"]]["last_success_position"]
            < position - 1
        ],
        "verification": verification,
    }


def history_from(rows, previous=None):
    return v36.history_from(rows, previous)


def summary(rows, previous=None):
    history = history_from(rows, previous)
    solved_entries = [e for e in history.values() if e["successes"]]
    calls = sum(r["charged_evaluations"] for r in rows)
    new = sum(len(r["new_first_solving_semantics"]) for r in rows)
    return {
        "tasks": len(rows),
        "solved": sum(r["solved"] for r in rows),
        "evaluations": calls,
        "first_solving_semantics": new,
        "discovery_per_1000_evaluations": (
            new * 1000 // calls if calls else 0
        ),
        "archive_size": len(history),
        "solved_semantic_size": len({
            e["semantic_sha256"] for e in solved_entries
        }),
        "rediscoveries": sum(len(r["rediscovered"]) for r in rows),
        "max_solved_length": max(
            (len(e["genome"]["ops"]) for e in solved_entries),
            default=0,
        ),
    }
