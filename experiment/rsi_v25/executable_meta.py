"""Externally evaluated causal-successor search; no transfer bank is imported."""
from __future__ import annotations

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.executable_family import (
    ROOT_PARAMS, ablations, acquired_components, baseline_source, neighbors,
    predecessor_ablation_source, predecessor_source, render_source,
)
from experiment.rsi_v25.public_development import (
    DEVELOPMENT_CAPS, DevelopmentHost, population,
)
from experiment.rsi_v25.search_engine import Caps, run_search

META_CAPS = Caps()
ARMS = ("g2_meta", "g1_meta", "g2_ablation", "no_meta")


def parent_choice_witness(source: str, control_source: str) -> dict | None:
    """Compare nonempty parent choices on identical public revealed views.

    Development calibration uses guarded in-process execution only. Canonical
    controller decisions are independently replayed in isolated subprocesses.
    """
    original, successor = {}, {}
    exec(compile(control_source, "<matched-exploration-ablation>", "exec"), original)
    exec(compile(source, "<guarded-family-successor>", "exec"), successor)
    for spec in population():
        search = run_search(source, DevelopmentHost(spec), caps=DEVELOPMENT_CAPS, isolated=False)
        for observation in search["observations"]:
            view = observation["view"]
            first = original["select_parent_batch"](view, 1)
            second = successor["select_parent_batch"](view, 1)
            # Empty/nonempty differences certify stopping only, not exploration.
            if first and second and first != second:
                return {"episode": spec, "view": view, "view_sha256": digest(view),
                        "control_source_sha256": digest_bytes(control_source.encode()),
                        "control_parent_ids": first, "successor_parent_ids": second}
    return None


def annotate_calibration(calibration: dict) -> dict:
    by_params = {digest(row["params"]): row for row in calibration["candidates"]}
    root = by_params[digest(ROOT_PARAMS)]
    for row in calibration["candidates"]:
        components = acquired_components(row["params"])
        source = render_source(row["params"])
        if row["source_sha256"] != digest_bytes(source.encode()):
            raise ValueError("Development receipt does not bind executable bytes")
        causal = []
        for component, params in zip(components, ablations(row["params"])):
            control = by_params[digest(params)]
            causal.append({"component": component, "params": params,
                           "source_sha256": control["source_sha256"],
                           "utility": control["utility"],
                           "strict_loss": tuple(row["utility"]) > tuple(control["utility"])})
        exploration = any(axis in components for axis in ("strategy", "depth_weight", "novelty_weight"))
        witness = None
        if exploration:
            for control in causal:
                if control["component"] in ("strategy", "depth_weight", "novelty_weight"):
                    candidate_witness = parent_choice_witness(source, render_source(control["params"]))
                    if candidate_witness:
                        witness = {**candidate_witness, "control_params": control["params"],
                                   "component": control["component"]}
                        break
        row["component_ablations"] = causal
        row["parent_choice_witness"] = witness
        row["eligible_successor"] = bool(
            tuple(row["utility"]) > tuple(root["utility"])
            and exploration and witness and causal and all(x["strict_loss"] for x in causal)
        )
        # The meta objective is discovery of a causal exploration successor,
        # not raw utility gains from behaviorally silent numeric acquisitions.
        # Fixed bridge: root/equivalent 750, unqualified candidate 650,
        # a qualified strict causal improvement 800. All four arms see it.
        row["meta_quality_milli"] = (
            750 if row["params"] == ROOT_PARAMS else 800 if row["eligible_successor"] else 650
        )
    calibration["meta_objective"] = "strict-causal-exploration-successor-v1"
    return calibration


class MetaHost:
    forbidden_tokens: list[str] = []

    def __init__(self, calibration):
        self.by_params = {digest(row["params"]): row for row in calibration["candidates"]}
        self.calibration_sha256 = digest(calibration)

    def _row(self, params):
        receipt = self.by_params[digest(params)]
        return {"candidate": params, "source_sha256": receipt["source_sha256"],
                "quality_milli": receipt["meta_quality_milli"]}

    def root(self):
        return self._row(dict(ROOT_PARAMS))

    def children(self, params, depth):
        return tuple(self._row(row["params"]) for row in neighbors(params)) if depth < 2 else ()

    def evaluate(self, row):
        receipt = self.by_params[digest(row["candidate"])]
        return {"accepted": True, "source_sha256": receipt["source_sha256"],
                "quality_milli": receipt["meta_quality_milli"],
                "public_development_utility": receipt["utility"],
                "eligible_successor": receipt["eligible_successor"],
                "development_receipt_sha256": digest(receipt)}

    def action(self, row):
        axes = acquired_components(row["candidate"])
        return {"family": "executable-policy", "target_axes": list(axes),
                "mechanisms": list(axes) or ["preserved-g2"],
                "changed_regions": ["policy-metadata-and-parent-selection"]}

    def generation(self, row, depth):
        # Quality/evidence characterize a candidate; a changed parameter is not
        # treated as an already qualified improvement-process generation.
        return 0


def choose_successor(result, calibration):
    by_source = {row["source_sha256"]: row for row in calibration["candidates"]}
    candidates = [by_source[node["source_sha256"]] for node in result["nodes"].values()
                  if by_source[node["source_sha256"]]["eligible_successor"]]
    if not candidates:
        selected = by_source[digest_bytes(predecessor_source().encode())]
        return {**selected, "qualified_discovery": False, "selection_reason": "no-qualified-successor"}
    # Max utility, then fewest components, then smallest digest; all arms equal.
    candidates.sort(key=lambda row: (tuple(-x for x in row["utility"]),
                                    len(row["acquired_components"]), row["source_sha256"]))
    return {**candidates[0], "qualified_discovery": True,
            "selection_reason": "utility-then-parsimony-then-source-digest"}


def run_meta(calibration, checkpoint=None):
    controls = {"g2_meta": predecessor_source(), "g1_meta": baseline_source(),
                "g2_ablation": predecessor_ablation_source(), "no_meta": None}
    results = {}
    for arm in ARMS:
        search = run_search(controls[arm], MetaHost(calibration), caps=META_CAPS, isolated=True)
        results[arm] = {"search": search, "selected": choose_successor(search, calibration)}
        if checkpoint:
            checkpoint(results)
    return results
