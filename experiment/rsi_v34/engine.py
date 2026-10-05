"""Count and retain every paid diagnostic probe without rewriting V33."""
from pathlib import Path

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v31 import engine as evaluator, programs
from experiment.rsi_v31.archive import Archive
from experiment.rsi_v33 import engine as previous

CAPS, ARMS, MAX_EVALUATIONS = previous.CAPS, previous.ARMS, previous.MAX_EVALUATIONS
controller, probe_genomes = previous.controller, previous.probe_genomes
history_from, summary = previous.history_from, previous.summary


def episode(task, position, history, arm, *, isolated=True, replay=None):
    row = previous.episode(task, position, history, arm, isolated=isolated, replay=replay)
    row["solved_by_search"] = row["solved"]
    row["solved_by_probes"] = any(probe["quality_milli"] == 1000 for probe in row["probes"])
    root_sha = row["root_evaluation"]["source_sha256"]
    by_sha = {program["source_sha256"]: program for program in row["programs"]}
    probe_sources = {probe["source_sha256"] for probe in row["probes"]}
    for program in row["programs"]:
        program["evaluation_origin"] = "probe_and_search" if program["source_sha256"] in probe_sources else "search"
    for genome, receipt in zip(probe_genomes(task["width"]), row["probes"]):
        sha = receipt["source_sha256"]
        if programs.descriptor(genome)["source_sha256"] != sha:
            raise ValueError("Substituted probe source")
        if sha in by_sha:
            if by_sha[sha]["evaluation"] != receipt:
                raise ValueError("Conflicting probe and search receipt")
            continue
        origin = history.get(sha)
        program = {"source_sha256": sha, "genome": genome, "semantic_sha256": digest(genome),
                   "parent_source_sha256": origin["parent_source_sha256"] if origin else root_sha,
                   "search_parent_source_sha256": root_sha, "evaluation": receipt,
                   "quality_milli": receipt["quality_milli"], "previously_observed": origin is not None,
                   "evaluation_origin": "probe"}
        row["programs"].append(program)
        by_sha[sha] = program
    successes = [program for program in row["programs"] if program["quality_milli"] == 1000]
    row["solved"] = bool(successes)
    row["new_solutions"] = [program["source_sha256"] for program in successes
                            if program["source_sha256"] not in history]
    row["rediscovered"] = [program["source_sha256"] for program in successes
                           if program["source_sha256"] in history
                           and history[program["source_sha256"]]["last_success_position"] < position - 1]
    row["charged_evaluations"] = len(row["probes"]) + row["search"]["represented_requests"] + 1
    return row


def binding(tasks, arm, apparatus, isolated):
    value = previous.binding(tasks, arm, apparatus, isolated)
    return {**value, "schema": "mira-genesis-v34-complete-probe-development-binding-v1",
            "all_evaluated_probes_retained": True, "success_scope": "ALL_CHARGED_CANDIDATES"}


def verify_stream(tasks, arm, rows, *, isolated=True):
    if len(tasks) != len(rows):
        raise ValueError("Omitted task, negative or incomplete stream")
    prefix = []
    for position, (task, row) in enumerate(zip(tasks, rows)):
        host = evaluator.Host(task, {}, "cold", isolated=False)
        expected_probes = [host.evaluate(host.row(genome)) for genome in probe_genomes(task["width"])]
        if row["probes"] != expected_probes:
            raise ValueError("Altered probe receipt")
        if len(row["programs"]) != len({p["source_sha256"] for p in row["programs"]}):
            raise ValueError("Duplicated archive program")
        for program in row["programs"]:
            if host.evaluate(host.row(program["genome"])) != program["evaluation"]:
                raise ValueError("Altered evaluator receipt")
        rebuilt = episode(task, position, history_from(prefix), arm, isolated=isolated, replay=row)
        if digest(rebuilt) != digest(row):
            raise ValueError("Altered probe retention, successes, route, cost or ancestry")
        prefix.append(row)
    return True


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
