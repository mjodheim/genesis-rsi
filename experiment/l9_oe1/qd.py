"""Unstructured quality-diversity archive for OE1."""
from __future__ import annotations

from dataclasses import dataclass

DOMINANCE_RADIUS = 0.35


@dataclass(frozen=True)
class BehaviorProfile:
    solved_task_ids: frozenset[str]
    mean_cost: float
    late_discovery_rate: float
    quality: float

    def descriptor(self):
        return {
            "solved_task_ids": sorted(self.solved_task_ids),
            "mean_cost": self.mean_cost,
            "late_discovery_rate": self.late_discovery_rate,
            "quality": self.quality,
        }


@dataclass
class Elite:
    improver_sha256: str
    profile: BehaviorProfile
    novelty: float
    learning_progress: float
    children: int = 0

    def parent_score(self, genome):
        penalty = (1.0 + self.children) ** max(0.0, genome.parent_child_penalty)
        return (
            max(1e-9, self.profile.quality) ** max(0.0, genome.parent_quality_weight)
            * (1.0 + self.novelty * max(0.0, genome.parent_novelty_weight))
            * (1.0 + max(0.0, self.learning_progress) * max(0.0, genome.parent_progress_weight))
            / penalty
        )


def _jaccard_distance(a, b):
    union = a | b
    if not union:
        return 0.0
    return 1.0 - (len(a & b) / len(union))


def behavior_distance(a: BehaviorProfile, b: BehaviorProfile):
    solve = _jaccard_distance(a.solved_task_ids, b.solved_task_ids)
    cost_scale = max(1.0, a.mean_cost, b.mean_cost)
    cost = min(1.0, abs(a.mean_cost - b.mean_cost) / cost_scale)
    tail = min(1.0, abs(a.late_discovery_rate - b.late_discovery_rate))
    return 0.70 * solve + 0.15 * cost + 0.15 * tail


def novelty(profile, archive, *, k=5):
    if not archive:
        return 1.0
    distances = sorted(behavior_distance(profile, elite.profile) for elite in archive)
    chosen = distances[: max(1, min(k, len(distances)))]
    return sum(chosen) / len(chosen)


def dominates(a: Elite, b: Elite):
    # Quality dominance is only meaningful inside a local behavioural neighbourhood.
    # Distant behaviours are retained as stepping stones even when slightly weaker.
    if behavior_distance(a.profile, b.profile) > DOMINANCE_RADIUS:
        return False
    not_worse = (
        a.profile.quality >= b.profile.quality
        and a.novelty >= b.novelty
        and a.learning_progress >= b.learning_progress
    )
    strictly = (
        a.profile.quality > b.profile.quality
        or a.novelty > b.novelty
        or a.learning_progress > b.learning_progress
    )
    return not_worse and strictly


class QDArchive:
    """Pareto-style unstructured archive preserving useful stepping stones."""

    def __init__(self, *, max_size=64):
        self.max_size = max_size
        self.elites: list[Elite] = []

    def add(self, improver_sha256, profile, *, learning_progress=0.0):
        candidate = Elite(
            improver_sha256=improver_sha256,
            profile=profile,
            novelty=novelty(profile, self.elites),
            learning_progress=learning_progress,
        )
        if any(dominates(elite, candidate) for elite in self.elites):
            return False, candidate

        self.elites = [
            elite for elite in self.elites if not dominates(candidate, elite)
        ]
        self.elites.append(candidate)

        if len(self.elites) > self.max_size:
            self.elites.sort(
                key=lambda elite: (
                    elite.profile.quality
                    + elite.novelty
                    + max(0.0, elite.learning_progress)
                ),
                reverse=True,
            )
            self.elites = self.elites[: self.max_size]
        return True, candidate

    def parents(self, genome, *, count=1):
        ranked = sorted(
            self.elites,
            key=lambda elite: elite.parent_score(genome),
            reverse=True,
        )
        chosen = ranked[:count]
        for elite in chosen:
            elite.children += 1
        return tuple(chosen)

    def persist(self, store):
        for elite in self.elites:
            store.save_elite(
                niche_key=elite.improver_sha256,
                improver_sha256=elite.improver_sha256,
                quality=elite.profile.quality,
                novelty=elite.novelty,
                learning_progress=elite.learning_progress,
                children=elite.children,
                descriptor=elite.profile.descriptor(),
            )


def profile_from_results(task_rows):
    """Build a behavioural profile from matched task outcomes."""
    if not task_rows:
        return BehaviorProfile(frozenset(), 0.0, 0.0, 0.0)

    solved = frozenset(
        row["task_sha256"] for row in task_rows if row["solved"]
    )
    mean_cost = sum(row["charged_evaluations"] for row in task_rows) / len(task_rows)
    max_window = max(row.get("window", 0) for row in task_rows)
    late_start = max(0, max_window - 2)
    late = [row for row in task_rows if row.get("window", 0) >= late_start]
    late_discovery_rate = (
        sum(bool(row.get("new_solutions")) for row in late) / len(late)
        if late else 0.0
    )
    solve_rate = len(solved) / len(task_rows)
    cost_efficiency = 1.0 / max(1.0, mean_cost)
    quality = solve_rate + 0.05 * cost_efficiency + 0.10 * late_discovery_rate
    return BehaviorProfile(solved, mean_cost, late_discovery_rate, quality)
