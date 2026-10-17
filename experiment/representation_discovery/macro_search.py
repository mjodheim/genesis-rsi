"""Two-stage representation search: escape the short-horizon greedy trap.

Stage one explores combinations of reversible axis operators (2**n possibilities).
Stage two tests extra arbitrary shears against the best learned basis programs.
All selection uses original CIRCUIT1 training families; *historically exposed*
evaluation families only contribute post-selection descriptive results.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import random
from experiment.representation_discovery import prototype as p
from experiment.representation_discovery import adaptive_basis as ab

@dataclass(frozen=True)
class Result:
    program: tuple[ab.Op, ...]
    train_bits: int
    baseline_mask: int
    evaluated_candidates: int
    prescreen_probes: int
    stage_one_candidates: int
    stage_two_candidates: int

def axis_program(inputs: int, mask: int) -> tuple[ab.Op, ...]:
    if mask < 0 or mask >= (1 << inputs):
        raise ValueError("bad mask")
    return tuple(ab.Op("axis", k) for k in range(inputs) if (mask >> k) & 1)


def discover(training: tuple, inputs: int, *, seed: int = 0,
             shear_mode: str = "guided", top_bases: int = 4,
             per_base: int = 12) -> Result:
    """Explore an entire bounded axis grammar, then generate shear extensions.

    This is a HUMAN-DESIGNED operator grammar; the search does not invent it.
    Guided ranks shears by every training example (work separately recorded).
    Random samples the exact same number of shear candidates from identical
    axis-seed programs; thus both arms match EVALUATIONS, not total compute.
    """
    if not (2 <= inputs <= p.MAX_INPUTS) or top_bases < 1 or per_base < 1:
        raise ValueError("bad search configuration")
    if shear_mode not in ("guided", "random"):
        raise ValueError("bad shear mode")
    rng = random.Random(f"macro-search|{inputs}|{seed}|{shear_mode}")
    ax_candidates = [(ab.training_score(training, inputs, axis_program(inputs, mask)), mask)
                     for mask in range(1 << inputs)]
    ax_candidates.sort(key=lambda v: (v[0], v[1].bit_count(), v[1]))
    best_axes = ax_candidates[:top_bases]
    best_score, winner_mask = ax_candidates[0]
    best_program = axis_program(inputs, winner_mask)
    probes = stage_two = 0
    for _, mask in best_axes:
        base = axis_program(inputs, mask)
        transformed = tuple(ab.apply_program(t.target, inputs, base) for t in training)
        choices = [ab.Op("shear", dst, src)
                   for src in range(1 << inputs) for dst in range(1 << inputs)
                   if src != dst]
        if shear_mode == "guided":
            choices.sort(
                key=lambda op: (-ab._shear_signal(transformed, inputs, op.source, op.target),
                                op.source, op.target)
            )
            probes += len(choices) * len(training)
            selected = choices[:per_base]
        else:
            selected = rng.sample(choices, per_base)
        for op in selected:
            candidate = base + (op,)
            score = ab.training_score(training, inputs, candidate)
            stage_two += 1
            if score < best_score:
                best_score, best_program = score, candidate
    return Result(best_program, best_score, winner_mask,
                  len(ax_candidates) + stage_two, probes,
                  len(ax_candidates), stage_two)


def _random_family_control(n: int, program: tuple[ab.Op, ...]) -> dict[str, int]:
    """Previously unused negative-control family, generated after selection.

    This family is neither fresh externally governed evidence nor independent;
    its purpose is to reveal when a grammar favors structured truth tables.
    """
    rng = random.Random(f"representation-random-control|arity={n}|development")
    random_tables = tuple(
        p.tasks.Task(f"rand_{i}", "random_control", n, rng.getrandbits(1 << n))
        for i in range(12)
    )
    return {
        "identity": ab.bits_for(random_tables, n, ()),
        "selected": ab.bits_for(random_tables, n, program),
        "full_mobius": ab.bits_for(
            random_tables, n, axis_program(n, (1 << n) - 1)
        ),
    }


def trial(seeds: tuple[int, ...] = (0, 1, 2)) -> dict:
    rows = []
    for n in range(3, p.MAX_INPUTS + 1):
        train = p.tasks_for(p.FAMILIES_TRAIN, n)
        eval_ = p.tasks_for(p.FAMILIES_EVAL, n)
        for seed in seeds:
            guided = discover(train, n, seed=seed)
            random = discover(train, n, seed=seed, shear_mode="random")
            assert guided.evaluated_candidates == random.evaluated_candidates
            for task in (*train, *eval_):
                enc = ab.apply_program(task.target, n, guided.program)
                restored = ab.invert_program(p.decode(p.encode(enc, n), n), n, guided.program)
                assert restored == task.target
            full = axis_program(n, (1 << n) - 1)
            row = {
                "arity": n,
                "seed": seed,
                "training_tasks": len(train),
                "development_evaluation_tasks": len(eval_),
                "guided_program": [(op.kind, op.target, op.source) for op in guided.program],
                "random_program": [(op.kind, op.target, op.source) for op in random.program],
                "axis_baseline_mask": guided.baseline_mask,
                "guided_training_bits_including_descriptor": guided.train_bits,
                "random_training_bits_including_descriptor": random.train_bits,
                "evaluation_identity_bits": ab.bits_for(eval_, n, ()),
                "evaluation_full_mobius_bits": ab.bits_for(eval_, n, full),
                "evaluation_guided_bits": ab.bits_for(eval_, n, guided.program),
                "evaluation_random_bits": ab.bits_for(eval_, n, random.program),
                "evaluation_guided_including_descriptor": (
                    ab.bits_for(eval_, n, guided.program) +
                    ab.program_descriptor_bits(guided.program, n)
                ),
                "evaluation_random_including_descriptor": (
                    ab.bits_for(eval_, n, random.program) +
                    ab.program_descriptor_bits(random.program, n)
                ),
                "evaluation_full_mobius_including_descriptor": (
                    ab.bits_for(eval_, n, full) +
                    ab.program_descriptor_bits(full, n)
                ),
                "guided_candidates": guided.evaluated_candidates,
                "random_candidates": random.evaluated_candidates,
                "guided_prescreen_probes": guided.prescreen_probes,
                "random_prescreen_probes": random.prescreen_probes,
                "control_random_family_bits": _random_family_control(n, guided.program),
            }
            rows.append(row)
    return {
        "schema": "genesis-macro-search-development-v1",
        "status": "DEVELOPMENT_ONLY_NOT_BLIND",
        "previously_exposed_evaluation_families": p.FAMILIES_EVAL,
        "selection_families": p.FAMILIES_TRAIN,
        "fixed_grammar": ["invertible axis pass", "invertible coordinate shear"],
        "candidate_evaluations_matched_but_prescreen_compute_not_matched": True,
        "evaluation_bits_exclude_descriptor_except_explicit_including_descriptor_fields": True,
        "negative_control_random_family_not_frozen": True,
        "rows": rows,
    }

if __name__ == "__main__":
    print(json.dumps(trial(), indent=2))
