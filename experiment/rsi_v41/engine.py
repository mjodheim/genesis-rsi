"""Observed-quality archive selection with immutable evaluator-owned budgets."""
import json
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps
from experiment.rsi_v27.engine import development_functions, run_search
from experiment.rsi_v30 import meta
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v41 import bank, programs

ARMS = ("adaptive", "recency", "greedy", "cold")
CAPS = Caps(requests=10, rounds=8, parallelism=2, mutation_depth=3)
MAX_EVALUATIONS = 14
WORKER = ROOT / "experiment/rsi_v31/worker.py"


@lru_cache(maxsize=4096)
def functions(source):
    return development_functions(source, ())


def execute(genome, inputs, *, isolated=True):
    source = programs.render(genome)
    if not isolated:
        values = [functions(source)["transform"](value) for value in inputs]
    else:
        with tempfile.TemporaryDirectory(prefix="v41-transform-") as temporary:
            path = Path(temporary) / "program.py"
            path.write_text(source)
            run = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(path)],
                                 input=json.dumps({"inputs": inputs}), text=True, capture_output=True,
                                 cwd=temporary, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=3)
        if run.returncode:
            raise ValueError("Isolated pure candidate failed: " + run.stderr[-500:])
        values = json.loads(run.stdout)
    if (type(values) is not list or len(values) != len(inputs)
            or any(not programs.valid_value(genome["domain"], value) for value in values)):
        raise ValueError("Pure candidate output exceeds externally fixed type/resource contract")
    return values


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a):
        current = [i + 1]
        for j, y in enumerate(b):
            current.append(min(current[-1] + 1, previous[j + 1] + 1, previous[j] + (x != y)))
        previous = current
    return previous[-1]


