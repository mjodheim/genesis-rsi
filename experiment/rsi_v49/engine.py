"""Paid whole-pipeline search; construction has no target or output oracle."""
import itertools

from experiment.rsi_v25.commitments import digest
from experiment.rsi_v49 import native

ARMS = ("archive", "archive-ancestor", "greedy", "cold")


def cap(task):
    return 26


def history_from(rows, previous=None):
    history = {key: dict(value) for key, value in (previous or {}).items()}
    for row in rows:
        for program in row["programs"]:
            entry = history.setdefault(program["source_sha256"], {
                **program, "successes": 0, "first_success_position": -1, "last_success_position": -1})
            if program["evaluation"]["accepted"] and program["evaluation"]["quality_milli"] == 1000:
                if not entry["successes"]:
                    entry["first_success_position"] = row["global_position"]
                entry["successes"] += 1
                entry["last_success_position"] = row["global_position"]
    return history


def frontiers(history, arm, slots):
    values = [e for e in history.values() if e["successes"] and len(e["genome"]["ops"]) <= slots]
    values.sort(key=lambda e: (-len(e["genome"]["ops"]), -e["last_success_position"], e["source_sha256"]))
    if arm == "cold":
        return []
    if arm == "greedy":
        return sorted(values, key=lambda e: (-e["last_success_position"], e["source_sha256"]))[:1]
    # Archive and latest-tool ablation receive identical paid retrieval.
    return values[:4]


