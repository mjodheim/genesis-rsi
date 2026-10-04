"""Matched-budget probe retrieval on consumed data, preserving the qualified G7."""
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank, engine as v31, programs
from experiment.rsi_v31.archive import Archive

CAPS = Caps(requests=10, rounds=8, parallelism=2, mutation_depth=3)
ARMS = ("probe", "scalar", "probe_ablation", "cold")
MAX_EVALUATIONS = CAPS.requests + 4


def controller(arm):
    if arm not in ARMS:
        raise ValueError("Unknown V33 development arm")
    if arm == "probe_ablation":
        return family.parent()
    if arm == "cold":
        return family.fixed("generation")
    return programs.parent()


def probe_genomes(width):
    root = programs.identity(width)
    return (root, {**root, "mask": 1}, {**root, "rotation": 1})


def history_from(episodes):
    history = v31.history_from(episodes)
    for entry in history.values():
        entry["successful_fingerprints"] = []
    for episode in episodes:
        for row in episode["programs"]:
            if row["quality_milli"] == 1000:
                history[row["source_sha256"]]["successful_fingerprints"].append(episode["fingerprint"])
    return history


def distance(current, previous, arm):
    dimensions = 1 if arm == "scalar" else 3
    return sum(abs(current[i] - previous[i]) for i in range(dimensions))


class Host(v31.Host):
    def __init__(self, task, history, arm, *, isolated=True, receipts=None):
        controller(arm)  # reject an invalid arm before any evaluation
        super().__init__(task, history, "archive", isolated=isolated, receipts=receipts)
        self.arm = arm
        self.probes = [self.initial] + [self.evaluate(self.row(genome))
                                      for genome in probe_genomes(task["width"])[1:]]
        self.fingerprint = [row["quality_milli"] for row in self.probes]
        champions = [entry for entry in self.history.values() if entry["successes"]]
        def nearest(entry):
            return min(distance(self.fingerprint, old, arm) for old in entry["successful_fingerprints"])
        ranked = sorted(champions, key=lambda entry: (
            nearest(entry), -entry["last_success_position"], -entry["successes"], entry["source_sha256"]))
        nearest_distance = nearest(ranked[0]) if ranked else None
        threshold = 25 if arm == "scalar" else 75
        compatible = nearest_distance is not None and nearest_distance <= threshold
        diagnostics = {"exploration": int(compatible), "generation": int(not compatible), "scheduling": 0}
        target = meta.select(controller(arm), diagnostics, isolated=isolated)
        count = {"identity": 2, "exploration": 2, "generation": 0}[target]
        self.retrieved = ranked[:count]
        self.routing = {"controller_sha256": digest_bytes(controller(arm).encode()),
                        "diagnostics": diagnostics, "target": target,
                        "nearest_distance": nearest_distance, "threshold": threshold,
                        "retrieved_sources": [entry["source_sha256"] for entry in self.retrieved],
                        "controller_calls": 1}

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        rows = ([self.row(entry["genome"]) for entry in self.retrieved]
                if genome == self.root_genome else [])
        rows.extend(self.row(child) for child in programs.neighbors(genome))
        unique = {}
        for row in rows:
            unique.setdefault(row["source_sha256"], row)
        return tuple(unique.values())


