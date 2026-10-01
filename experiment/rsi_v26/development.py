"""Complete project-authored public frontier-development population."""
from itertools import product

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.public_development import DevelopmentHost as BaseHost, DEVELOPMENT_CAPS
from experiment.rsi_v25.search_engine import run_search, global_utility
from experiment.rsi_v26.family import ROOT_PARAMS, render, universe, ablations, components


def population():
    return tuple({"first_quality": q, "winner": winner, "width": width,
                  "continuation_depth": winning_depth, "nonwinning_depth": tail}
                 for q, winner, width, winning_depth, tail in product(
                     (0, 500, 800), ("root", "first", "second"), (2, 4, 6), (1, 2), (1, 3)))


class Host(BaseHost):
    def __init__(self, spec):
        super().__init__(spec)
        for i in range(spec["width"]):
            winning = (spec["winner"] == "first" and i == 0) or (spec["winner"] == "second" and i == 1)
            if not winning:
                for depth in range(1, spec["nonwinning_depth"]):
                    token = f"r{i + 1}-d{depth}"
                    self.edges[token] = [self._row(
                        f"r{i + 1}-d{depth + 1}", max(0, min(700, spec["first_quality"] - 200 - depth * 100)),
                        "nonwinning-continuation")]


def evaluate(source):
    episodes = []
    for spec in population():
        result = run_search(source, Host(spec), caps=DEVELOPMENT_CAPS, isolated=False)
        episodes.append({"episode_sha256": digest(spec), "accepted": result["accepted"],
                         "best_quality_milli": result["best_quality_milli"],
                         "represented_requests": result["represented_requests"], "rounds": result["rounds"],
                         "observations_sha256": digest(result["observations"])})
    return {"source_sha256": digest_bytes(source.encode()), "episodes": episodes,
            "utility": global_utility(episodes)}


def witness(source, control_source):
    control, candidate = {}, {}
    exec(compile(control_source, "<bounded-component-ablation>", "exec"), control)
    exec(compile(source, "<bounded-frontier-candidate>", "exec"), candidate)
    for spec in population():
        result = run_search(source, Host(spec), caps=DEVELOPMENT_CAPS, isolated=False)
        for observation in result["observations"]:
            view = observation["view"]
            first = control["select_parent_batch"](view, 2)
            second = candidate["select_parent_batch"](view, 2)
            if first and second and first != second:
                return {"episode": spec, "view": view, "view_sha256": digest(view),
                        "control_parent_ids": first, "successor_parent_ids": second,
                        "control_source_sha256": digest_bytes(control_source.encode())}
    return None


def calibration():
    rows = [{**row, **evaluate(render(row["params"]))} for row in universe()]
    by_params = {digest(row["params"]): row for row in rows}
    root = by_params[digest(ROOT_PARAMS)]
    for row in rows:
        controls = [{"component": axis, "params": params,
                     "source_sha256": by_params[digest(params)]["source_sha256"],
                     "utility": by_params[digest(params)]["utility"]}
                    for axis, params in zip(components(row["params"]), ablations(row["params"]))]
        behavior = None
        for control in controls:
            if control["component"] == "strategy":
                observed = witness(render(row["params"]), render(control["params"]))
                if observed:
                    behavior = {**observed, "control_params": control["params"], "component": "strategy"}
        row["component_ablations"] = controls
        row["parent_choice_witness"] = behavior
        row["eligible_successor"] = bool(
            row["params"]["strategy"] != "inherited" and row["params"]["stop_quality"] == 1000
            and tuple(row["utility"]) > tuple(root["utility"]) and behavior and controls
            and all(tuple(row["utility"]) > tuple(control["utility"]) for control in controls))
        row["meta_quality_milli"] = 750 if row["params"] == ROOT_PARAMS else 800 if row["eligible_successor"] else 650
    return {"schema": "mira-genesis-rsi-v26-complete-public-calibration-v1",
            "scope": "PUBLIC_DEVELOPMENT_ONLY_NOT_A_SCIENTIFIC_ARM",
            "population_sha256": digest(population()), "population_count": len(population()),
            "candidate_count": len(rows), "candidates": rows, "holdout_consumed": False,
            "candidate_evaluations": len(rows) * len(population()),
            "represented_development_requests": sum(-row["utility"][2] for row in rows)}
