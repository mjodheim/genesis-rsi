"""Unfiltered prospective bottleneck contexts, authored before selector behavior."""
from itertools import product

from experiment.rsi_v25.commitments import digest

CONTEXTS = (
    *( {"fault": "exploration", "spec": {"family": "plateau", "decoy_quality": decoy,
          "winning_quality": 510, "winner_position": position, "winning_depth": depth,
          "width": 5, "decoy_depth": 3}}
       for decoy, position, depth in product((740, 890), (0, 1, 2, 3), (2, 3))),
    *( {"fault": "generation", "spec": {"family": "complement", "partial_quality": quality,
          "width": 4, "correct_position": position, "repeated_mutations": repeated, "first_axis": axis}}
       for quality, position, repeated, axis in product((560, 760), (0, 1, 2), (3, 5), ("a", "b"))),
    *( {"fault": "scheduling", "spec": {"family": "scheduling", "partial_quality": quality,
          "width": 6, "winner_position": position, "correct_position": correct, "decoy_depth": 3}}
       for quality, position, correct in product((955, 995), (0, 1, 2), (0, 1, 2))),
)


def validate():
    from experiment.rsi_v28.development import population
    from experiment.rsi_v28.fresh_bank import BANKS
    old = {digest(spec) for stage in range(3) for spec in population(stage)}
    old.update(digest(spec) for bank in BANKS for spec in bank)
    new = [digest(context["spec"]) for context in CONTEXTS]
    if len(new) != len(set(new)) or old.intersection(new):
        raise ValueError("V30 fresh contexts overlap development or consumed tasks")
    return True


validate()
