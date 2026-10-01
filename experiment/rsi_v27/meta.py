"""Prospective automatic descendant selection and public pilot diagnostics."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v27 import family
from experiment.rsi_v27.engine import CAPS, run_search
from experiment.rsi_v27.development import phase_episodes


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
        self.utilities = sorted(set(tuple(r["phases"][stage]["utility"]) for r in self.rows.values()))

    def row(self, params):
        row = self.rows[digest(params)]
        qualified = eligible(row, self.root_row, self.stage, self.rows)
        ordinal = self.utilities.index(tuple(row["phases"][self.stage]["utility"]))
        quality = 1000 if qualified else 500 + 499 * ordinal // max(1, len(self.utilities) - 1)
        return {"candidate": params, "source_sha256": row["source_sha256"],
                "quality_milli": quality, "qualified": qualified}

    def root(self):
        return self.row(self.base)

    def children(self, params, depth):
        return tuple(self.row(r["params"]) for r in family.neighbors(params, locked=self.base)
                     ) if depth < CAPS.mutation_depth else ()

    def action(self, row):
        axes = list(family.components(row["candidate"], self.base))
        return {"family": "executable-pipeline", "target_axes": axes,
                "mechanisms": axes or ["qualified-parent"], "changed_regions": axes}

    def evaluate(self, row):
        evidence = self.rows[digest(row["candidate"])]
        return {"accepted": True, "source_sha256": row["source_sha256"],
                "quality_milli": row["quality_milli"], "qualified": row["qualified"],
                "public_development_utility": evidence["phases"][self.stage]["utility"],
                "public_receipt_sha256": digest(evidence)}


def choose(search, host):
    rows = {row["source_sha256"]: row for row in host.rows.values()}
    available = [rows[node["source_sha256"]] for node in search["nodes"].values()
                 if eligible(rows[node["source_sha256"]], host.root_row, host.stage, host.rows)]
    if not available:
        return {"qualified_discovery": False, "params": host.base,
                "source_sha256": digest_bytes(family.render(host.base).encode())}
    available.sort(key=lambda row: (tuple(-x for x in row["phases"][host.stage]["utility"]),
                                   sum(row["params"].values()), row["source_sha256"]))
    return {"qualified_discovery": True, **available[0]}


def utility(selected, search, stage):
    if not selected["qualified_discovery"]:
        return (0, 0, 0, -search["represented_requests"], -search["rounds"])
    return (1, *selected["phases"][stage]["utility"][:2],
            -search["represented_requests"], -search["rounds"])


def pilot(calibration):
    base, phases = dict(family.ROOT_PARAMS), []
    for stage in range(3):
        host = Host(calibration, base, stage)
        search = run_search(family.render(base), host, isolated=False)
        selected = choose(search, host)
        controls = []
        for axis in family.components(base):
            ablated = {**base, axis: 0}
            comparison = run_search(family.render(ablated), host, isolated=False)
            successor = choose(comparison, host)
            controls.append({"component": axis, "controller_params": ablated,
                             "selected_params": successor["params"],
                             "utility": utility(successor, comparison, stage)})
        phases.append({"stage": stage, "parent_params": base, "selected_params": selected["params"],
                       "qualified_discovery": selected["qualified_discovery"],
                       "utility": utility(selected, search, stage), "controls": controls,
                       "trace_sha256": digest(search), "search": search})
        if not selected["qualified_discovery"]:
            break
        base = selected["params"]
    return {"scope": "PUBLIC_DEVELOPMENT_PILOT_NOT_CANONICAL", "holdout_consumed": False,
            "phases": phases, "final_params": base}
