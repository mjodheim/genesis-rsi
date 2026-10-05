[Reading 155 lines from start (total: 155 lines, 0 remaining)]

"""V52 search: exact structured memory plus cross-width abstractions."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import meta
from experiment.rsi_v31 import engine as v31, programs
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v52.abstractions import instantiate

CAPS = v32.CAPS
MAX_EVALUATIONS = v32.MAX_EVALUATIONS


class Host(v31.Host):
    def __init__(self, task, exact_memory, abstract_memory, position, *,
                 exact_top_k=2, abstract_top_k=1, abstract_only_without_exact=False,
                 allowed_modes=("low",), isolated=True, receipts=None):
        v31.Host.__init__(self, task, {}, "archive", isolated=isolated, receipts=receipts)
        signature = exact_memory.observed_signature(self.initial["quality_milli"])
        exact_hits = exact_memory.retrieve(
            signature, position=position, top_k=exact_top_k,
            min_similarity=v51.MIN_SIMILARITY, min_utility=v51.MIN_UTILITY,
            compatible_width=task["width"],
        )
        abstract_hits = []
        if abstract_memory.width_enabled(task["width"]):
            abstract_hits = abstract_memory.retrieve(
                root_quality_milli=self.initial["quality_milli"],
                width=task["width"], position=position, top_k=abstract_top_k,
                allowed_modes=allowed_modes,
            )
        if abstract_only_without_exact and exact_hits:
            abstract_hits = []
        diagnostics = {
            "exploration": int(bool(exact_hits or abstract_hits)),
            "generation": int(not (exact_hits or abstract_hits)),
            "scheduling": 0,
        }
        target = meta.select(v32.controller("adaptive"), diagnostics, isolated=isolated)
        allow_memory = target in ("identity", "exploration", "scheduling")
        self.exact_hits = exact_hits if allow_memory else []
        self.abstract_hits = abstract_hits if allow_memory else []
        exact_rows = [
            {"source_sha256": hit.source_sha256, "genome": hit.genome,
             "strategy_id": hit.strategy_id, "memory_origin": "exact"}
            for hit in self.exact_hits
        ]
        abstract_rows = []
        for hit in self.abstract_hits:
            genome = instantiate(hit.recipe, task["width"])
            abstract_rows.append({
                "source_sha256": programs.descriptor(genome)["source_sha256"],
                "genome": genome, "recipe_id": hit.recipe_id,
                "memory_origin": "abstract",
            })
        self.memory_rows = exact_rows + abstract_rows
        self.abstract_by_source = {
            row["source_sha256"]: hit for row, hit in zip(abstract_rows, self.abstract_hits)
        }
        self.routing = {
            "controller_sha256": digest_bytes(v32.controller("adaptive").encode()),
            "diagnostics": diagnostics, "target": target,
            "exact_sources": [row["source_sha256"] for row in exact_rows],
            "exact_strategy_ids": [hit.strategy_id for hit in self.exact_hits],
            "abstract_sources": [row["source_sha256"] for row in abstract_rows],
            "abstract_recipe_ids": [hit.recipe_id for hit in self.abstract_hits],
            "controller_calls": 1,
            "exact_top_k": exact_top_k,
            "abstract_top_k": abstract_top_k,
            "abstract_only_without_exact": abstract_only_without_exact,
            "allowed_modes": list(allowed_modes) if allowed_modes is not None else None,
            "width_memory_enabled": abstract_memory.width_enabled(task["width"]),
            "context_signature": list(signature),
        }

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        rows = []
        if genome == self.root_genome:
            rows.extend(self.row(row["genome"]) for row in self.memory_rows)
        rows.extend(self.row(child) for child in programs.neighbors(genome))
        unique = {}
        for row in rows:
            unique.setdefault(row["source_sha256"], row)
        return tuple(unique.values())


def episode(task, position, exact_memory, abstract_memory, *,
            exact_top_k=2, abstract_top_k=1, abstract_only_without_exact=False,
            allowed_modes=("low",), isolated=True, replay=None):
    receipts = None if replay is None else {
        row["source_sha256"]: row["evaluation"] for row in replay["programs"]
    }
    host = Host(
        task, exact_memory, abstract_memory, position,
        exact_top_k=exact_top_k, abstract_top_k=abstract_top_k,
        abstract_only_without_exact=abstract_only_without_exact, allowed_modes=allowed_modes,
        isolated=isolated, receipts=receipts,
    )
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)
    rows = []
    abstract_sources = set(host.routing["abstract_sources"])
    exact_sources = set(host.routing["exact_sources"])
    for key, node in search["nodes"].items():
        genome = node["candidate"]
        evaluation = host.initial if key == "root" else node["evaluation"]
        sha = programs.descriptor(genome)["source_sha256"]
        if node["source_sha256"] != sha:
            raise ValueError("Substituted transducer source")
        parent_id = node["parent_node_id"]
        parent_sha = search["nodes"][parent_id]["source_sha256"] if parent_id else None
        origin = "abstract" if sha in abstract_sources else "exact" if sha in exact_sources else "search"
        rows.append({
            "source_sha256": sha, "genome": genome, "semantic_sha256": digest(genome),
            "parent_source_sha256": parent_sha, "search_parent_source_sha256": parent_sha,
            "evaluation": evaluation, "quality_milli": evaluation["quality_milli"],
            "candidate_origin": origin,
        })
    successes = [row for row in rows if row["quality_milli"] == 1000]
    evaluated_abstract = [
        row["source_sha256"] for row in rows
        if row["candidate_origin"] == "abstract" and row["source_sha256"] != host.initial["source_sha256"]
    ]
    result = {
        "position": position, "task_sha256": digest(task),
        "search": search, "programs": rows,
        "root_evaluation": host.initial, "routing": host.routing,
        "charged_evaluations": search["represented_requests"] + 2,
        "solved": bool(successes),
        "new_solutions": [row["semantic_sha256"] for row in successes],
        "evaluated_abstract_sources": evaluated_abstract,
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError("V52 escaped the inherited evaluation cap")
    return result


def remember(exact_memory, abstract_memory, row):
    exact_memory.remember_episode(row)
    abstract_memory.remember_episode(row)
    return row


def summary(rows):
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "quality_milli": sum(row["search"]["best_quality_milli"] for row in rows),
        "evaluations": sum(row["charged_evaluations"] for row in rows),
        "new_solutions": sum(len(row["new_solutions"]) for row in rows),
        "exact_routes": sum(bool(row["routing"]["exact_sources"]) for row in rows),
        "abstract_routes": sum(bool(row["routing"]["abstract_sources"]) for row in rows),
        "abstract_candidates_evaluated": sum(len(row["evaluated_abstract_sources"]) for row in rows),
    }

[executed on device: Mjodheim-Ubuntu-cx33 (915d6eb6-54f1-400c-8c12-a1e043b0a356)]