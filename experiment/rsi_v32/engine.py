"""Bounded retrieval from past receipts, with unchanged G7 choosing the route.

This is project-directed Track B apparatus, not acquired new lineage machinery.
V31's evaluator, transducers, isolated policy ABI and durable archive are reused.
"""
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank, engine as v31, programs
from experiment.rsi_v31.archive import Archive

CAPS = v31.CAPS
ARMS = ("adaptive", "selector_ablation", "recency", "greedy", "cold")
TOLERANCES = (0, 25, 50, 75, 100, 150, 250, 1000)
MAX_EVALUATIONS = CAPS.requests + 2  # one root probe and one controller call


def controller(arm):
    if arm not in ARMS:
        raise ValueError("Unknown memory-selection arm")
    if arm == "adaptive":
        return programs.parent()
    if arm == "selector_ablation":
        return family.parent()  # exact G6, with G7's acquired selector removed
    return family.fixed({"recency": "exploration", "greedy": "scheduling", "cold": "generation"}[arm])


def history_from(episodes):
    history = v31.history_from(episodes)
    for entry in history.values():
        entry["successful_root_qualities"] = []
    for episode in episodes:
        quality = episode["root_evaluation"]["quality_milli"]
        for row in episode["programs"]:
            if row["quality_milli"] == 1000:
                history[row["source_sha256"]]["successful_root_qualities"].append(quality)
    return history


class Host(v31.Host):
    def __init__(self, task, history, arm, tolerance, *, isolated=True, receipts=None):
        if type(tolerance) is not int or tolerance not in TOLERANCES:
            raise ValueError("Unknown predeclared compatibility tolerance")
        # The base host executes exactly one identity probe. Its history has no
        # authority over the evaluator or worker and is filtered by program width.
        super().__init__(task, history, "archive", isolated=isolated, receipts=receipts)
        self.arm, self.tolerance = arm, tolerance
        quality = self.initial["quality_milli"]
        champions = [entry for entry in self.history.values() if entry["successes"]]
        self.ranked = sorted(champions, key=lambda entry: (
            min(abs(quality - old) for old in entry["successful_root_qualities"]),
            -entry["last_success_position"], -entry["successes"], entry["source_sha256"]))
        nearest = (min(abs(quality - old) for old in self.ranked[0]["successful_root_qualities"])
                   if self.ranked else None)
        compatible = nearest is not None and nearest <= tolerance
        diagnostics = {"exploration": int(compatible), "generation": int(not compatible), "scheduling": 0}
        target = meta.select(controller(arm), diagnostics, isolated=isolated)
        if arm == "recency":
            self.ranked = sorted(champions, key=lambda entry: (
                -entry["last_success_position"], -entry["successes"], entry["source_sha256"]))
        count = {"identity": 2, "exploration": 2, "generation": 0, "scheduling": 1}[target]
        self.retrieved = self.ranked[:count]
        self.routing = {"controller_sha256": digest_bytes(controller(arm).encode()),
                        "diagnostics": diagnostics, "nearest_distance_milli": nearest,
                        "target": target, "retrieved_sources": [x["source_sha256"] for x in self.retrieved],
                        "controller_calls": 1}

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        rows = ([self.row(entry["genome"]) for entry in self.retrieved]
                if genome == self.root_genome else [])
        rows.extend(self.row(row) for row in programs.neighbors(genome))
        unique = {}
        for row in rows:
            unique.setdefault(row["source_sha256"], row)
        return tuple(unique.values())


def episode(task, position, history, arm, tolerance, *, isolated=True, replay=None):
    receipts = None if replay is None else {row["source_sha256"]: row["evaluation"] for row in replay["programs"]}
    host = Host(task, history, arm, tolerance, isolated=isolated, receipts=receipts)
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
    new = [row["source_sha256"] for row in successes if row["source_sha256"] not in history]
    rediscovered = [row["source_sha256"] for row in successes if row["source_sha256"] in history
                   and history[row["source_sha256"]]["last_success_position"] < position - 1]
    return {"position": position, "task_sha256": digest(task), "window": task["window"],
            "task_family": task["family"], "width": task["width"], "search": search, "programs": rows,
            "root_evaluation": host.initial, "routing": host.routing,
            "charged_evaluations": search["represented_requests"] + 2,
            "solved": bool(successes), "new_solutions": new, "rediscovered": rediscovered,
            "archive_size_before": len(history)}


def binding(tasks, arm, tolerance, frozen):
    return {"schema": "mira-genesis-v32-observed-memory-binding-v1", "stream_sha256": bank.validate_stream(tasks),
            "arm": arm, "tolerance_milli": tolerance, "freeze_sha256": frozen,
            "policy_sha256": programs.PARENT_SHA256, "controller_sha256": digest_bytes(controller(arm).encode()),
            "caps": CAPS.__dict__, "root_evaluations_per_task": 1, "controller_calls_per_task": 1}


def run_stream(tasks, arm, tolerance, path, frozen, *, isolated=True, stop_after=None):
    identity = binding(tasks, arm, tolerance, frozen)
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
                                 "reserved_evaluations": MAX_EVALUATIONS}, expected_head=head)
        row = episode(task, position, history, arm, tolerance, isolated=isolated)
        archive.append("episode", row, expected_head=started)
        rows.append(row)
        history = history_from(rows)
    return rows, archive.read()[-1]["sha256"]


def verify_stream(tasks, arm, tolerance, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task, failure or incomplete stream")
    history, prefix = {}, []
    for position, (task, row) in enumerate(zip(tasks, rows)):
        evaluator = v31.Host(task, {}, "cold", isolated=False)
        for program in row["programs"]:
            expected = evaluator.evaluate(evaluator.row(program["genome"]))
            if digest(expected) != digest(program["evaluation"]):
                raise ValueError("Altered evaluator receipt")
        reconstructed = episode(task, position, history, arm, tolerance, isolated=isolated, replay=row)
        if digest(reconstructed) != digest(row):
            raise ValueError("Altered selector, policy, ancestry, costs or archive")
        prefix.append(row)
        history = history_from(prefix)
    return True


def summary(rows):
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows),
            "quality_milli": sum(row["search"]["best_quality_milli"] for row in rows),
            "evaluations": sum(row["charged_evaluations"] for row in rows),
            "new_solutions": sum(len(row["new_solutions"]) for row in rows),
            "routes": {target: sum(row["routing"]["target"] == target for row in rows)
                       for target in ("identity", "exploration", "generation", "scheduling")}}
