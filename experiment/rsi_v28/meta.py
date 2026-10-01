"""Prospective automatic descendant selection and public pilot diagnostics."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v28 import family
from experiment.rsi_v27.engine import CAPS, run_search
from experiment.rsi_v28.development import phase_episodes
from experiment.rsi_v28.development import population as public_population


def indexed(calibration):
    return {digest(row["params"]): row for row in calibration["candidates"]}


def eligible(row, root, stage, rows):
    p, base = row["params"], root["params"]
    acquired = family.components(p, base)
    if len(acquired) != 1 or any(base[k] and p[k] != base[k] for k in family.AXES):
        return False
    observed, previous = row["phases"][stage], root["phases"][stage]
    if tuple(observed["utility"]) <= tuple(previous["utility"]):
        return False
    # Improving an old partition alone cannot constitute the new transition.
    count = len(public_population(stage))
    from experiment.rsi_v25.search_engine import global_utility
    if global_utility(phase_episodes(row, stage)[-count:]) <= global_utility(phase_episodes(root, stage)[-count:]):
        return False
    # Required prior capabilities are full-quality solved episodes, not cost claims.
    if any(old["best_quality_milli"] == 1000 and new["best_quality_milli"] != 1000
           for old, new in zip(phase_episodes(root, stage), phase_episodes(row, stage))):
        return False
    # Every previously acquired mechanism remains causal on the cumulative population.
    for axis in family.components(p):
        control = {**p, axis: 0}
        if tuple(observed["utility"]) <= tuple(rows[digest(control)]["phases"][stage]["utility"]):
            return False
    return True


class Host:
    forbidden_tokens = []

    def __init__(self, calibration, base, stage):
        self.rows = indexed(calibration)
        self.base, self.stage = family.validate(base), stage
        self.root_row = self.rows[digest(base)]
        self.root_source = family.render(base)
        self.descriptors = {digest(r["params"]): {"structure_sha256": family.structure(family.render(r["params"])),
                            "target_axes": family.syntax_changes(family.render(r["params"]), self.root_source)}
                            for r in self.rows.values()}
        from experiment.rsi_v25.search_engine import global_utility
        count = len(public_population(stage))
        self.active_utilities = {digest(r["params"]): global_utility(phase_episodes(r, stage)[-count:])
                                 for r in self.rows.values()}
        self.utilities = sorted(set(self.active_utilities.values()))

    def row(self, candidate):
        g = family.genotype(candidate["params"], candidate["layout"])
        row = self.rows[digest(g["params"])]
        qualified = eligible(row, self.root_row, self.stage, self.rows)
        ordinal = self.utilities.index(self.active_utilities[digest(g["params"])])
        quality = 1000 if qualified else 500 + 499 * ordinal // max(1, len(self.utilities) - 1)
        return {"candidate": g, "source_sha256": digest_bytes(family.render_genotype(g).encode()),
                "quality_milli": quality, "qualified": qualified}

    def root(self):
        return self.row(family.genotype(self.base))

    def children(self, candidate, depth):
        # Each transition is typed as acquisition of one new semantic component.
        # This syntax constraint is independent of quality or eligibility outcomes.
        return tuple(self.row(r["genotype"]) for r in family.mutation_neighbors(candidate, locked=self.base)
                     if len(family.components(r["genotype"]["params"], self.base)) <= 1
                     ) if depth < CAPS.mutation_depth else ()

    def action(self, row):
        axes = [axis + ":" + str(row["candidate"]["params"][axis])
                for axis in family.components(row["candidate"]["params"], self.base)]
        return {"family": "executable-pipeline", **self.descriptors[digest(row["candidate"]["params"])],
                "mechanisms": axes or ["qualified-parent"], "changed_regions": axes}

    def evaluate(self, row):
        evidence = self.rows[digest(row["candidate"]["params"])]
        return {"accepted": True, "source_sha256": row["source_sha256"],
                "quality_milli": row["quality_milli"], "qualified": row["qualified"],
                "public_development_utility": evidence["phases"][self.stage]["utility"],
                "public_receipt_sha256": digest(evidence)}


def choose(search, host):
    available = [{**host.rows[digest(node["candidate"]["params"])],
                  "genotype": node["candidate"], "source_sha256": node["source_sha256"]}
                 for node in search["nodes"].values()
                 if eligible(host.rows[digest(node["candidate"]["params"])], host.root_row, host.stage, host.rows)]
    if not available:
        return {"qualified_discovery": False, "params": host.base, "genotype": family.genotype(host.base),
                "source_sha256": digest_bytes(family.render(host.base).encode())}
    available.sort(key=lambda row: (tuple(-x for x in row["phases"][host.stage]["utility"]),
                                   sum(row["params"].values()), row["genotype"]["layout"], row["source_sha256"]))
    return {"qualified_discovery": True, **available[0]}


def utility(selected, search, stage):
    if not selected["qualified_discovery"]:
        return (0, 0, 0, -search["represented_requests"], -search["rounds"])
    return (1, *selected["phases"][stage]["utility"][:2],
            -search["represented_requests"], -search["rounds"])


def pilot(calibration, *, isolated=False, checkpoint=None):
    base, phases, candidate = dict(family.ROOT_PARAMS), [], family.genotype(family.ROOT_PARAMS)
    for stage in range(3):
        host = Host(calibration, base, stage)
        search = run_search(family.render_genotype(candidate), host, isolated=isolated)
        selected = choose(search, host)
        controls = []
        for axis in family.components(base):
            ablated = {**base, axis: 0}
            comparison = run_search(family.render(ablated), host, isolated=isolated)
            successor = choose(comparison, host)
            controls.append({"component": axis, "controller_params": ablated,
                             "selected_params": successor["params"],
                             "utility": utility(successor, comparison, stage), "search": comparison})
        phases.append({"stage": stage, "parent_params": base, "selected_params": selected["params"],
                       "qualified_discovery": selected["qualified_discovery"],
                       "selected_genotype": selected["genotype"], "selected_source_sha256": selected["source_sha256"],
                       "utility": utility(selected, search, stage), "controls": controls,
                       "trace_sha256": digest(search), "search": search})
        if checkpoint:
            checkpoint(phases)
        if not selected["qualified_discovery"]:
            break
        base, candidate = selected["params"], selected["genotype"]
    return {"scope": "PUBLIC_DEVELOPMENT_PILOT_NOT_CANONICAL", "holdout_consumed": False,
            "phases": phases, "final_params": base}
