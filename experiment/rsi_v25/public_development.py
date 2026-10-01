"""Complete project-authored public development population, never final transfer tasks."""
from __future__ import annotations

import itertools
from typing import Any

from experiment.rsi_v25.commitments import digest, digest_bytes
from experiment.rsi_v25.executable_family import acquired_components, render_source, universe
from experiment.rsi_v25.search_engine import Caps, global_utility, run_search

DEVELOPMENT_CAPS = Caps(requests=9, rounds=8, parallelism=2, mutation_depth=4)


def population() -> tuple[dict[str, Any], ...]:
    return tuple({"first_quality": quality, "winner": winner, "width": width,
                  "continuation_depth": depth}
                 for quality, winner, width, depth in itertools.product(
                     (0, 500, 800), ("root", "first", "second"), (2, 4), (1, 2)))


class DevelopmentHost:
    forbidden_tokens: list[str] = []

    def __init__(self, spec):
        self.spec = dict(spec)
        self.edges = {"root": []}
        quality = spec["first_quality"]
        for i in range(spec["width"]):
            token = f"r{i + 1}"
            q = quality if i == 0 else max(0, min(700, quality - i * 100))
            if spec["winner"] == "root" and i == 1:
                q = 1000
            self.edges["root"].append(self._row(token, q, "open-branch"))
            self.edges[token] = [self._row(f"{token}-d1", max(0, min(700, quality - 200)), "follow-branch")]
            winning = (spec["winner"] == "first" and i == 0) or (spec["winner"] == "second" and i == 1)
            if winning and spec["continuation_depth"] == 1:
                self.edges[token][0] = self._row(f"{token}-d1", 1000, "follow-branch")
            elif winning:
                self.edges[f"{token}-d1"] = [self._row(f"{token}-d2", 1000, "compose-continuation")]

    def _row(self, token, quality, mechanism):
        candidate = {"token": token, "quality": quality, "mechanism": mechanism}
        return {"candidate": candidate, "quality_milli": quality, "source_sha256": digest([self.spec, candidate])}

    def root(self):
        return self._row("root", 0, "seed")

    def children(self, candidate, depth):
        return tuple(self.edges.get(candidate["token"], ())) if depth < DEVELOPMENT_CAPS.mutation_depth else ()

    def evaluate(self, row):
        return {"accepted": True, "quality_milli": row["quality_milli"],
                "source_sha256": row["source_sha256"], "evaluator": "public-graph-only"}

    def action(self, row):
        return {"family": "public-development", "target_axes": ["search-process"],
                "mechanisms": [row["candidate"]["mechanism"]], "changed_regions": ["public-graph"]}

    def generation(self, row, depth):
        return 0


def evaluate_source(source: str, *, isolated: bool = False) -> dict[str, Any]:
    rows = []
    for spec in population():
        result = run_search(source, DevelopmentHost(spec), caps=DEVELOPMENT_CAPS, isolated=isolated)
        rows.append({"episode_sha256": digest(spec), "accepted": result["accepted"],
                     "best_quality_milli": result["best_quality_milli"],
                     "represented_requests": result["represented_requests"], "rounds": result["rounds"],
                     "observations_sha256": digest(result["observations"])})
    return {"source_sha256": digest_bytes(source.encode()), "utility": global_utility(rows), "episodes": rows}


def calibration() -> dict[str, Any]:
    """Evaluate the entire public grammar without selecting a scientific successor."""
    candidates = []
    for row in universe():
        evaluation = evaluate_source(render_source(row["params"]))
        candidates.append({**row, **evaluation,
                           "acquired_components": list(acquired_components(row["params"]))})
    return {"schema": "mira-genesis-rsi-v25-public-calibration-v1",
            "scope": "PUBLIC_DEVELOPMENT_ONLY_NOT_A_SCIENTIFIC_ARM",
            "population_sha256": digest(population()), "population_count": len(population()),
            "candidate_count": len(candidates), "candidates": candidates,
            "candidate_evaluations": len(candidates) * len(population()),
            "represented_development_requests": sum(-row["utility"][2] for row in candidates),
            "holdout_consumed": False}
