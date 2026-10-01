"""Persistent branching around unchanged G7 under a fixed external budget."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v31 import bank, programs
from experiment.rsi_v31.archive import Archive

CAPS = Caps(requests=12, rounds=8, parallelism=2, mutation_depth=3)
ARMS = ("archive", "greedy", "cold")


def execute(genome, inputs, *, isolated=True):
    source = programs.render(genome)
    if not isolated:
        return [programs.transform(genome, value) for value in inputs]
    with tempfile.TemporaryDirectory(prefix="v31-transform-") as temporary:
        path = Path(temporary) / "program.py"
        path.write_text(source)
        result = subprocess.run([sys.executable, "-I", "-S", str(Path(__file__).with_name("worker.py")), str(path)],
                                input=json.dumps({"inputs": inputs}), text=True, capture_output=True,
                                cwd=temporary, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=3)
    if result.returncode:
        raise ValueError("Isolated transducer failed: " + result.stderr[-500:])
    values = json.loads(result.stdout)
    if type(values) is not list or len(values) != len(inputs) or any(type(x) is not int for x in values):
        raise ValueError("Invalid program output")
    return values


class Host:
    forbidden_tokens = []

    def __init__(self, task, history, arm, *, isolated=True, receipts=None):
        bank.validate_task(task)
        if arm not in ARMS:
            raise ValueError("Unknown retention arm")
        self.task, self.isolated, self.receipts = task, isolated, receipts
        self.history = {key: value for key, value in history.items() if value["genome"]["width"] == task["width"]}
        if arm == "cold":
            self.history = {}
        elif arm == "greedy" and self.history:
            latest = max(self.history.values(), key=lambda row: (row["last_success_position"], row["source_sha256"]))
            self.history = {latest["source_sha256"]: latest}
        self.root_genome = programs.identity(task["width"])
        self.initial = self.evaluate(self.row(self.root_genome))

    def row(self, genome):
        return {"candidate": programs.validate(genome), **programs.descriptor(genome)}

    def root(self):
        return {**self.row(self.root_genome), "quality_milli": self.initial["quality_milli"]}

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        rows = []
        if genome == self.root_genome:
            # Retrieval is fixed engineering, using only already observed success/recency.
            # No current task family, target, input/output pair or future quality enters it.
            rows.extend(self.row(row["genome"]) for row in sorted(self.history.values(),
                        key=lambda row: (-row["successes"], -row["last_success_position"], row["source_sha256"])))
        rows.extend(self.row(row) for row in programs.neighbors(genome))
        unique = {}
        for row in rows:
            unique.setdefault(row["source_sha256"], row)
        return tuple(unique.values())

    def action(self, row):
        return {"family": "bounded-transducer", "structure_sha256": row["structure_sha256"],
                "target_axes": row["target_axes"]}

    def evaluate(self, row):
        sha = row["source_sha256"]
        if self.receipts is not None:
            if sha not in self.receipts:
                raise ValueError("Replay requested an unobserved evaluation")
            return self.receipts[sha]
        values = execute(row["candidate"], self.task["inputs"], isolated=self.isolated)
        target = [programs.transform(self.task["target"], value) for value in self.task["inputs"]]
        width = self.task["width"]
        matches = sum(width - (actual ^ expected).bit_count() for actual, expected in zip(values, target))
        return {"accepted": True, "source_sha256": sha, "quality_milli": matches * 1000 // (len(values) * width),
                "output_sha256": digest(values), "evaluator_task_sha256": digest(self.task)}


def binding(tasks, arm, freeze_sha256):
    return {"schema": "mira-genesis-v31-archive-binding-v1", "stream_sha256": bank.validate_stream(tasks),
            "arm": arm, "freeze_sha256": freeze_sha256, "policy_sha256": programs.PARENT_SHA256,
            "caps": CAPS.__dict__, "root_evaluations_per_task": 1}


def history_from(rows):
    history = {}
    for episode in rows:
        for row in episode["programs"]:
            sha = row["source_sha256"]
            entry = history.setdefault(sha, {**row, "successes": 0, "last_success_position": -1})
            if row["quality_milli"] == 1000:
                entry["successes"] += 1
                entry["last_success_position"] = episode["position"]
    return history


def episode(task, position, history, arm, *, isolated=True, replay=None):
    receipts = None
    if replay is not None:
        receipts = {row["source_sha256"]: row["evaluation"] for row in replay["programs"]}
    host = Host(task, history, arm, isolated=isolated, receipts=receipts)
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)
    rows = []
    for key, node in search["nodes"].items():
        genome = node["candidate"]
        evaluation = host.initial if key == "root" else node["evaluation"]
        sha = programs.descriptor(genome)["source_sha256"]
        if node["source_sha256"] != sha:
            raise ValueError("Substituted transducer source")
        origin = history.get(sha)
        parent_node = node["parent_node_id"]
        parent_sha = search["nodes"][parent_node]["source_sha256"] if parent_node else None
        rows.append({"source_sha256": sha, "genome": genome, "semantic_sha256": digest(genome),
                     "parent_source_sha256": origin["parent_source_sha256"] if origin else parent_sha,
                     "search_parent_source_sha256": parent_sha, "evaluation": evaluation,
                     "quality_milli": evaluation["quality_milli"], "previously_observed": origin is not None})
    successes = [row for row in rows if row["quality_milli"] == 1000]
    new_successes = [row for row in successes if row["source_sha256"] not in history]
    rediscovered = [row for row in successes if row["source_sha256"] in history
                    and history[row["source_sha256"]]["last_success_position"] < position - 1]
    return {"position": position, "task_sha256": digest(task), "window": task["window"],
            "task_family": task["family"], "width": task["width"], "search": search, "programs": rows,
            "root_evaluation": host.initial, "charged_evaluations": search["represented_requests"] + 1,
            "solved": bool(successes), "new_solutions": [row["source_sha256"] for row in new_successes],
            "rediscovered": [row["source_sha256"] for row in rediscovered], "archive_size_before": len(history)}


def run_stream(tasks, arm, path, frozen, *, isolated=True, stop_after=None):
    identity = binding(tasks, arm, frozen)
    archive = Archive(path, identity, create=not Path(path).exists())
    rows = archive.episodes()
    if len(rows) > len(tasks) or any(row["task_sha256"] != digest(task) for row, task in zip(rows, tasks)):
        raise ValueError("Checkpoint is not an exact stream prefix")
    history = history_from(rows)
    limit = len(tasks) if stop_after is None else min(stop_after, len(tasks))
    for position in range(len(rows), limit):
        task = tasks[position]
        head = archive.read()[-1]["sha256"]
        started = archive.append("start", {"position": position, "task_sha256": digest(task),
                                 "reserved_evaluations": CAPS.requests + 1}, expected_head=head)
        # A crash during this transaction is visibly pending and cannot be retried for free.
        row = episode(task, position, history, arm, isolated=isolated)
        archive.append("episode", row, expected_head=started)
        rows.append(row)
        history = history_from(rows)
    return rows, archive.read()[-1]["sha256"]


def verify_stream(tasks, arm, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task, failure or incomplete stream")
    history = {}
    prefix = []
    for position, (task, row) in enumerate(zip(tasks, rows)):
        for program in row["programs"]:
            expected = Host(task, {}, "cold", isolated=False).evaluate(Host.row(None, program["genome"]))
            if digest(expected) != digest(program["evaluation"]):
                raise ValueError("Altered evaluator receipt")
        reconstructed = episode(task, position, history, arm, isolated=isolated, replay=row)
        if digest(reconstructed) != digest(row):
            raise ValueError("Altered policy decision, ancestry, cost, archive or recovery")
        prefix.append(row)
        history = history_from(prefix)
    return True


def windows(rows):
    result = []
    families, semantics = set(), set()
    for window in sorted({row["window"] for row in rows}):
        subset = [row for row in rows if row["window"] == window]
        families.update((row["task_family"], row["width"]) for row in subset)
        semantics.update(program["semantic_sha256"] for row in subset for program in row["programs"])
        new = sum(len(row["new_solutions"]) for row in subset)
        cost = sum(row["charged_evaluations"] for row in subset)
        result.append({"window": window, "tasks": len(subset), "solved": sum(row["solved"] for row in subset),
                       "new_solutions": new, "new_solutions_per_1000_evaluations": new * 1000 // cost,
                       "evaluations": cost, "archive_semantic_size": len(semantics),
                       "cumulative_task_family_widths": len(families),
                       "rediscoveries": sum(len(row["rediscovered"]) for row in subset)})
    return result