def tools(history, domain, arm, slots):
    width = max(1, slots // (4 if arm == "archive-ancestor" else 2))
    if arm == "cold" or slots == 1:
        return 1, [{"ops": [op], "donor_source_sha256": None, "acquired_position": None} for op in range(1, 5)]
    values = [entry for entry in history.values() if entry["successes"]]
    if arm == "greedy":
        values.sort(key=lambda e: (-e["last_success_position"], e["source_sha256"]))
        values = values[:1]
    values = [e for e in values if len(e["genome"]["ops"]) == width]
    values.sort(key=lambda e: (tuple(e["genome"]["ops"]), e["first_success_position"], e["source_sha256"]))
    found = {}
    for entry in values:
        found.setdefault(tuple(entry["genome"]["ops"]), {"ops": entry["genome"]["ops"],
            "donor_source_sha256": entry["source_sha256"], "acquired_position": entry["first_success_position"]})
    if not found:
        return 1, [{"ops": [op], "donor_source_sha256": None, "acquired_position": None} for op in range(1, 5)]
    return width, list(found.values())[:4]


def episode(task, global_position, history, arm, *, isolated=True, replay=None):
    if arm not in ARMS:
        raise ValueError("Unknown coupled native arm")
    # Only these public fields and paid scalar scores enter proposal construction.
    domain, slots = task["domain"], task["slots"]
    calls = []

    def exact(row):
        return row["evaluation"]["accepted"] and row["evaluation"]["quality_milli"] == 1000

    def evaluate(value, construction):
        if len(calls) >= cap(task) - int(construction["kind"] != "verify"):
            raise ValueError("Unpaid request outside fixed external cap")
        value = native.validate(value)
        if replay is None:
            evaluation = native.evaluate(task, value, isolated=isolated)
        else:
            if len(calls) >= len(replay["calls"]):
                raise ValueError("Replay requested an unobserved call")
            old = replay["calls"][len(calls)]
            if old["genome"] != value or old["construction"] != construction:
                raise ValueError("Altered proposal, ancestry or donor acquisition")
            evaluation = old["evaluation"]
        row = {"genome": value, "construction": construction, "evaluation": evaluation}
        calls.append(row)
        return row

    root = evaluate(native.genome(domain, []), {"kind": "root"})
    observations = [root]
    for entry in frontiers(history, arm, slots):
        if exact(observations[-1]):
            break
        observations.append(evaluate(entry["genome"], {"kind": "screen"}))
    selected = min(observations, key=lambda r: (-r["evaluation"]["quality_milli"], len(r["genome"]["ops"]), r["evaluation"]["source_sha256"]))
    width, learned = tools(history, domain, arm, slots)
    found = next((r for r in observations if exact(r)), None)
    stop = "screen_exact" if found else "external_fixed_budget"
    if found is None:
        for product in itertools.product(learned, repeat=slots // width):
            if len(calls) >= cap(task) - 1:
                break
            value = native.genome(domain, [op for donor in product for op in donor["ops"]])
            row = evaluate(value, {"kind": "learned-compose", "parent_source_sha256": selected["evaluation"]["source_sha256"],
                "donors": list(product), "macro_width": width})
            if exact(row):
                found, stop = row, "composition_exact"
                break
        else:
            stop = "proposal_population_exhausted"
    if found:
        confirmation = evaluate(found["genome"], {"kind": "verify"})
        if confirmation["evaluation"] != found["evaluation"]:
            raise ValueError("Whole native pipeline failed exact paid confirmation")
    if replay is not None and len(calls) != len(replay["calls"]):
        raise ValueError("Omitted paid call")
    programs = {}
    for call in calls:
        sha = call["evaluation"]["source_sha256"]
        if sha in programs:
            if programs[sha]["evaluation"] != call["evaluation"]:
                raise ValueError("Conflicting duplicate native result")
            continue
        old = history.get(sha)
        parent = call["construction"].get("parent_source_sha256")
        programs[sha] = {"genome": call["genome"], "source_sha256": sha,
            "semantic_sha256": call["evaluation"]["semantic_sha256"],
            "parent_source_sha256": old["parent_source_sha256"] if old else parent,
            "search_parent_source_sha256": parent, "evaluation": call["evaluation"],
            "construction": call["construction"], "previously_observed": old is not None}
    solved = [p for p in programs.values() if p["evaluation"]["accepted"] and p["evaluation"]["quality_milli"] == 1000]
    prior_observed = {e["semantic_sha256"] for e in history.values()}
    prior_solved = {e["semantic_sha256"] for e in history.values() if e["successes"]}
    return {"task_sha256": digest(task), "global_position": global_position, "epoch": task["epoch"],
        "domain": domain, "slots": slots, "calls": calls, "programs": list(programs.values()),
        "stop_reason": stop, "candidate_cap": cap(task), "macro_width": width, "learned_fragments": learned,
        "selected_root_sha256": selected["evaluation"]["source_sha256"], "charged_evaluations": len(calls),
        "screen_calls": sum(c["construction"]["kind"] == "screen" for c in calls),
        "policy_calls": 0, "host_authored_scheduler": True, "solved": bool(solved),
        "primitive_visits": sum(c["evaluation"]["primitive_visits"] for c in calls),
        "transformed_bytes": sum(c["evaluation"]["transformed_bytes"] for c in calls),
        "archive_size_before": len(history),
        "new_novel_solving_behaviors": sorted({p["semantic_sha256"] for p in solved} - prior_observed),
        "new_first_solving_semantics": sorted({p["semantic_sha256"] for p in solved} - prior_solved),
        "new_source_solves": [p["source_sha256"] for p in solved if p["source_sha256"] not in history],
        "rediscovered": [p["semantic_sha256"] for p in solved if p["source_sha256"] in history
            and history[p["source_sha256"]]["successes"] and history[p["source_sha256"]]["last_success_position"] < global_position - 1]}


def verify_episode(task, position, history, arm, row, *, isolated=True):
    if row["task_sha256"] != digest(task) or row["global_position"] != position:
        raise ValueError("Substituted task or position")
    for call in row["calls"]:
        expected = native.evaluate(task, call["genome"], isolated=False)
        expected["isolated"] = isolated
        if expected != call["evaluation"]:
            raise ValueError("Altered native output, diagnostic behavior or work meter")
        for text, output in zip([*task["inputs"], *native.WITNESSES], call["evaluation"]["outputs"]):
            if output != {"ok": True, "value": native.reference(call["genome"]["ops"], text)}:
                raise ValueError("Native pipeline differs from independently constructed reference")
    rebuilt = episode(task, position, history, arm, isolated=isolated, replay=row)
    if rebuilt != row:
        raise ValueError("Altered selection, novelty, provenance or accounting")
    return True


def summary(rows, history_before=None):
    full = history_from(rows, history_before)
    solved = [entry for entry in full.values() if entry["successes"]]
    cost = sum(row["charged_evaluations"] for row in rows)
    new = sum(len(row["new_novel_solving_behaviors"]) for row in rows)
    visits = sum(row["primitive_visits"] for row in rows)
    return {"tasks": len(rows), "solved": sum(row["solved"] for row in rows), "evaluations": cost,
        "policy_calls": 0, "primitive_visits": visits, "transformed_bytes": sum(r["transformed_bytes"] for r in rows),
        "novel_solving_behaviors": new, "first_solving_semantics": sum(len(r["new_first_solving_semantics"]) for r in rows),
        "new_source_solves": sum(len(r["new_source_solves"]) for r in rows),
        "discovery_per_1000_evaluations": {"numerator": new * 1000, "denominator": cost},
        "discovery_per_1000_primitive_visits": {"numerator": new * 1000, "denominator": visits},
        "archive_size": len(full), "solved_semantic_size": len({e["semantic_sha256"] for e in solved}),
        "branches": len({e["genome"]["ops"][0] for e in solved if e["genome"]["ops"]}),
        "rediscoveries": sum(len(row["rediscovered"]) for row in rows),
        "max_solved_length": max((len(e["genome"]["ops"]) for e in solved), default=0)}
