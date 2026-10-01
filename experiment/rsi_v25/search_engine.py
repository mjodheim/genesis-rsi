"""Externally bounded executable search, shared by development and native hosts."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiment.rsi_v25.commitments import ROOT, digest, digest_bytes, load_module

SANDBOX = load_module("v25_preserved_sandbox", ROOT / "experiment/rsi_v23/sandbox_policy.py")
GUARD = load_module("v25_preserved_guard", ROOT / "experiment/rsi_v23/policy_guard.py")


@dataclass(frozen=True)
class Caps:
    requests: int = 9
    rounds: int = 8
    parallelism: int = 2
    mutation_depth: int = 2

    def validate(self):
        if any(type(x) is not int or x <= 0 for x in self.__dict__.values()):
            raise ValueError("Search caps must be positive external integers")
        return self


def global_utility(rows) -> tuple[int, int, int, int]:
    if not rows or not all(row["accepted"] for row in rows):
        raise ValueError("Utility requires complete accepted evaluator records")
    return (sum(row["best_quality_milli"] == 1000 for row in rows),
            sum(row["best_quality_milli"] for row in rows),
            -sum(row["represented_requests"] for row in rows),
            -sum(row["rounds"] for row in rows))


def run_search(source: str | None, host, *, caps: Caps = Caps(), isolated: bool = True) -> dict[str, Any]:
    """Only revealed observations enter the policy; host/evaluator stay external."""
    caps.validate()
    if source is not None and GUARD.guard_source(source, host.forbidden_tokens):
        raise ValueError("Executable policy violates the immutable source guard")
    with tempfile.TemporaryDirectory(prefix="v25-search-policy-") as temporary:
        path = Path(temporary) / "policy.py"
        functions = None
        if source is None:
            metadata = (0, 0, 0, 0, 0, 0, 0, 1, caps.rounds, caps.rounds)
        elif isolated:
            path.write_text(source)
            result = SANDBOX.metadata(path, host.forbidden_tokens)
            if not result.get("accepted"):
                raise ValueError(f"Policy metadata rejected: {result}")
            metadata = result["metadata"]
        else:
            # Development-only acceleration on generated, guarded family bytes.
            # Scientific controller decisions always use isolated=True.
            functions = {}
            exec(compile(source, "<public-development-policy>", "exec"), functions)
            metadata = functions["policy_metadata"]()
        if any(type(x) is not int for x in metadata) or len(metadata) != 10 or min(metadata[7:]) <= 0:
            raise ValueError("Invalid executable metadata")
        root = host.root()
        nodes = {"root": {"node_id": "root", "parent_node_id": None,
                          "candidate": root["candidate"], "source_sha256": root["source_sha256"],
                          "lineage_depth": 0, "action": host.action(root),
                          "outcome": {"quality_milli": root["quality_milli"],
                                      "evolver_profile_generation": 0, "ever_champion": True,
                                      "root_branch_node_id": "root"}}}
        revealed, seen, cursors = ["root"], {root["source_sha256"]}, {}
        requests = rounds = stalls = 0
        best, observations, stop = root["quality_milli"], [], None
        while requests < caps.requests and rounds < min(caps.rounds, metadata[8]):
            if rounds and stalls >= metadata[9]:
                stop = "policy_stall_rounds"
                break
            children = {}
            for node_id in revealed:
                node = nodes[node_id]
                rows = host.children(node["candidate"], node["lineage_depth"])
                cursor = cursors.get(node_id, 0)
                while cursor < len(rows) and rows[cursor]["source_sha256"] in seen:
                    cursor += 1
                cursors[node_id] = cursor
                if cursor < len(rows):
                    children[node_id] = rows
            if not children:
                stop = "candidate_family_exhausted"
                break
            view = {"root_node_id": "root", "eligible_parent_ids": sorted(children),
                    "revealed_nodes": [{key: nodes[node_id][key] for key in
                                        ("node_id", "lineage_depth", "action", "outcome")}
                                       for node_id in revealed]}
            parallelism = min(caps.parallelism, metadata[7], caps.requests - requests)
            if source is None:
                parents = view["eligible_parent_ids"][:1]
            elif isolated:
                result = SANDBOX.execute(path, view, parallelism, host.forbidden_tokens)
                if not result.get("accepted"):
                    raise ValueError(f"Isolated policy decision rejected: {result}")
                parents = result["selected_parent_ids"]
            else:
                parents = functions["select_parent_batch"](view, parallelism)
            if (not isinstance(parents, list) or len(parents) != len(set(parents))
                    or len(parents) > parallelism or any(parent not in children for parent in parents)):
                raise ValueError("Policy exceeded external eligibility/parallelism authority")
            if not parents:
                stop = "policy_empty_batch"
                break
            before, produced = best, []
            for parent_id in parents:
                parent = nodes[parent_id]
                rows, cursor = children[parent_id], cursors[parent_id]
                # A parallel predecessor may just have revealed this same source.
                while cursor < len(rows) and rows[cursor]["source_sha256"] in seen:
                    cursor += 1
                if cursor == len(rows):
                    # Another legal member of this same batch may have revealed
                    # the final shared child. It is not evaluated or charged twice.
                    cursors[parent_id] = cursor
                    continue
                child = rows[cursor]
                depth = parent["lineage_depth"] + 1
                if depth > caps.mutation_depth:
                    raise ValueError("External mutation depth exceeded")
                evaluation = host.evaluate(child)
                if (not evaluation.get("accepted") or type(evaluation.get("quality_milli")) is not int
                        or not 0 <= evaluation["quality_milli"] <= 1000
                        or evaluation.get("source_sha256") != child["source_sha256"]):
                    raise ValueError("External evaluator returned an invalid identity or result")
                node_id = "n-" + digest([parent_id, child["source_sha256"], cursor])[:24]
                nodes[node_id] = {"node_id": node_id, "parent_node_id": parent_id,
                                  "candidate": child["candidate"], "source_sha256": child["source_sha256"],
                                  "lineage_depth": depth, "action": host.action(child),
                                  "outcome": {"quality_milli": evaluation["quality_milli"],
                                              "evolver_profile_generation": host.generation(child, depth),
                                              "ever_champion": evaluation["quality_milli"] > best,
                                              "root_branch_node_id": node_id if parent_id == "root" else parent["outcome"]["root_branch_node_id"]},
                                  "evaluation": evaluation}
                best = max(best, evaluation["quality_milli"])
                requests += 1
                cursors[parent_id] = cursor + 1
                seen.add(child["source_sha256"])
                revealed.append(node_id)
                produced.append(node_id)
            rounds += 1
            stalls = 0 if best > before else stalls + 1
            observations.append({"round": rounds, "view": view, "view_sha256": digest(view),
                                 "parent_node_ids": parents, "result_node_ids": produced,
                                 "requests_after": requests, "parallelism_cap": parallelism})
        if stop is None:
            stop = "external_request_budget" if requests >= caps.requests else "round_limit"
        return {"schema": "mira-genesis-rsi-v25-executable-search-v1", "accepted": True,
                "policy_sha256": None if source is None else digest_bytes(source.encode()),
                "best_quality_milli": best, "represented_requests": requests, "rounds": rounds,
                "stop_reason": stop, "nodes": nodes, "observations": observations,
                "caps": caps.__dict__, "isolated_policy_processes": isolated}
