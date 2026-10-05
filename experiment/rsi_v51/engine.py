"""V51 development engine: V32 search with a structured persistent memory."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import meta
from experiment.rsi_v31 import engine as v31, programs
from experiment.rsi_v32 import engine as v32

CAPS = v32.CAPS
MAX_EVALUATIONS = v32.MAX_EVALUATIONS
# V32's best finite selector used a 25-milli compatibility tolerance. V51 keeps
# that observed-only boundary and additionally rejects memories with measured
# negative utility. These are development constants, not an L9 decision rule.
MIN_SIMILARITY = 1.0 / 1.025
MIN_UTILITY = -0.10


class Host(v31.Host):
    def __init__(self, task, memory, position, *, top_k=2, isolated=True, receipts=None):
        # Empty in-memory archive: all reuse comes through the structured DB.
        v31.Host.__init__(self, task, {}, "archive", isolated=isolated, receipts=receipts)
        signature = memory.observed_signature(self.initial["quality_milli"])
        hits = memory.retrieve(
            signature,
            position=position,
            top_k=top_k,
            min_similarity=MIN_SIMILARITY,
            min_utility=MIN_UTILITY,
            compatible_width=task["width"],
        )
        diagnostics = {"exploration": int(bool(hits)), "generation": int(not hits), "scheduling": 0}
        target = meta.select(v32.controller("adaptive"), diagnostics, isolated=isolated)
        count = {"identity": top_k, "exploration": top_k, "generation": 0, "scheduling": 1}[target]
        selected = hits[:count]
        self.retrieved = [
            {"source_sha256": hit.source_sha256, "genome": hit.genome, "strategy_id": hit.strategy_id}
            for hit in selected
        ]
        self.routing = {
            "controller_sha256": digest_bytes(v32.controller("adaptive").encode()),
            "diagnostics": diagnostics,
            "target": target,
            "retrieved_sources": [hit.source_sha256 for hit in selected],
            "retrieved_strategy_ids": [hit.strategy_id for hit in selected],
            "retrieval_scores": [hit.score for hit in selected],
            "controller_calls": 1,
            "top_k": top_k,
            "context_signature": list(signature),
            "min_similarity": MIN_SIMILARITY,
            "min_utility": MIN_UTILITY,
        }

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


def episode(task, position, memory, *, top_k=2, isolated=True, replay=None):
    receipts = None if replay is None else {
        row["source_sha256"]: row["evaluation"] for row in replay["programs"]
    }
    host = Host(task, memory, position, top_k=top_k, isolated=isolated, receipts=receipts)
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)
    rows = []
    for key, node in search["nodes"].items():
        genome = node["candidate"]
        evaluation = host.initial if key == "root" else node["evaluation"]
        sha = programs.descriptor(genome)["source_sha256"]
        if node["source_sha256"] != sha:
            raise ValueError("Substituted transducer source")
        parent_node = node["parent_node_id"]
        parent_sha = search["nodes"][parent_node]["source_sha256"] if parent_node else None
        rows.append({
            "source_sha256": sha,
            "genome": genome,
            "semantic_sha256": digest(genome),
            "parent_source_sha256": parent_sha,
            "search_parent_source_sha256": parent_sha,
            "evaluation": evaluation,
            "quality_milli": evaluation["quality_milli"],
        })
    successes = [row for row in rows if row["quality_milli"] == 1000]
    result = {
        "position": position,
        "task_sha256": digest(task),
        "search": search,
        "programs": rows,
        "root_evaluation": host.initial,
        "routing": host.routing,
        "charged_evaluations": search["represented_requests"] + 2,
        "solved": bool(successes),
        "new_solutions": [row["semantic_sha256"] for row in successes],
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError("Structured memory escaped the inherited evaluation cap")
    return result


def remember(memory, row):
    memory.remember_episode(row)
    return row


def summary(rows):
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "quality_milli": sum(row["search"]["best_quality_milli"] for row in rows),
        "evaluations": sum(row["charged_evaluations"] for row in rows),
        "new_solutions": sum(len(row["new_solutions"]) for row in rows),
        "memory_routes": sum(bool(row["routing"]["retrieved_sources"]) for row in rows),
    }
