"""Complete charged native search with state-owned branch frontiers."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v31 import programs as policy
from experiment.rsi_v35 import bank, native

ARMS = ("archive", "greedy", "cold")
MAX_EVALUATIONS = 14


def history_from(rows, previous=None):
    history = {key: dict(value) for key, value in (previous or {}).items()}
    for row in rows:
        for program in row["programs"]:
            entry = history.setdefault(program["source_sha256"], {
                **program, "successes": 0, "last_success_position": -1})
            if program["evaluation"]["matched_slots"] == row["slots"]:
                entry["successes"] += 1
                entry["last_success_position"] = row["global_position"]
    return history


def frontiers(history, domain, arm):
    if arm not in ARMS:
        raise ValueError("Unknown native archive arm")
    successes = [e for e in history.values() if e["successes"] and e["genome"]["domain"] == domain]
    if arm == "cold":
        return []
    if arm == "greedy":
        return sorted(successes, key=lambda e: (-e["last_success_position"], e["source_sha256"]))[:1]
    result = []
    for first_operator in range(1, 5):
        branch = [e for e in successes if e["genome"]["ops"] and e["genome"]["ops"][0] == first_operator]
        if branch:
            result.append(min(branch, key=lambda e: (-len(e["genome"]["ops"]),
                                                     -e["last_success_position"], e["source_sha256"])))
    return sorted(result, key=lambda e: (-e["last_success_position"], e["source_sha256"]))


class Host:
    def __init__(self, task, history, arm, *, isolated=True, replay=None):
        bank.validate_task(task)
        self.task, self.history, self.arm = task, history, arm
        self.isolated, self.replay, self.calls = isolated, replay, []
        self.forbidden_tokens = [task["task_id"], task["domain"]]
        self.kind = "root"
        null = self.row(native.genome(task["domain"], []))
        observed = [(null, self.evaluate(null))]
        self.kind = "screen"
        for entry in frontiers(history, task["domain"], arm):
            proposal = self.row(entry["genome"])
            measured = self.evaluate(proposal)
            observed.append((proposal, measured))
            if measured["matched_slots"] == task["slots"]:
                break
        self.selected, self.initial = min(observed, key=lambda item: (
            -item[1]["matched_slots"], len(item[0]["candidate"]["ops"]), item[0]["source_sha256"]))
        self.screen_calls = len(observed) - 1
        self.caps = Caps(requests=12 - self.screen_calls, rounds=8, parallelism=2, mutation_depth=3)
        self.kind = "search"

    def row(self, genome):
        return {"candidate": native.validate(genome), **native.descriptor(genome)}

    def root(self):
        return {**self.selected, "quality_milli": self.initial["quality_milli"]}

    def action(self, row):
        return {"family": "native-composition", "structure_sha256": row["structure_sha256"],
                "target_axes": row["target_axes"]}

    def children(self, genome, depth):
        if depth >= self.caps.mutation_depth:
            return ()
        current = genome["ops"] + [0] * (self.task["slots"] - len(genome["ops"]))
        rows = []
        for index in range(len(current)):
            for op in range(5):
                if op != current[index]:
                    changed = [*current[:index], op, *current[index + 1:]]
                    rows.append(self.row(native.genome(self.task["domain"], changed)))
        return tuple(rows)

    def evaluate(self, row):
        if self.replay is None:
            value = native.evaluate(self.task, row["candidate"], isolated=self.isolated)
        else:
            if len(self.calls) >= len(self.replay):
                raise ValueError("Replay requested an unobserved call")
            old = self.replay[len(self.calls)]
            if old["kind"] != self.kind or old["genome"] != row["candidate"]:
                raise ValueError("Altered screening/search/verification order")
            value = old["evaluation"]
        self.calls.append({"kind": self.kind, "genome": row["candidate"], "evaluation": value})
        return value


def episode(task, global_position, history, arm, *, isolated=True, replay=None):
    host = Host(task, history, arm, isolated=isolated, replay=None if replay is None else replay["calls"])
    # Replay executes the pinned policy locally, never charging a new experiment.
    search = run_search(policy.parent(), host, caps=host.caps, isolated=isolated and replay is None)
    if replay is not None:
        search["isolated_policy_processes"] = isolated
    successes = [call for call in host.calls if call["evaluation"]["matched_slots"] == task["slots"]]
    if successes:
        host.kind = "verify"
        verification = host.evaluate(host.row(successes[0]["genome"]))
        if verification != successes[0]["evaluation"]:
            raise ValueError("Exact solution failed independent re-execution")
    if len(host.calls) > MAX_EVALUATIONS:
        raise ValueError("Candidate, screening and verification budget exceeded")
    if replay is not None and len(host.calls) != len(replay["calls"]):
        raise ValueError("Omitted paid evaluation")
    node_by_source = {node["source_sha256"]: node for node in search["nodes"].values()}
    programs = {}
    for call in host.calls:
        genome, evaluation = call["genome"], call["evaluation"]
        sha = native.descriptor(genome)["source_sha256"]
        if sha in programs:
            if programs[sha]["evaluation"] != evaluation:
                raise ValueError("Conflicting duplicate receipt")
            continue
        old = history.get(sha)
        node = node_by_source.get(sha)
        parent_id = node["parent_node_id"] if node else None
        parent_sha = search["nodes"][parent_id]["source_sha256"] if parent_id else None
        programs[sha] = {"genome": genome, "source_sha256": sha,
                         "semantic_sha256": native.descriptor(genome)["semantic_sha256"],
                         "parent_source_sha256": old["parent_source_sha256"] if old else parent_sha,
                         "search_parent_source_sha256": parent_sha, "evaluation": evaluation,
                         "previously_observed": old is not None}
    solved = [p for p in programs.values() if p["evaluation"]["matched_slots"] == task["slots"]]
    old_solved = {entry["semantic_sha256"] for entry in history.values() if entry["successes"]}
    return {"task_sha256": digest(task), "global_position": global_position, "epoch": task["epoch"],
            "domain": task["domain"], "slots": task["slots"], "calls": host.calls, "search": search,
            "programs": list(programs.values()), "selected_root_sha256": host.selected["source_sha256"],
            "screen_calls": host.screen_calls, "charged_evaluations": len(host.calls),
            "policy_calls": 1 + search["rounds"] + int(search["stop_reason"] == "policy_empty_batch"),
            "solved": bool(solved), "archive_size_before": len(history),
            "new_first_solving_semantics": [p["semantic_sha256"] for p in solved if p["semantic_sha256"] not in old_solved],
            "new_source_solves": [p["source_sha256"] for p in solved if p["source_sha256"] not in history],
            "rediscovered": [p["semantic_sha256"] for p in solved if p["source_sha256"] in history
                             and history[p["source_sha256"]]["successes"]
                             and history[p["source_sha256"]]["last_success_position"] < global_position - 1]}


def verify_episode(task, position, history, arm, row, *, isolated=True):
    if row["task_sha256"] != digest(task) or row["global_position"] != position:
        raise ValueError("Substituted task or position")
    for call in row["calls"]:
        value = call["genome"]
        expected_outputs = native.execute(value, task["inputs"], task["slots"], isolated=False)
        expected = native.receipt(task, value, expected_outputs, isolated=isolated)
        if expected != call["evaluation"]:
            raise ValueError("Altered native output, source or evaluator receipt")
    rebuilt = episode(task, position, history, arm, isolated=isolated, replay=row)
    if digest(rebuilt) != digest(row):
        raise ValueError("Altered policy, archive, ancestry, novelty or accounting")
    return True


def summary(rows, history_before=None):
    previous = {} if history_before is None else history_before
    full = history_from(rows, previous)
    solved = [entry for entry in full.values() if entry["successes"]]
    cost = sum(row["charged_evaluations"] for row in rows)
    new = sum(len(row["new_first_solving_semantics"]) for row in rows)
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows),
            "evaluations": cost, "policy_calls": sum(row["policy_calls"] for row in rows),
            "first_solving_semantics": new, "new_source_solves": sum(len(row["new_source_solves"]) for row in rows),
            "discovery_per_1000_evaluations": new * 1000 // cost if cost else 0,
            "archive_size": len(full), "solved_semantic_size": len({e["semantic_sha256"] for e in solved}),
            "branches": len({e["genome"]["ops"][0] for e in solved if e["genome"]["ops"]}),
            "rediscoveries": sum(len(row["rediscovered"]) for row in rows),
            "max_solved_length": max((len(e["genome"]["ops"]) for e in solved), default=0)}
