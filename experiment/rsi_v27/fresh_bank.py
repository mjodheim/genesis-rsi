"""Prospectively fixed project-authored represented tasks, distinct from development."""
from itertools import product

from experiment.rsi_v27.development import Host, PUBLIC_CAPS, population
from experiment.rsi_v25.commitments import digest

CAPS = PUBLIC_CAPS
BANKS = (
    tuple({"family": "plateau", "decoy_quality": decoy, "winning_quality": 420,
           "winner_position": position, "winning_depth": depth, "width": 4,
           "decoy_depth": 3} for decoy, position, depth in product((720, 880), (0, 1, 2), (2, 3))),
    tuple({"family": "complement", "partial_quality": quality, "width": 3,
           "correct_position": position, "repeated_mutations": 3, "first_axis": axis}
          for quality, position, axis in product((450, 700), (0, 1, 2), ("a", "b"))),
    tuple({"family": "scheduling", "partial_quality": quality, "width": 5,
           "winner_position": position, "correct_position": correct, "decoy_depth": 3}
          for quality, position, correct in product((920, 980), (0, 2), (0, 1, 2))),
)


def cumulative(stage):
    if type(stage) is not int or stage not in range(3):
        raise ValueError("Unknown fresh partition")
    return tuple(spec for bank in BANKS[:stage + 1] for spec in bank)


def validate():
    public = {digest(spec) for stage in range(3) for spec in population(stage)}
    fresh = [digest(spec) for bank in BANKS for spec in bank]
    if len(fresh) != len(set(fresh)) or public.intersection(fresh):
        raise ValueError("Fresh represented tasks overlap development")
    return True


validate()
