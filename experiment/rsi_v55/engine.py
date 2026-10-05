"""V55 feedback-driven diagnostic search under the inherited G7 budget."""
from experiment.rsi_v25.commitments import digest
from experiment.rsi_v27.engine import run_search
from experiment.rsi_v31 import programs
from experiment.rsi_v53 import engine as v53
from experiment.rsi_v55.diagnostics import diagnose

CAPS = v53.CAPS
MAX_EVALUATIONS = v53.MAX_EVALUATIONS
DIAGNOSTIC_MIN_WIDTH = 10


class Host(v53.Host):
    def __init__(self, task, exact_memory, abstract_memory, position, *,
                 diagnostic_min_width=DIAGNOSTIC_MIN_WIDTH,
                 isolated=True, receipts=None, **kwargs):
        self.diagnostic_observations = []
        self.diagnostic_probe_by_source = {}
        self.diagnostic_solution_sources = set()
        self.diagnostic_active = False
        self.diagnostic_aborted = False
        self.diagnostic_min_width = diagnostic_min_width

        super().__init__(
            task,
            exact_memory,
            abstract_memory,
            position,
            isolated=isolated,
            receipts=receipts,
            **kwargs,
        )

        state = diagnose(
            task["width"],
            self.initial["quality_milli"],
            self.diagnostic_observations,
        )
        self.diagnostic_active = (
            task["width"] >= diagnostic_min_width
            and state["active"]
            and not self.routing["exact_sources"]
        )

        if self.diagnostic_active:
            # Diagnostic inference replaces speculative cross-width memory for
            # this task. Exact compatible memory remains authoritative and
            # prevents diagnostic activation above.
            self.memory_rows = []
            self.abstract_hits = []
            self.scaffold_hits = []
            self.routing["abstract_sources"] = []
            self.routing["abstract_recipe_ids"] = []
            self.routing["scaffold_sources"] = []
            self.routing["scaffold_recipe_ids"] = []
            self.routing["diagnostics"]["exploration"] = 1
            self.routing["diagnostics"]["generation"] = 0

        self.routing.update({
            "diagnostic_active": self.diagnostic_active,
            "diagnostic_min_width": diagnostic_min_width,
            "diagnostic_mask_size": (
                state["mask_size"] if self.diagnostic_active else None
            ),
        })

    def evaluate(self, row):
        evaluation = super().evaluate(row)
        planned = getattr(
            self, "diagnostic_probe_by_source", {}
        )
        source = row["source_sha256"]
        if source in planned:
            observation = (
                planned[source],
                evaluation["quality_milli"],
            )
            if observation not in self.diagnostic_observations:
                self.diagnostic_observations.append(observation)
        return evaluation

    def _diagnostic_child(self):
        state = diagnose(
            self.task["width"],
            self.initial["quality_milli"],
            self.diagnostic_observations,
        )
        if not state["active"]:
            self.diagnostic_aborted = True
            return None

        if len(state["hypotheses"]) == 1:
            genome = programs.validate({
                "width": self.task["width"],
                "rotation": 0,
                "mask": state["hypotheses"][0],
            })
            row = self.row(genome)
            self.diagnostic_solution_sources.add(
                row["source_sha256"]
            )
            return row

        probe = state["next_probe"]
        if probe is None:
            self.diagnostic_aborted = True
            return None

        genome = programs.validate({
            "width": self.task["width"],
            "rotation": 0,
            "mask": probe,
        })
        row = self.row(genome)
        self.diagnostic_probe_by_source[
            row["source_sha256"]
        ] = probe
        return row

    def children(self, genome, depth):
        if not self.diagnostic_active or self.diagnostic_aborted:
            return super().children(genome, depth)

        if depth >= CAPS.mutation_depth:
            return ()

        # During diagnosis, spend exactly one request per round at the root.
        # This prevents G7's second parallel parent from consuming the fixed
        # budget on an unrelated branch while the sparse mask is identified.
        if genome != self.root_genome:
            return ()

        child = self._diagnostic_child()
        return () if child is None else (child,)


def episode(task, position, exact_memory, abstract_memory, *,
            diagnostic_min_width=DIAGNOSTIC_MIN_WIDTH,
            isolated=True, replay=None, **kwargs):
    receipts = None if replay is None else {
        row["source_sha256"]: row["evaluation"]
        for row in replay["programs"]
    }
    host = Host(
        task,
        exact_memory,
        abstract_memory,
        position,
        diagnostic_min_width=diagnostic_min_width,
        isolated=isolated,
        receipts=receipts,
        **kwargs,
    )
    search = run_search(
        programs.parent(), host, caps=CAPS,
        isolated=isolated,
    )

    exact_sources = set(host.routing["exact_sources"])
    abstract_sources = set(host.routing["abstract_sources"])
    scaffold_sources = set(host.routing["scaffold_sources"])
    probe_sources = set(host.diagnostic_probe_by_source)
    solution_sources = set(host.diagnostic_solution_sources)

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

        if sha in solution_sources:
            origin = "diagnostic_solution"
        elif sha in probe_sources:
            origin = "diagnostic_probe"
        elif sha in scaffold_sources:
            origin = "scaffold"
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

    successes = [
        row for row in rows if row["quality_milli"] == 1000
    ]
    result = {
        "position": position,
        "task_sha256": digest(task),
        "search": search,
        "programs": rows,
        "root_evaluation": host.initial,
        "routing": {
            **host.routing,
            "diagnostic_observations": len(
                host.diagnostic_observations
            ),
            "diagnostic_aborted": host.diagnostic_aborted,
        },
        "charged_evaluations": (
            search["represented_requests"] + 2
        ),
        "solved": bool(successes),
        "new_solutions": [
            row["semantic_sha256"] for row in successes
        ],
        "evaluated_abstract_sources": [
            row["source_sha256"]
            for row in rows
            if row["candidate_origin"] == "abstract"
            and row["source_sha256"]
            != host.initial["source_sha256"]
        ],
        "evaluated_scaffold_sources": [
            row["source_sha256"]
            for row in rows
            if row["candidate_origin"] == "scaffold"
            and row["source_sha256"]
            != host.initial["source_sha256"]
        ],
        "evaluated_diagnostic_probe_sources": [
            row["source_sha256"]
            for row in rows
            if row["candidate_origin"] == "diagnostic_probe"
        ],
        "evaluated_diagnostic_solution_sources": [
            row["source_sha256"]
            for row in rows
            if row["candidate_origin"] == "diagnostic_solution"
        ],
    }
    if result["charged_evaluations"] > MAX_EVALUATIONS:
        raise ValueError(
            "V55 escaped the inherited evaluation cap"
        )
    return result


def remember(exact_memory, abstract_memory, row):
    exact_memory.remember_episode(row)
    abstract_memory.remember_episode(row)
    return row


def summary(rows):
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
        "diagnostic_routes": sum(
            bool(row["routing"]["diagnostic_active"])
            for row in rows
        ),
        "diagnostic_aborts": sum(
            bool(row["routing"]["diagnostic_aborted"])
            for row in rows
        ),
        "diagnostic_probes_evaluated": sum(
            len(row["evaluated_diagnostic_probe_sources"])
            for row in rows
        ),
        "diagnostic_solutions_evaluated": sum(
            len(row["evaluated_diagnostic_solution_sources"])
            for row in rows
        ),
        "diagnostic_tasks_solved": sum(
            row["solved"]
            and bool(row["routing"]["diagnostic_active"])
            for row in rows
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
    }
