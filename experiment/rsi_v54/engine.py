"""V54 search: V53 selective scaffolds plus recursive affine descendants."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import meta
from experiment.rsi_v31 import engine as v31, programs
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v52.abstractions import instantiate

CAPS = v32.CAPS
MAX_EVALUATIONS = v32.MAX_EVALUATIONS

SCAFFOLD_TOP_K = 2
SCAFFOLD_MIN_WIDTH = 10
SCAFFOLD_ROOT_QUALITY_MAX = 799
LINEAGE_TOP_K = 1


class Host(v31.Host):
    def __init__(self, task, exact_memory, abstract_memory, lineage_memory, position, *,
                 exact_top_k=2, abstract_top_k=1,
                 scaffold_top_k=SCAFFOLD_TOP_K,
                 scaffold_min_width=SCAFFOLD_MIN_WIDTH,
                 scaffold_root_quality_max=SCAFFOLD_ROOT_QUALITY_MAX,
                 lineage_top_k=LINEAGE_TOP_K,
                 abstract_only_without_exact=True,
                 scaffold_only_without_exact=True,
                 scaffold_replaces_abstract=True,
                 allowed_modes=None, isolated=True, receipts=None):
        v31.Host.__init__(self, task, {}, "archive", isolated=isolated, receipts=receipts)
        signature = exact_memory.observed_signature(self.initial["quality_milli"])
        exact_hits = exact_memory.retrieve(
            signature,
            position=position,
            top_k=exact_top_k,
            min_similarity=v51.MIN_SIMILARITY,
            min_utility=v51.MIN_UTILITY,
            compatible_width=task["width"],
        )

        abstract_hits = []
        rotation_hits = []
        lineage_hits = []
        scaffold_gate = (
            task["width"] >= scaffold_min_width
            and self.initial["quality_milli"] <= scaffold_root_quality_max
        )

        if abstract_memory.width_enabled(task["width"]):
            abstract_hits = abstract_memory.retrieve(
                root_quality_milli=self.initial["quality_milli"],
                width=task["width"],
                position=position,
                top_k=abstract_top_k,
                allowed_modes=allowed_modes,
            )
            if scaffold_gate:
                rotation_hits = abstract_memory.retrieve(
                    root_quality_milli=self.initial["quality_milli"],
                    width=task["width"],
                    position=position,
                    top_k=scaffold_top_k,
                    min_utility=-1.0,
                    allowed_modes=("rotation",),
                )
                lineage_hits = lineage_memory.retrieve(
                    width=task["width"],
                    position=position,
                    top_k=lineage_top_k,
                )

        if abstract_only_without_exact and exact_hits:
            abstract_hits = []
        if scaffold_only_without_exact and exact_hits:
            rotation_hits = []
            lineage_hits = []

        exact_rows = [{
            "source_sha256": hit.source_sha256,
            "genome": hit.genome,
            "strategy_id": hit.strategy_id,
            "memory_origin": "exact",
        } for hit in exact_hits]

        abstract_rows = []
        for hit in abstract_hits:
            genome = instantiate(hit.recipe, task["width"])
            abstract_rows.append({
                "source_sha256": programs.descriptor(genome)["source_sha256"],
                "genome": genome,
                "recipe_id": hit.recipe_id,
                "memory_origin": "abstract",
            })

        scaffold_rows = []
        scaffold_lineage = {}

        # A causally proven affine descendant gets one slot. The remaining slot
        # keeps V53's best rotation scaffold, preserving the inherited search arm
        # without increasing root width or the evaluation cap.
        for hit in lineage_hits:
            source = programs.descriptor(hit.genome)["source_sha256"]
            scaffold_rows.append({
                "source_sha256": source,
                "genome": hit.genome,
                "recipe_id": None,
                "memory_origin": "lineage",
            })
            scaffold_lineage[source] = {
                "kind": "lineage",
                "provenance_key": hit.recipe_sha256,
                "recursive_successes": hit.recursive_successes,
                "max_depth": hit.max_depth,
                "lineage_score": hit.score,
            }

        for hit in rotation_hits:
            genome = instantiate(hit.recipe, task["width"])
            source = programs.descriptor(genome)["source_sha256"]
            scaffold_rows.append({
                "source_sha256": source,
                "genome": genome,
                "recipe_id": hit.recipe_id,
                "memory_origin": "scaffold",
            })
            scaffold_lineage[source] = {
                "kind": "rotation",
                "provenance_key": f"rotation:{hit.recipe_id}",
                "recursive_successes": 0,
                "max_depth": 0,
                "lineage_score": 0.0,
            }

        unique_scaffolds = {}
        for row in scaffold_rows:
            unique_scaffolds.setdefault(row["source_sha256"], row)
        scaffold_rows = list(unique_scaffolds.values())[:scaffold_top_k]
        scaffold_sources = {row["source_sha256"] for row in scaffold_rows}
        scaffold_lineage = {
            source: meta_row
            for source, meta_row in scaffold_lineage.items()
            if source in scaffold_sources
        }

        if scaffold_rows and scaffold_replaces_abstract:
            abstract_rows = []

        diagnostics = {
            "exploration": int(bool(exact_rows or abstract_rows or scaffold_rows)),
            "generation": int(not (exact_rows or abstract_rows or scaffold_rows)),
            "scheduling": 0,
        }
        target = meta.select(v32.controller("adaptive"), diagnostics, isolated=isolated)
        allow_memory = target in ("identity", "exploration", "scheduling")
        if not allow_memory:
            exact_rows = []
            abstract_rows = []
            scaffold_rows = []
            scaffold_lineage = {}

        ordered = exact_rows + scaffold_rows + abstract_rows
        unique = {}
        for row in ordered:
            unique.setdefault(row["source_sha256"], row)
        self.memory_rows = list(unique.values())

        self.routing = {
            "controller_sha256": digest_bytes(v32.controller("adaptive").encode()),
            "diagnostics": diagnostics,
            "target": target,
            "exact_sources": [row["source_sha256"] for row in exact_rows],
            "exact_strategy_ids": [row["strategy_id"] for row in exact_rows],
            "abstract_sources": [row["source_sha256"] for row in abstract_rows],
            "abstract_recipe_ids": [row["recipe_id"] for row in abstract_rows],
            "scaffold_sources": [row["source_sha256"] for row in scaffold_rows],
            "scaffold_recipe_ids": [row["recipe_id"] for row in scaffold_rows],
            "scaffold_lineage": scaffold_lineage,
            "scaffold_gate": scaffold_gate,
            "controller_calls": 1,
            "exact_top_k": exact_top_k,
            "abstract_top_k": abstract_top_k,
            "scaffold_top_k": scaffold_top_k,
            "lineage_top_k": lineage_top_k,
            "scaffold_min_width": scaffold_min_width,
            "scaffold_root_quality_max": scaffold_root_quality_max,
            "abstract_only_without_exact": abstract_only_without_exact,
            "scaffold_only_without_exact": scaffold_only_without_exact,
            "scaffold_replaces_abstract": scaffold_replaces_abstract,
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


def episode(task, position, exact_memory, abstract_memory, lineage_memory, *,
            exact_top_k=2, abstract_top_k=1,
            scaffold_top_k=SCAFFOLD_TOP_K,
            scaffold_min_width=SCAFFOLD_MIN_WIDTH,
            scaffold_root_quality_max=SCAFFOLD_ROOT_QUALITY_MAX,
            lineage_top_k=LINEAGE_TOP_K,
            abstract_only_without_exact=True,
            scaffold_only_without_exact=True,
            scaffold_replaces_abstract=True,
            allowed_modes=None, isolated=True, replay=None):
    receipts = None if replay is None else {
        row["source_sha256"]: row["evaluation"] for row in replay["programs"]
    }
    host = Host(
        task, exact_memory, abstract_memory, lineage_memory, position,
        exact_top_k=exact_top_k,
        abstract_top_k=abstract_top_k,
        scaffold_top_k=scaffold_top_k,
        scaffold_min_width=scaffold_min_width,
        scaffold_root_quality_max=scaffold_root_quality_max,
        lineage_top_k=lineage_top_k,
        abstract_only_without_exact=abstract_only_without_exact,
        scaffold_only_without_exact=scaffold_only_without_exact,
        scaffold_replaces_abstract=scaffold_replaces_abstract,
        allowed_modes=allowed_modes,
        isolated=isolated,
        receipts=receipts,
    )
    search = run_search(programs.parent(), host, caps=CAPS, isolated=isolated)

    exact_sources = set(host.routing["exact_sources"])
    abstract_sources = set(host.routing["abstract_sources"])
    scaffold_sources = set(host.routing["scaffold_sources"])
    rows = []
    for key, node in search["nodes"].items():
        genome = node["candidate"]
        evaluation = host.initial if key == "root" else node["evaluation"]
        sha = programs.descriptor(genome)["source_sha256"]
        if node["source_sha256"] != sha:
            raise ValueError("Substituted transducer source")
        parent_id = node["parent_node_id"]
        parent_sha = search["nodes"][parent_id]["source_sha256"] if parent_id else None
        if sha in scaffold_sources:
            meta_row = host.routing["scaffold_lineage"].get(sha, {})
            origin = "lineage" if meta_row.get("kind") == "lineage" else "scaffold"
        elif sha in abstract_sources:
            origin = "abstract"
        elif sha in exact_sources:
            origin = "exact"
        else:
            origin = "search"
        rows.append({
            "source_sha256": sha,
            "genome": genome,
            "semantic_sha256": digest(genome),
            "parent_source_sha256": parent_sha,
            "search_parent_source_sha256": parent_sha,
            "evaluation": evaluation,
            "quality_milli": evaluation["quality_milli"],
            "candidate_origin": origin,
        })

    successes = [row for row in rows if row["quality_milli"] == 1000]
    evaluated_abstract = [
        row["source_sha256"] for row in rows
        if row["candidate_origin"] == "abstract"
        and row["source_sha256"] != host.initial["source_sha256"]
    ]
    evaluated_scaffolds = [
        row["source_sha256"] for row in rows
        if row["candidate_origin"] in ("scaffold", "lineage")
        and row["source_sha256"] != host.initial["source_sha256"]
    ]

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
        "evaluated_abstract_sources": evaluated_abstract,
        "evaluated_scaffold_sources": evaluated_scaffolds,
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError("V54 escaped the inherited evaluation cap")
    return result


def remember(exact_memory, abstract_memory, lineage_memory, row):
    exact_memory.remember_episode(row)
    abstract_memory.remember_episode(row)
    return lineage_memory.remember_episode(row)


def summary(rows):
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "quality_milli": sum(row["search"]["best_quality_milli"] for row in rows),
        "evaluations": sum(row["charged_evaluations"] for row in rows),
        "new_solutions": sum(len(row["new_solutions"]) for row in rows),
        "exact_routes": sum(bool(row["routing"]["exact_sources"]) for row in rows),
        "abstract_routes": sum(bool(row["routing"]["abstract_sources"]) for row in rows),
        "scaffold_routes": sum(bool(row["routing"]["scaffold_sources"]) for row in rows),
        "lineage_scaffold_routes": sum(
            any(meta["kind"] == "lineage" for meta in row["routing"]["scaffold_lineage"].values())
            for row in rows
        ),
        "scaffold_candidates_evaluated": sum(
            len(row["evaluated_scaffold_sources"]) for row in rows
        ),
    }
