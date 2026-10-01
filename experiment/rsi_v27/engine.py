"""External immutable-budget pipeline with isolated lineage-owned decisions."""
import json
import subprocess
import sys
import tempfile
from functools import lru_cache
from pathlib import Path

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.search_engine import Caps, GUARD

WORKER = Path(__file__).with_name("worker.py")
CAPS = Caps(requests=12, rounds=8, parallelism=2, mutation_depth=3)


@lru_cache(maxsize=128)
def development_functions(source, forbidden):
    if GUARD.guard_source(source, forbidden):
        raise ValueError("Lineage source violates immutable policy guard")
    functions = {}
    exec(compile(source, "<public-development-only>", "exec"), functions)
    return functions


def call(path, payload):
    with tempfile.TemporaryDirectory(prefix="v27-policy-call-") as temporary:
        run = subprocess.run([sys.executable, "-I", "-S", str(WORKER), str(path)],
                             input=json.dumps(payload), text=True, capture_output=True,
                             cwd=temporary, env={"PYTHONHASHSEED": "0", "LC_ALL": "C"}, timeout=3)
    if run.returncode:
        raise ValueError("Isolated lineage call failed: " + run.stderr[-1000:])
    return json.loads(run.stdout)


def run_search(source, host, *, caps=CAPS, isolated=True):
    caps.validate()
    if isolated and GUARD.guard_source(source, host.forbidden_tokens):
        raise ValueError("Lineage source violates immutable policy guard")
    functions = {} if isolated else development_functions(source, tuple(host.forbidden_tokens))
    with tempfile.TemporaryDirectory(prefix="v27-policy-source-") as temporary:
        path = Path(temporary) / "policy.py"
        if isolated:
            path.write_text(source)
            metadata = call(path, {"mode": "metadata"})["metadata"]
        else:
            metadata = functions["policy_metadata"]()
        if len(metadata) != 10 or any(type(x) is not int for x in metadata) or min(metadata[7:]) <= 0:
            raise ValueError("Invalid policy ABI metadata")
        root = host.root()
        if type(root.get("quality_milli")) is not int or not 0 <= root["quality_milli"] <= 1000:
            raise ValueError("Invalid external root quality")
        nodes = {"root": {"node_id": "root", "parent_node_id": None, "lineage_depth": 0,
                          "candidate": root["candidate"], "source_sha256": root["source_sha256"],
                          "action": host.action(root), "outcome": {"quality_milli": root["quality_milli"],
                          "root_branch_node_id": "root", "ever_champion": True,
                          "evolver_profile_generation": 0}}}
        seen, revealed = {root["source_sha256"]}, ["root"]
        observations = []
        requests = rounds = stalls = 0
        best, stop = root["quality_milli"], None
        while requests < caps.requests and rounds < min(caps.rounds, metadata[8]):
            if rounds and stalls >= metadata[9]:
                stop = "policy_stall_rounds"
                break
            choices = {key: [r for r in host.children(nodes[key]["candidate"], nodes[key]["lineage_depth"])
                             if r["source_sha256"] not in seen] for key in revealed}
            choices = {key: rows for key, rows in choices.items() if rows}
            if not choices:
                stop = "candidate_family_exhausted"
                break
            view = {"root_node_id": "root", "eligible_parent_ids": sorted(choices),
                    "revealed_nodes": [{k: nodes[key][k] for k in
                        ("node_id", "parent_node_id", "lineage_depth", "action", "outcome")} for key in revealed],
                    "remaining_requests": caps.requests - requests, "remaining_rounds": caps.rounds - rounds}
            descriptions = {key: [{"source_sha256": r["source_sha256"], "action": host.action(r)}
                                  for r in rows] for key, rows in choices.items()}
            parallelism = min(caps.parallelism, metadata[7], caps.requests - requests)
            if isolated:
                decision = call(path, {"mode": "decide", "view": view, "choices": descriptions,
                                       "max_parallelism": parallelism})
                parents, ordered = decision["selected_parent_ids"], decision["ordered_candidates"]
                if decision["metadata"] != list(metadata):
                    raise ValueError("Policy metadata changed during execution")
            else:
                parents = functions["select_parent_batch"](view, parallelism)
                order = functions.get("order_candidates")
                ordered = {key: order(view, key, rows) if order else [r["source_sha256"] for r in rows]
                           for key, rows in descriptions.items()}
            if (type(parents) is not list or len(parents) != len(set(parents))
                    or len(parents) > parallelism or any(key not in choices for key in parents)):
                raise ValueError("Policy exceeded external parent authority")
            if set(ordered) != set(choices):
                raise ValueError("Candidate ordering changed the eligible parent population")
            for key, hashes in ordered.items():
                if type(hashes) is not list or len(hashes) != len(set(hashes)) or set(hashes) != {
                        r["source_sha256"] for r in choices[key]}:
                    raise ValueError("Candidate ordering is not an exact permutation")
            if not parents:
                stop = "policy_empty_batch"
                break
            before, produced = best, []
            for key in parents:
                by_hash = {r["source_sha256"]: r for r in choices[key]}
                available = [h for h in ordered[key] if h not in seen]
                if not available:
                    continue
                child = by_hash[available[0]]
                depth = nodes[key]["lineage_depth"] + 1
                if depth > caps.mutation_depth:
                    raise ValueError("External mutation-depth budget exceeded")
                evaluation = host.evaluate(child)
                if (not evaluation.get("accepted") or type(evaluation.get("quality_milli")) is not int
                        or not 0 <= evaluation["quality_milli"] <= 1000
                        or evaluation["source_sha256"] != child["source_sha256"]):
                    raise ValueError("External evaluator identity or quality mismatch")
                node_id = "n-" + digest([key, child["source_sha256"]])[:24]
                nodes[node_id] = {"node_id": node_id, "parent_node_id": key, "lineage_depth": depth,
                                 "candidate": child["candidate"], "source_sha256": child["source_sha256"],
                                 "action": host.action(child), "evaluation": evaluation,
                                 "outcome": {"quality_milli": evaluation["quality_milli"],
                                 "root_branch_node_id": node_id if key == "root" else nodes[key]["outcome"]["root_branch_node_id"],
                                 "ever_champion": evaluation["quality_milli"] > best,
                                 "evolver_profile_generation": 0}}
                best = max(best, evaluation["quality_milli"])
                requests += 1
                seen.add(child["source_sha256"])
                revealed.append(node_id)
                produced.append(node_id)
            rounds += 1
            stalls = 0 if best > before else stalls + 1
            observations.append({"round": rounds, "view": view, "view_sha256": digest(view),
                                 "ordered_candidates": ordered, "parent_node_ids": parents,
                                 "result_node_ids": produced, "requests_after": requests,
                                 "parallelism_cap": parallelism})
        if stop is None:
            stop = "external_request_budget" if requests >= caps.requests else "round_limit"
        return {"schema": "mira-genesis-v27-bounded-pipeline-search-v1", "accepted": True,
                "policy_sha256": digest_bytes(source.encode()), "best_quality_milli": best,
                "represented_requests": requests, "rounds": rounds, "stop_reason": stop,
                "nodes": nodes, "observations": observations, "caps": caps.__dict__,
                "isolated_policy_processes": isolated}
