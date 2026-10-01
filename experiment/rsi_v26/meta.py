"""Four frozen meta controls; generator follows actual selected executable parents."""
from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.executable_family import baseline_source, predecessor_source, predecessor_ablation_source
from experiment.rsi_v25.search_engine import Caps, run_search
from experiment.rsi_v26.family import ROOT_PARAMS, neighbors, components, render

CAPS = Caps()
ARMS = ("g2_meta", "g1_meta", "g2_ablation", "no_meta")
CONTROLS = {"g2_meta": predecessor_source(), "g1_meta": baseline_source(),
            "g2_ablation": predecessor_ablation_source(), "no_meta": None}


class Host:
    forbidden_tokens = []
    def __init__(self, calibration):
        self.by_params = {digest(row["params"]): row for row in calibration["candidates"]}
    def row(self, params):
        evaluated = self.by_params[digest(params)]
        return {"candidate": dict(params), "source_sha256": evaluated["source_sha256"],
                "quality_milli": evaluated["meta_quality_milli"]}
    def root(self):
        return self.row(ROOT_PARAMS)
    def children(self, params, depth):
        return tuple(self.row(row["params"]) for row in neighbors(params)) if depth < CAPS.mutation_depth else ()
    def evaluate(self, row):
        evidence = self.by_params[digest(row["candidate"])]
        return {"accepted": True, "source_sha256": evidence["source_sha256"],
                "quality_milli": evidence["meta_quality_milli"],
                "public_development_utility": evidence["utility"],
                "development_receipt_sha256": digest(evidence)}
    def action(self, row):
        axes = components(row["candidate"])
        return {"family": "executable-policy", "target_axes": list(axes),
                "mechanisms": list(axes) or ["preserved-g2"],
                "changed_regions": ["parent-selection-and-metadata"]}
    def generation(self, row, depth):
        return 0


def choose(search, calibration):
    by_hash = {row["source_sha256"]: row for row in calibration["candidates"]}
    candidates = [by_hash[node["source_sha256"]] for node in search["nodes"].values()
                  if by_hash[node["source_sha256"]]["eligible_successor"]]
    if not candidates:
        return {**by_hash[digest_bytes(predecessor_source().encode())], "qualified_discovery": False}
    candidates.sort(key=lambda row: (tuple(-x for x in row["utility"]), len(row["acquired_components"]),
                                    row["source_sha256"]))
    return {**candidates[0], "qualified_discovery": True}


def run(calibration, checkpoint=None):
    result = {}
    for arm in ARMS:
        search = run_search(CONTROLS[arm], Host(calibration), caps=CAPS, isolated=True)
        result[arm] = {"search": search, "selected": choose(search, calibration)}
        if checkpoint:
            checkpoint(result)
    return result
