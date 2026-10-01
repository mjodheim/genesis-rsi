"""Charged current-task probes and observed-quality root selection around G7."""
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import family, meta
from experiment.rsi_v31 import bank, engine as v31, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v32.engine import history_from

CAPS = Caps(requests=10, rounds=8, parallelism=2, mutation_depth=3)
ARMS = ("adaptive", "selector_ablation", "recency", "greedy", "cold")
MARGINS = (0, 25, 50, 100)
MAX_EVALUATIONS = 14


def controller(arm):
    if arm not in ARMS:
        raise ValueError("Unknown active-probe arm")
    if arm == "adaptive":
        return programs.parent()
    if arm == "selector_ablation":
        return family.parent()
    return family.fixed("generation" if arm == "cold" else "exploration")


class Host(v31.Host):
    def __init__(self, task, history, arm, margin, *, isolated=True, receipts=None):
        if type(margin) is not int or margin not in MARGINS:
            raise ValueError("Unknown predeclared gain margin")
        super().__init__(task, history, "archive", isolated=isolated, receipts=receipts)
        self.identity_genome, self.identity_evaluation = self.root_genome, self.initial
        quality = self.initial["quality_milli"]
        champions = [row for row in self.history.values() if row["successes"]]
        ranked = sorted(champions, key=lambda row: (
            min(abs(quality - old) for old in row["successful_root_qualities"]),
            -row["last_success_position"], -row["successes"], row["source_sha256"]))
        if arm in ("recency", "greedy"):
            ranked = sorted(champions, key=lambda row: (
                -row["last_success_position"], -row["successes"], row["source_sha256"]))
        memories = ranked[:1 if arm == "greedy" else 2] if arm != "cold" else []
        # Exactly two distinct paid probes for every arm, including empty archives.
        candidates = [row["genome"] for row in memories]
        candidates.extend(programs.neighbors(self.identity_genome))
        self.probes, seen = [], {programs.descriptor(self.identity_genome)["source_sha256"]}
        memory_hashes = {row["source_sha256"] for row in memories}
        for genome in candidates:
            row = self.row(genome)
            sha = row["source_sha256"]
            if sha in seen:
                continue
            seen.add(sha)
            self.probes.append({**row, "evaluation": self.evaluate(row), "from_archive": sha in memory_hashes})
            if len(self.probes) == 2:
                break
        best = max(self.probes, key=lambda row: (row["evaluation"]["quality_milli"], -self.probes.index(row)))
        gain = best["evaluation"]["quality_milli"] - quality
        compatible = gain > margin
        diagnostics = {"exploration": int(compatible), "generation": int(not compatible), "scheduling": 0}
        target = meta.select(controller(arm), diagnostics, isolated=isolated)
        # G6 without the acquired selector defaults to identity: forced probe root.
        use_probe = target in ("identity", "exploration")
        # Cold's two local probes are useful observed work too, under the same cap.
        if arm == "cold":
            use_probe = gain > 0
        if use_probe:
            self.root_genome, self.initial = best["candidate"], best["evaluation"]
        self.probe_hashes = seen
        self.routing = {"controller_sha256": digest_bytes(controller(arm).encode()),
                        "diagnostics": diagnostics, "observed_probe_gain_milli": gain,
                        "target": target, "chosen_root_sha256": programs.descriptor(self.root_genome)["source_sha256"],
                        "used_probe_root": use_probe, "probe_source_sha256": [row["source_sha256"] for row in self.probes],
                        "archive_probe_sources": [row["source_sha256"] for row in self.probes if row["from_archive"]],
                        "controller_calls": 1, "probe_evaluations": 2}

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        return tuple(self.row(child) for child in programs.neighbors(genome)
                     if programs.descriptor(child)["source_sha256"] not in self.probe_hashes)


