"""V54 search with recursively learned scaffold-refinement operators."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v30 import meta
from experiment.rsi_v31 import engine as v31, programs
from experiment.rsi_v32 import engine as v32
from experiment.rsi_v51 import engine as v51
from experiment.rsi_v52.abstractions import instantiate
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v54.refinements import apply_refinement

CAPS = v32.CAPS
MAX_EVALUATIONS = v32.MAX_EVALUATIONS

SCAFFOLD_TOP_K = v53.SCAFFOLD_TOP_K
REFINEMENT_TOP_K = 1
SCAFFOLD_MIN_WIDTH = v53.SCAFFOLD_MIN_WIDTH
SCAFFOLD_ROOT_QUALITY_MAX = v53.SCAFFOLD_ROOT_QUALITY_MAX


class Host(v31.Host):
    def __init__(self, task, exact_memory, abstract_memory,
                 refinement_memory, position, *,
                 exact_top_k=2, abstract_top_k=1,
                 scaffold_top_k=SCAFFOLD_TOP_K,
                 refinement_top_k=REFINEMENT_TOP_K,
                 scaffold_min_width=SCAFFOLD_MIN_WIDTH,
                 scaffold_root_quality_max=SCAFFOLD_ROOT_QUALITY_MAX,
                 abstract_only_without_exact=True,
                 scaffold_only_without_exact=True,
                 scaffold_replaces_abstract=True,
                 allowed_modes=None, isolated=True, receipts=None):
        v31.Host.__init__(
            self, task, {}, "archive",
            isolated=isolated, receipts=receipts
        )
        signature = exact_memory.observed_signature(
            self.initial["quality_milli"]
        )
        exact_hits = exact_memory.retrieve(
            signature,
            position=position,
            top_k=exact_top_k,
            min_similarity=v51.MIN_SIMILARITY,
            min_utility=v51.MIN_UTILITY,
            compatible_width=task["width"],
        )

        abstract_hits = []
        base_hits = []
        refinement_hits = []
        scaffold_gate = (
            task["width"] >= scaffold_min_width
            and self.initial["quality_milli"]
            <= scaffold_root_quality_max
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
                base_hits = abstract_memory.retrieve(
                    root_quality_milli=self.initial["quality_milli"],
                    width=task["width"],
                    position=position,
                    top_k=scaffold_top_k,
                    min_utility=-1.0,
                    allowed_modes=("rotation",),
                )
                refinement_hits = refinement_memory.retrieve(
                    root_quality_milli=self.initial["quality_milli"],
                    width=task["width"],
                    position=position,
                    top_k=refinement_top_k,
                )

        if abstract_only_without_exact and exact_hits:
            abstract_hits = []
        if scaffold_only_without_exact and exact_hits:
            base_hits = []
            refinement_hits = []

        diagnostics = {
            "exploration": int(bool(
                exact_hits or abstract_hits or base_hits
            )),
            "generation": int(not (
                exact_hits or abstract_hits or base_hits
            )),
            "scheduling": 0,
        }
        target = meta.select(
            v32.controller("adaptive"),
            diagnostics,
            isolated=isolated,
        )
        allow_memory = target in (
            "identity", "exploration", "scheduling"
        )
        self.exact_hits = exact_hits if allow_memory else []
        self.abstract_hits = abstract_hits if allow_memory else []
        self.base_hits = base_hits if allow_memory else []
        self.refinement_hits = (
            refinement_hits if allow_memory else []
        )

        exact_rows = [
            {
                "source_sha256": hit.source_sha256,
                "genome": hit.genome,
                "strategy_id": hit.strategy_id,
                "memory_origin": "exact",
            }
            for hit in self.exact_hits
        ]

        base_rows = []
        for hit in self.base_hits:
            genome = instantiate(hit.recipe, task["width"])
            source = programs.descriptor(genome)["source_sha256"]
            base_rows.append({
                "source_sha256": source,
                "genome": genome,
                "recipe_id": hit.recipe_id,
                "memory_origin": "scaffold",
                "scaffold_generation": 1,
                "refinement_id": None,
                "base_source_sha256": source,
                "base_genome": genome,
            })

        refined_rows = []
        if base_rows:
            base = base_rows[0]
            for hit in self.refinement_hits:
                genome = apply_refinement(
                    hit.operator, base["genome"]
                )
                source = programs.descriptor(
                    genome
                )["source_sha256"]
                if source == base["source_sha256"]:
                    continue
                refined_rows.append({
                    "source_sha256": source,
                    "genome": genome,
                    "memory_origin": "refined_scaffold",
                    "scaffold_generation": hit.lineage_depth,
                    "refinement_id": hit.refinement_id,
                    "base_source_sha256": base["source_sha256"],
                    "base_genome": base["genome"],
                })

        # Preserve the V53 root scaffold budget exactly: one learned
        # refinement may replace one of the two ordinary scaffold slots.
        scaffold_rows = []
        seen = set()
        for row in refined_rows + base_rows:
            if row["source_sha256"] in seen:
                continue
            seen.add(row["source_sha256"])
            scaffold_rows.append(row)
            if len(scaffold_rows) >= scaffold_top_k:
                break

        if scaffold_rows and scaffold_replaces_abstract:
            self.abstract_hits = []

        abstract_rows = []
        for hit in self.abstract_hits:
            genome = instantiate(hit.recipe, task["width"])
            abstract_rows.append({
                "source_sha256": programs.descriptor(
                    genome
                )["source_sha256"],
                "genome": genome,
                "recipe_id": hit.recipe_id,
                "memory_origin": "abstract",
            })

        ordered = exact_rows + scaffold_rows + abstract_rows
        unique = {}
        for row in ordered:
            unique.setdefault(row["source_sha256"], row)
        self.memory_rows = list(unique.values())

        self.scaffold_meta_by_source = {
            row["source_sha256"]: {
                "generation": row["scaffold_generation"],
                "refinement_id": row["refinement_id"],
                "origin": row["memory_origin"],
                "base_source_sha256": row["base_source_sha256"],
                "base_genome": row["base_genome"],
            }
            for row in scaffold_rows
        }

        self.routing = {
            "controller_sha256": digest_bytes(
                v32.controller("adaptive").encode()
            ),
            "diagnostics": diagnostics,
            "target": target,
            "exact_sources": [
                row["source_sha256"] for row in exact_rows
            ],
            "exact_strategy_ids": [
                hit.strategy_id for hit in self.exact_hits
            ],
            "abstract_sources": [
                row["source_sha256"] for row in abstract_rows
            ],
            "abstract_recipe_ids": [
                hit.recipe_id for hit in self.abstract_hits
            ],
            "scaffold_sources": [
                row["source_sha256"] for row in scaffold_rows
            ],
            "base_scaffold_sources": [
                row["source_sha256"] for row in scaffold_rows
                if row["memory_origin"] == "scaffold"
            ],
            "refined_scaffold_sources": [
                row["source_sha256"] for row in scaffold_rows
                if row["memory_origin"] == "refined_scaffold"
            ],
            "refinement_ids": [
                row["refinement_id"] for row in scaffold_rows
                if row["memory_origin"] == "refined_scaffold"
            ],
            "scaffold_generations": [
                row["scaffold_generation"]
                for row in scaffold_rows
            ],
            "scaffold_gate": scaffold_gate,
            "controller_calls": 1,
            "exact_top_k": exact_top_k,
            "abstract_top_k": abstract_top_k,
            "scaffold_top_k": scaffold_top_k,
            "refinement_top_k": refinement_top_k,
            "scaffold_min_width": scaffold_min_width,
            "scaffold_root_quality_max": (
                scaffold_root_quality_max
            ),
            "abstract_only_without_exact": (
                abstract_only_without_exact
            ),
            "scaffold_only_without_exact": (
                scaffold_only_without_exact
            ),
            "scaffold_replaces_abstract": (
                scaffold_replaces_abstract
            ),
            "allowed_modes": (
                list(allowed_modes)
                if allowed_modes is not None else None
            ),
            "width_memory_enabled": (
                abstract_memory.width_enabled(task["width"])
            ),
            "context_signature": list(signature),
        }

    def children(self, genome, depth):
        if depth >= CAPS.mutation_depth:
            return ()
        rows = []
        if genome == self.root_genome:
            rows.extend(
                self.row(row["genome"])
                for row in self.memory_rows
            )
        rows.extend(
            self.row(child)
            for child in programs.neighbors(genome)
        )
        unique = {}
        for row in rows:
            unique.setdefault(row["source_sha256"], row)
        return tuple(unique.values())


def episode(task, position, exact_memory, abstract_memory,
            refinement_memory, *,
            exact_top_k=2, abstract_top_k=1,
            scaffold_top_k=SCAFFOLD_TOP_K,
            refinement_top_k=REFINEMENT_TOP_K,
            scaffold_min_width=SCAFFOLD_MIN_WIDTH,
            scaffold_root_quality_max=SCAFFOLD_ROOT_QUALITY_MAX,
            abstract_only_without_exact=True,
            scaffold_only_without_exact=True,
            scaffold_replaces_abstract=True,
            allowed_modes=None, isolated=True, replay=None):
    receipts = None if replay is None else {
        row["source_sha256"]: row["evaluation"]
        for row in replay["programs"]
    }
    host = Host(
        task,
        exact_memory,
        abstract_memory,
        refinement_memory,
        position,
        exact_top_k=exact_top_k,
        abstract_top_k=abstract_top_k,
        scaffold_top_k=scaffold_top_k,
        refinement_top_k=refinement_top_k,
        scaffold_min_width=scaffold_min_width,
        scaffold_root_quality_max=scaffold_root_quality_max,
        abstract_only_without_exact=abstract_only_without_exact,
        scaffold_only_without_exact=scaffold_only_without_exact,
        scaffold_replaces_abstract=scaffold_replaces_abstract,
        allowed_modes=allowed_modes,
        isolated=isolated,
        receipts=receipts,
    )
    search = run_search(
        programs.parent(), host, caps=CAPS,
        isolated=isolated
    )

    exact_sources = set(host.routing["exact_sources"])
    abstract_sources = set(host.routing["abstract_sources"])
    base_sources = set(
        host.routing["base_scaffold_sources"]
    )
    refined_sources = set(
        host.routing["refined_scaffold_sources"]
    )
    rows = []

    for key, node in search["nodes"].items():
        genome = node["candidate"]
        evaluation = (
            host.initial if key == "root"
            else node["evaluation"]
        )
        sha = programs.descriptor(
            genome
        )["source_sha256"]
        if node["source_sha256"] != sha:
            raise ValueError("Substituted transducer source")

        parent_id = node["parent_node_id"]
        parent_sha = (
            search["nodes"][parent_id]["source_sha256"]
            if parent_id else None
        )

        if sha in refined_sources:
            origin = "refined_scaffold"
        elif sha in base_sources:
            origin = "scaffold"
        elif sha in abstract_sources:
            origin = "abstract"
        elif sha in exact_sources:
            origin = "exact"
        else:
            origin = "search"

        scaffold_generation = 0
        scaffold_ancestor_source = None
        scaffold_ancestor_refinement_id = None
        scaffold_base_source = None
        scaffold_base_genome = None
        scaffold_ancestor_genome = None
        descended_from_scaffold = False

        if key != "root":
            branch_id = node["outcome"][
                "root_branch_node_id"
            ]
            branch_node = search["nodes"][branch_id]
            branch_source = branch_node["source_sha256"]
            scaffold_meta = host.scaffold_meta_by_source.get(
                branch_source
            )
            if scaffold_meta is not None:
                scaffold_generation = scaffold_meta[
                    "generation"
                ]
                scaffold_ancestor_source = branch_source
                scaffold_ancestor_refinement_id = (
                    scaffold_meta["refinement_id"]
                )
                scaffold_base_source = scaffold_meta[
                    "base_source_sha256"
                ]
                scaffold_base_genome = scaffold_meta[
                    "base_genome"
                ]
                scaffold_ancestor_genome = branch_node[
                    "candidate"
                ]
                descended_from_scaffold = key != branch_id

        rows.append({
            "source_sha256": sha,
            "genome": genome,
            "semantic_sha256": digest(genome),
            "parent_source_sha256": parent_sha,
            "search_parent_source_sha256": parent_sha,
            "evaluation": evaluation,
            "quality_milli": evaluation["quality_milli"],
            "candidate_origin": origin,
            "scaffold_generation": scaffold_generation,
            "scaffold_ancestor_source_sha256": (
                scaffold_ancestor_source
            ),
            "scaffold_ancestor_refinement_id": (
                scaffold_ancestor_refinement_id
            ),
            "scaffold_ancestor_genome": (
                scaffold_ancestor_genome
            ),
            "scaffold_base_source_sha256": (
                scaffold_base_source
            ),
            "scaffold_base_genome": scaffold_base_genome,
            "descended_from_scaffold": (
                descended_from_scaffold
            ),
        })

    successes = [
        row for row in rows
        if row["quality_milli"] == 1000
    ]
    evaluated_abstract = [
        row["source_sha256"]
        for row in rows
        if row["candidate_origin"] == "abstract"
        and row["source_sha256"]
        != host.initial["source_sha256"]
    ]
    evaluated_scaffolds = [
        row["source_sha256"]
        for row in rows
        if row["candidate_origin"] in (
            "scaffold", "refined_scaffold"
        )
        and row["source_sha256"]
        != host.initial["source_sha256"]
    ]
    evaluated_refined = [
        row["source_sha256"]
        for row in rows
        if row["candidate_origin"] == "refined_scaffold"
        and row["source_sha256"]
        != host.initial["source_sha256"]
    ]
    refined_lineage_successes = [
        row["source_sha256"]
        for row in successes
        if row["scaffold_ancestor_refinement_id"]
        is not None
    ]

    result = {
        "position": position,
        "task_sha256": digest(task),
        "search": search,
        "programs": rows,
        "root_evaluation": host.initial,
        "routing": host.routing,
        "charged_evaluations": (
            search["represented_requests"] + 2
        ),
        "solved": bool(successes),
        "new_solutions": [
            row["semantic_sha256"] for row in successes
        ],
        "evaluated_abstract_sources": evaluated_abstract,
        "evaluated_scaffold_sources": evaluated_scaffolds,
        "evaluated_refined_scaffold_sources": (
            evaluated_refined
        ),
        "refined_lineage_successes": (
            refined_lineage_successes
        ),
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError(
            "V54 escaped the inherited evaluation cap"
        )
    return result


def remember(exact_memory, abstract_memory,
             refinement_memory, row):
    exact_memory.remember_episode(row)
    abstract_memory.remember_episode(row)
    refinement_memory.remember_episode(row)
    return row


def summary(rows):
    generations = [
        generation
        for row in rows
        for generation in row["routing"][
            "scaffold_generations"
        ]
    ]
    return {
        "tasks": len(rows),
        "solved": sum(row["solved"] for row in rows),
        "quality_milli": sum(
            row["search"]["best_quality_milli"]
            for row in rows
        ),
        "evaluations": sum(
            row["charged_evaluations"] for row in rows
        ),
        "new_solutions": sum(
            len(row["new_solutions"]) for row in rows
        ),
        "exact_routes": sum(
            bool(row["routing"]["exact_sources"])
            for row in rows
        ),
        "abstract_routes": sum(
            bool(row["routing"]["abstract_sources"])
            for row in rows
        ),
        "scaffold_routes": sum(
            bool(row["routing"]["scaffold_sources"])
            for row in rows
        ),
        "refined_scaffold_routes": sum(
            bool(row["routing"]["refined_scaffold_sources"])
            for row in rows
        ),
        "scaffold_candidates_evaluated": sum(
            len(row["evaluated_scaffold_sources"])
            for row in rows
        ),
        "refined_scaffold_candidates_evaluated": sum(
            len(row["evaluated_refined_scaffold_sources"])
            for row in rows
        ),
        "refined_lineage_successes": sum(
            len(row["refined_lineage_successes"])
            for row in rows
        ),
        "max_scaffold_generation_used": max(
            generations, default=0
        ),
    }