def similarity(domain, actual, expected):
    if domain == "arithmetic":
        return 1000 // (1 + abs(actual - expected))
    if domain in ("text", "sequence"):
        return (max(len(actual), len(expected), 1) - edit_distance(actual, expected)) * 1000 // max(len(actual), len(expected), 1)
    keys = set(actual) | set(expected)
    return (sum(1000 // (1 + abs(actual[key] - expected[key])) for key in keys if key in actual and key in expected)
            // len(keys)) if keys else 1000


def history_from(episodes):
    """Rebuild observed memory plus a deterministic novelty-yield frontier."""
    history = {}
    for absolute_position, episode in enumerate(episodes):
        novel = set(episode["new_solving_behaviors"])
        for row in episode["programs"]:
            entry = history.setdefault(row["source_sha256"], {**row, "successes": 0, "last_success_position": -1,
                                                            "successful_root_qualities": [], "observations": 0,
                                                            "novel_successes": 0, "last_novel_position": -1,
                                                            "child_sources": set(), "novel_child_behaviors": set()})
            entry["observations"] += 1
            if row["quality_milli"] == 1000:
                entry["successes"] += 1
                entry["last_success_position"] = absolute_position
                entry["successful_root_qualities"].append(episode["root_evaluation"]["quality_milli"])
                if row["behavior_witness_sha256"] in novel:
                    entry["novel_successes"] += 1
                    entry["last_novel_position"] = absolute_position
    for episode in episodes:
        novel = set(episode["new_solving_behaviors"])
        for row in episode["programs"]:
            parent = row.get("search_parent_source_sha256")
            child = row["source_sha256"]
            if parent in history and parent != child:
                history[parent]["child_sources"].add(child)
                if row["quality_milli"] == 1000 and row["behavior_witness_sha256"] in novel:
                    history[parent]["novel_child_behaviors"].add(row["behavior_witness_sha256"])
    return history

class Host:
    forbidden_tokens = []

    def __init__(self, task, history, arm, *, isolated=True, receipts=None, stagnating=False):
        bank.validate_task(task)
        if arm not in ARMS:
            raise ValueError("Unknown governed retention arm")
        self.task, self.receipts, self.isolated, self.stagnating = task, receipts, isolated, stagnating
        champions = [row for row in history.values() if row["successes"] and row["genome"]["domain"] == task["domain"]]
        self.root_genome = self.identity_genome = programs.identity(task["domain"])
        self.initial = self.identity_evaluation = self.evaluate(self.row(self.identity_genome))
        quality = self.initial["quality_milli"]
        compatibility = sorted(champions, key=lambda row: (
            min(abs(quality - old) for old in row["successful_root_qualities"]),
            -row["last_success_position"], -row["successes"], row["source_sha256"]))
        if arm in ("recency", "greedy"):
            compatibility = sorted(champions, key=lambda row: (
                -row["last_success_position"], -row["successes"], row["source_sha256"]))
        memory, roles = [], {}
        if arm == "adaptive":
            distinct, observed = [], set()
            for row in compatibility:
                signature = row["behavior_witness_sha256"]
                if signature not in observed:
                    distinct.append(row)
                    observed.add(signature)
            compatibility = distinct
            if compatibility:
                memory.append(compatibility[0])
                roles[compatibility[0]["source_sha256"]] = "compatibility"
            if stagnating:
                frontier = sorted(champions, key=lambda row: (
                    -((row["novel_successes"] + len(row["novel_child_behaviors"])) * 1000
                      // max(1, len(row["child_sources"]))),
                    len(row["child_sources"]),
                    -row["last_novel_position"],
                    min(abs(quality - old) for old in row["successful_root_qualities"]),
                    -row["last_success_position"], row["source_sha256"]))
                used_behaviors = {row["behavior_witness_sha256"] for row in memory}
                for row in frontier:
                    if row["source_sha256"] not in roles and row["behavior_witness_sha256"] not in used_behaviors:
                        memory.append(row)
                        roles[row["source_sha256"]] = "novelty-frontier"
                        break
            else:
                for row in compatibility[1:]:
                    if row["source_sha256"] not in roles:
                        memory.append(row)
                        roles[row["source_sha256"]] = "compatibility-secondary"
                        break
            for row in compatibility:
                if len(memory) == 2:
                    break
                if row["source_sha256"] not in roles:
                    memory.append(row)
                    roles[row["source_sha256"]] = "compatibility-fill"
        elif arm != "cold":
            memory = compatibility[:1 if arm == "greedy" else 2]
            roles = {row["source_sha256"]: arm for row in memory}
        # V39 changes selection only: two paid probes, the same search cap and the
        # same evaluator remain. One adaptive slot exploits compatibility; the
        # second explores a successful but under-exhausted novelty-producing frontier.
        self.memory_sources = {row["source_sha256"] for row in memory}
        self.memory_roles = roles
        candidates = [row["genome"] for row in memory]
        candidates.extend(programs.neighbors(self.identity_genome))
        self.probes = []
        self.probed = {programs.descriptor(self.identity_genome)["source_sha256"]}
        for genome in candidates:
            row = self.row(genome)
            if row["source_sha256"] in self.probed:
                continue
            self.probed.add(row["source_sha256"])
            self.probes.append({**row, "evaluation": self.evaluate(row)})
            if len(self.probes) == 2:
                break
        if arm == "adaptive":
            best = max(enumerate(self.probes), key=lambda pair: (
                pair[1]["evaluation"]["quality_milli"],
                int(self.memory_roles.get(pair[1]["source_sha256"]) == "novelty-frontier"),
                -pair[0]))[1]
        else:
            best = max(enumerate(self.probes), key=lambda pair: (pair[1]["evaluation"]["quality_milli"], -pair[0]))[1]
        gain = best["evaluation"]["quality_milli"] - quality
        frontier_tie = (arm == "adaptive" and self.stagnating and gain == 0
                        and self.memory_roles.get(best["source_sha256"]) == "novelty-frontier")
        diagnostics = {"exploration": int(gain > 0 or frontier_tie),
                       "generation": int(gain < 0 or (gain == 0 and not frontier_tie)), "scheduling": 0}
        selected = meta.select(programs.parent(), diagnostics, isolated=isolated)
        if selected == "exploration":
            self.root_genome, self.initial = best["candidate"], best["evaluation"]
        self.routing = {"controller_sha256": programs.PARENT_SHA256, "controller_calls": 1, "probe_evaluations": 2,
                        "diagnostics": diagnostics, "target": selected, "observed_probe_gain_milli": gain,
                        "used_probe_root": selected == "exploration", "frontier_tie_break": frontier_tie,
                        "stagnation_trigger": self.stagnating,
                        "memory_policy": "conditional_stagnation4_frontier_v1",
                        "probe_source_sha256": [row["source_sha256"] for row in self.probes],
                        "probe_roles": [self.memory_roles.get(row["source_sha256"], "local") for row in self.probes],
                        "archive_probe_sources": [row["source_sha256"] for row in self.probes if row["source_sha256"] in self.memory_sources],
                        "chosen_root_sha256": programs.descriptor(self.root_genome)["source_sha256"]}

    def row(self, genome):
        return {"candidate": programs.validate(genome), **programs.descriptor(genome)}

    def root(self):
        return {**self.row(self.root_genome), "quality_milli": self.initial["quality_milli"]}

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        return tuple(self.row(child) for child in programs.neighbors(genome)
                     if programs.descriptor(child)["source_sha256"] not in self.probed)

    def action(self, row):
        return {"family": "pure-pipeline-program", "structure_sha256": row["structure_sha256"], "target_axes": row["target_axes"]}

    def evaluate(self, row):
        sha = row["source_sha256"]
        if self.receipts is not None:
            if sha not in self.receipts:
                raise ValueError("Replay requested unobserved work")
            return self.receipts[sha]
        domain, inputs = self.task["domain"], self.task["inputs"]
        combined = [*inputs, *programs.WITNESSES[domain]]
        values = execute(row["candidate"], combined, isolated=self.isolated)
        expected = execute(self.task["target"], inputs, isolated=False)
        actual = values[:len(inputs)]
        quality = sum(similarity(domain, a, b) for a, b in zip(actual, expected)) // len(inputs)
        # Integer rounding never creates a perfect solution from partial matches.
        if quality == 1000 and actual != expected:
            raise ValueError("Evaluator rounded a partial solution into perfection")
        return {"accepted": True, "source_sha256": sha, "quality_milli": quality,
                "output_sha256": digest(actual), "behavior_witness_sha256": digest([domain, values[len(inputs):]]),
                "evaluator_task_sha256": digest(self.task), "task_cases": len(inputs),
                "public_behavior_witnesses": len(programs.WITNESSES[domain])}


def episode(task, position, prefix, arm, *, isolated=True, replay=None):
    history = history_from(prefix)
    receipts = None if replay is None else {row["source_sha256"]: row["evaluation"] for row in replay["programs"]}
    recent_same_domain = [row for row in reversed(prefix) if row["domain"] == task["domain"]][:4]
    stagnating = (arm == "adaptive" and len(recent_same_domain) == 4
                  and not any(row["new_solving_behaviors"] for row in recent_same_domain))
    host = Host(task, history, arm, isolated=isolated, receipts=receipts, stagnating=stagnating)
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)
    rows = {}
    identity_sha = programs.descriptor(host.identity_genome)["source_sha256"]
    def retain(genome, evaluation, parent_sha, phase):
        sha = programs.descriptor(genome)["source_sha256"]
        if evaluation["source_sha256"] != sha:
            raise ValueError("Substituted pure program")
        origin = history.get(sha)
        rows.setdefault(sha, {"source_sha256": sha, "genome": genome, "phase": phase,
            "parent_source_sha256": origin["parent_source_sha256"] if origin else parent_sha,
            "search_parent_source_sha256": parent_sha, "evaluation": evaluation, "quality_milli": evaluation["quality_milli"],
            "behavior_witness_sha256": evaluation["behavior_witness_sha256"], "previously_observed": origin is not None})
    retain(host.identity_genome, host.identity_evaluation, None, "identity")
    for row in host.probes:
        retain(row["candidate"], row["evaluation"], identity_sha, "probe")
    for key, row in search["nodes"].items():
        parent_key = row["parent_node_id"]
        retain(row["candidate"], host.initial if key == "root" else row["evaluation"],
               search["nodes"][parent_key]["source_sha256"] if parent_key else identity_sha, "search")
    prior_behaviors = {row["behavior_witness_sha256"] for row in history.values()}
    successes = [row for row in rows.values() if row["quality_milli"] == 1000]
    novel_behaviors = sorted({row["behavior_witness_sha256"] for row in successes} - prior_behaviors)
    return {"position": position, "absolute_position": len(prefix), "task_sha256": digest(task), "window": task["window"],
            "domain": task["domain"], "search": search, "programs": list(rows.values()), "root_evaluation": host.identity_evaluation,
            "routing": host.routing, "charged_evaluations": search["represented_requests"] + 4,
            "best_quality_milli": max(row["quality_milli"] for row in rows.values()), "solved": bool(successes),
            "new_solving_behaviors": novel_behaviors,
            "new_solving_sources": [row["source_sha256"] for row in successes if row["source_sha256"] not in history],
            "rediscovered_successes": [row["source_sha256"] for row in successes if row["source_sha256"] in history
                and 0 <= history[row["source_sha256"]]["last_success_position"] < len(prefix) - 1],
            "archive_source_size_before": len(history), "archive_behavior_size_before": len(prior_behaviors)}


def binding(tasks, arm, frozen, previous_receipt, prefix):
    return {"schema": "mira-genesis-v41-development-binding-v1", "stream_sha256": bank.validate_stream(tasks), "arm": arm,
            "freeze_sha256": frozen, "previous_receipt_sha256": previous_receipt, "history_sha256": digest(prefix),
            "policy_sha256": programs.PARENT_SHA256, "caps": CAPS.__dict__, "maximum_task_evaluations": MAX_EVALUATIONS}


def run_stream(tasks, arm, path, frozen, previous_receipt, prefix, *, isolated=True, stop_after=None):
    identity = binding(tasks, arm, frozen, previous_receipt, prefix)
    archive = Archive(path, identity, create=not Path(path).exists())
    rows = archive.episodes()
    if len(rows) > len(tasks) or any(row["task_sha256"] != digest(task) for row, task in zip(rows, tasks)):
        raise ValueError("Checkpoint is not an exact epoch prefix")
    limit = len(tasks) if stop_after is None else min(stop_after, len(tasks))
    for position in range(len(rows), limit):
        task = tasks[position]
        started = archive.append("start", {"position": position, "task_sha256": digest(task), "reserved_evaluations": MAX_EVALUATIONS},
                                 expected_head=archive.read()[-1]["sha256"])
        row = episode(task, position, [*prefix, *rows], arm, isolated=isolated)
        archive.append("episode", row, expected_head=started)
        rows.append(row)
    return rows, archive.read()[-1]["sha256"]


def verify_stream(tasks, arm, prefix, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task or incomplete epoch")
    history = list(prefix)
    for position, (task, row) in enumerate(zip(tasks, rows)):
        evaluator = Host(task, {}, "cold", isolated=False)
        for program in row["programs"]:
            if digest(evaluator.evaluate(evaluator.row(program["genome"]))) != digest(program["evaluation"]):
                raise ValueError("Altered task or witness evaluator receipt")
        expected = episode(task, position, history, arm, isolated=isolated, replay=row)
        if digest(expected) != digest(row):
            raise ValueError("Altered archive, probe, policy, ancestry, cost or recovery")
        history.append(row)
    return True


def summary(rows, prefix=()):
    previous = history_from(prefix)
    current = history_from([*prefix, *rows])
    cost = sum(row["charged_evaluations"] for row in rows)
    new = sum(len(row["new_solving_behaviors"]) for row in rows)
    parents = {}
    for sha, row in current.items():
        if row["parent_source_sha256"] is not None:
            parents.setdefault(row["parent_source_sha256"], set()).add(sha)
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows),
            "quality_milli": sum(row["best_quality_milli"] for row in rows), "evaluations": cost,
            "new_solving_behaviors": new, "new_solving_behaviors_per_1000_evaluations": new * 1000 / cost if cost else 0,
            "archive_source_size": len(current), "archive_source_size_before": len(previous),
            "archive_behavior_size": len({row["behavior_witness_sha256"] for row in current.values()}),
            "archive_behavior_size_before": len({row["behavior_witness_sha256"] for row in previous.values()}),
            "branching_parents": sum(len(children) > 1 for children in parents.values()),
            "rediscovered_successes": sum(len(row["rediscovered_successes"]) for row in rows),
            "task_domains_seen": sorted({row["domain"] for row in [*prefix, *rows]}),
            "probe_roots": sum(row["routing"]["used_probe_root"] for row in rows)}