def episode(task, position, history, arm, margin, *, isolated=True, replay=None):
    receipts = None if replay is None else {row["source_sha256"]: row["evaluation"] for row in replay["programs"]}
    host = Host(task, history, arm, margin, isolated=isolated, receipts=receipts)
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)
    rows = {}
    identity_sha = programs.descriptor(host.identity_genome)["source_sha256"]

    def retain(genome, evaluation, parent_sha, phase):
        sha = programs.descriptor(genome)["source_sha256"]
        if evaluation["source_sha256"] != sha:
            raise ValueError("Substituted probed or searched source")
        origin = history.get(sha)
        rows.setdefault(sha, {"source_sha256": sha, "genome": genome, "semantic_sha256": digest(genome),
            "parent_source_sha256": origin["parent_source_sha256"] if origin else parent_sha,
            "search_parent_source_sha256": parent_sha, "evaluation": evaluation,
            "quality_milli": evaluation["quality_milli"], "previously_observed": origin is not None, "phase": phase})

    retain(host.identity_genome, host.identity_evaluation, None, "identity")
    for probe in host.probes:
        retain(probe["candidate"], probe["evaluation"], identity_sha, "probe")
    for key, node in search["nodes"].items():
        parent_key = node["parent_node_id"]
        retain(node["candidate"], host.initial if key == "root" else node["evaluation"],
               search["nodes"][parent_key]["source_sha256"] if parent_key else identity_sha, "search")
    successes = [row for row in rows.values() if row["quality_milli"] == 1000]
    return {"position": position, "task_sha256": digest(task), "window": task["window"],
            "task_family": task["family"], "width": task["width"], "search": search, "programs": list(rows.values()),
            "root_evaluation": host.identity_evaluation, "routing": host.routing,
            "best_quality_milli": max(row["quality_milli"] for row in rows.values()),
            "charged_evaluations": search["represented_requests"] + 4,
            "solved": bool(successes), "new_solutions": [row["source_sha256"] for row in successes
                                                          if row["source_sha256"] not in history],
            "rediscovered": [row["source_sha256"] for row in successes if row["source_sha256"] in history
                              and history[row["source_sha256"]]["last_success_position"] < position - 1],
            "archive_size_before": len(history)}


def binding(tasks, arm, margin, frozen):
    return {"schema": "mira-genesis-v33-active-memory-binding-v1", "stream_sha256": bank.validate_stream(tasks),
            "arm": arm, "margin_milli": margin, "freeze_sha256": frozen,
            "policy_sha256": programs.PARENT_SHA256, "controller_sha256": digest_bytes(controller(arm).encode()),
            "caps": CAPS.__dict__, "root_evaluations_per_task": 1, "probe_evaluations_per_task": 2,
            "controller_calls_per_task": 1}


def run_stream(tasks, arm, margin, path, frozen, *, isolated=True, stop_after=None):
    identity = binding(tasks, arm, margin, frozen)
    archive = Archive(path, identity, create=not Path(path).exists())
    rows = archive.episodes()
    if len(rows) > len(tasks) or any(row["task_sha256"] != digest(task) for row, task in zip(rows, tasks)):
        raise ValueError("Checkpoint is not an exact stream prefix")
    history = history_from(rows)
    limit = len(tasks) if stop_after is None else min(stop_after, len(tasks))
    for position in range(len(rows), limit):
        task = tasks[position]
        started = archive.append("start", {"position": position, "task_sha256": digest(task),
                                 "reserved_evaluations": MAX_EVALUATIONS}, expected_head=archive.read()[-1]["sha256"])
        row = episode(task, position, history, arm, margin, isolated=isolated)
        archive.append("episode", row, expected_head=started)
        rows.append(row)
        history = history_from(rows)
    return rows, archive.read()[-1]["sha256"]


def verify_stream(tasks, arm, margin, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task, failure or incomplete stream")
    prefix = []
    for position, (task, row) in enumerate(zip(tasks, rows)):
        evaluator = v31.Host(task, {}, "cold", isolated=False)
        for program in row["programs"]:
            if digest(evaluator.evaluate(evaluator.row(program["genome"]))) != digest(program["evaluation"]):
                raise ValueError("Altered evaluator receipt")
        reconstructed = episode(task, position, history_from(prefix), arm, margin, isolated=isolated, replay=row)
        if digest(reconstructed) != digest(row):
            raise ValueError("Altered probes, routing, policy, ancestry, costs or archive")
        prefix.append(row)
    return True


def summary(rows):
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows),
            "quality_milli": sum(row["best_quality_milli"] for row in rows),
            "evaluations": sum(row["charged_evaluations"] for row in rows),
            "new_solutions": sum(len(row["new_solutions"]) for row in rows),
            "probe_roots": sum(row["routing"]["used_probe_root"] for row in rows),
            "identity_roots": sum(not row["routing"]["used_probe_root"] for row in rows)}