def episode(task, position, history, arm, *, isolated=True, replay=None):
    receipts = None
    if replay is not None:
        receipts = {row["source_sha256"]: row["evaluation"] for row in replay["programs"]}
        for row in replay["probes"]:
            old = receipts.setdefault(row["source_sha256"], row)
            if old != row:
                raise ValueError("Conflicting probe and search receipt")
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
        parent_id = node["parent_node_id"]
        parent_sha = search["nodes"][parent_id]["source_sha256"] if parent_id else None
        rows.append({"source_sha256": sha, "genome": genome, "semantic_sha256": digest(genome),
                     "parent_source_sha256": origin["parent_source_sha256"] if origin else parent_sha,
                     "search_parent_source_sha256": parent_sha, "evaluation": evaluation,
                     "quality_milli": evaluation["quality_milli"], "previously_observed": origin is not None})
    successes = [row for row in rows if row["quality_milli"] == 1000]
    retrieved = set(host.routing["retrieved_sources"])
    measured = [row for row in rows if row["source_sha256"] in retrieved
                and row["source_sha256"] != host.initial["source_sha256"]]
    return {"position": position, "task_sha256": digest(task), "window": task["window"],
            "task_family": task["family"], "width": task["width"], "search": search, "programs": rows,
            "root_evaluation": host.initial, "probes": host.probes, "fingerprint": host.fingerprint,
            "routing": host.routing, "charged_evaluations": search["represented_requests"] + 4,
            "solved": bool(successes),
            "new_solutions": [row["source_sha256"] for row in successes if row["source_sha256"] not in history],
            "rediscovered": [row["source_sha256"] for row in successes if row["source_sha256"] in history
                             and history[row["source_sha256"]]["last_success_position"] < position - 1],
            "retrieval_evaluated": len(measured),
            "retrieval_worse_than_root": sum(row["quality_milli"] < host.initial["quality_milli"] for row in measured),
            "archive_size_before": len(history)}


def binding(tasks, arm, apparatus, isolated):
    return {"schema": "mira-genesis-v33-consumed-development-binding-v1",
            "stream_sha256": bank.validate_stream(tasks), "arm": arm, "apparatus_sha256": apparatus,
            "policy_sha256": programs.PARENT_SHA256, "controller_sha256": digest_bytes(controller(arm).encode()),
            "caps": CAPS.__dict__, "isolated": isolated, "scope": "CONSUMED_DEVELOPMENT_ONLY"}


def run_stream(tasks, arm, path, apparatus, *, isolated=True, stop_after=None):
    archive = Archive(path, binding(tasks, arm, apparatus, isolated), create=not Path(path).exists())
    rows = archive.episodes()
    if len(rows) > len(tasks) or any(row["task_sha256"] != digest(task) for row, task in zip(rows, tasks)):
        raise ValueError("Checkpoint is not an exact stream prefix")
    verify_stream(tasks[:len(rows)], arm, rows, isolated=isolated)
    limit = len(tasks) if stop_after is None else min(stop_after, len(tasks))
    history = history_from(rows)
    for position in range(len(rows), limit):
        started = archive.append("start", {"position": position, "task_sha256": digest(tasks[position]),
                                 "reserved_evaluations": MAX_EVALUATIONS}, expected_head=archive.read()[-1]["sha256"])
        row = episode(tasks[position], position, history, arm, isolated=isolated)
        archive.append("episode", row, expected_head=started)
        rows.append(row)
        history = history_from(rows)
    return rows, archive.read()[-1]["sha256"]


def verify_stream(tasks, arm, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task, negative or incomplete stream")
    prefix = []
    for position, (task, row) in enumerate(zip(tasks, rows)):
        evaluator = v31.Host(task, {}, "cold", isolated=False)
        expected_probes = [evaluator.evaluate(evaluator.row(genome)) for genome in probe_genomes(task["width"])]
        if expected_probes != row["probes"]:
            raise ValueError("Altered probe receipt")
        for program in row["programs"]:
            if evaluator.evaluate(evaluator.row(program["genome"])) != program["evaluation"]:
                raise ValueError("Altered evaluator receipt")
        reconstructed = episode(task, position, history_from(prefix), arm, isolated=isolated, replay=row)
        if digest(reconstructed) != digest(row):
            raise ValueError("Altered route, policy, ancestry, cost or fingerprint")
        prefix.append(row)
    return True


def summary(rows):
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows),
            "evaluations": sum(row["charged_evaluations"] for row in rows),
            "new_solutions": sum(len(row["new_solutions"]) for row in rows),
            "retrieval_evaluated": sum(row["retrieval_evaluated"] for row in rows),
            "retrieval_worse_than_root": sum(row["retrieval_worse_than_root"] for row in rows),
            "windows": v31.windows(rows)}
