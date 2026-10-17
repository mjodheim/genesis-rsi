"""Unpublished DEVELOPMENT study: learn finite reversible encodings.

Search space extends axis-wise GF(2) butterflies with arbitrary reversible
coordinate shears. Every primitive is hand-provided, not autonomously invented.
Training-only guided and random-control searches consume the same number of
candidate program evaluations, while prescreening work is separately counted.

NOT a new blind task bank, unrestricted grammar invention, general RSI,
or a demonstration of improved recursive successor production.
"""
from __future__ import annotations

from dataclasses import dataclass
import random

from experiment.representation_discovery import prototype as base

@dataclass(frozen=True, order=True)
class Op:
    kind: str
    target: int
    source: int = 0


def encode_op(op: Op, inputs: int) -> int:
    """Code-length proxy for finite, machine-decodable operation descriptors."""
    if op.kind == "axis" and 0 <= op.target < inputs and op.source == 0:
        return inputs.bit_length() + 2
    if (op.kind == "shear" and 0 <= op.target < (1 << inputs)
            and 0 <= op.source < (1 << inputs) and op.source != op.target):
        return 2 * inputs + 2
    raise ValueError("malformed representation operation")


def apply_op(value: int, inputs: int, op: Op) -> int:
    encode_op(op, inputs)
    if op.kind == "axis":
        return base.representation(value, inputs, 1 << op.target)
    return value ^ ((1 << op.target) if ((value >> op.source) & 1) else 0)


def apply_program(table: int, inputs: int, program: tuple[Op, ...]) -> int:
    result = table
    for op in program:
        result = apply_op(result, inputs, op)
    return result


def invert_program(table: int, inputs: int, program: tuple[Op, ...]) -> int:
    result = table
    for op in reversed(program):
        result = apply_op(result, inputs, op)
    return result


def program_descriptor_bits(program: tuple[Op, ...], inputs: int) -> int:
    return 0 if not program else (8 + sum(encode_op(op, inputs) for op in program))


def bits_for(tasks: tuple, inputs: int, program: tuple[Op, ...]) -> int:
    return sum(base.encoding_bits(apply_program(t.target, inputs, program), inputs) for t in tasks)


def training_score(tasks: tuple, inputs: int, program: tuple[Op, ...]) -> int:
    return bits_for(tasks, inputs, program) + program_descriptor_bits(program, inputs)


def _shear_signal(data: tuple[int, ...], inputs: int, source: int, target: int) -> int:
    """Training-only sparsity proxy for prioritizing new primitive hypotheses."""
    joint = source_only = 0
    for table in data:
        if (table >> source) & 1:
            if (table >> target) & 1:
                joint += 1
            else:
                source_only += 1
    return joint - source_only


@dataclass(frozen=True)
class Candidate:
    program: tuple[Op, ...]
    parent: tuple[Op, ...] | None
    score: int
    generation: int


def discover(training: tuple, inputs: int, *,
             strategy: str = "guided",
             seed: int = 0, candidate_limit: int = 64,
             max_generations: int = 5, beam_size: int = 3) -> tuple[Candidate, dict]:
    """Finite search, matched evaluated-candidate budget and auditable receipts.

    Guided prescreen scores ALL shears by co-occurrence. Random does no such
    work, so this is not a matched-total-compute comparison; count all probes.
    """
    if strategy not in ("guided", "random"):
        raise ValueError("unknown search strategy")
    if not (2 <= inputs <= base.MAX_INPUTS):
        raise ValueError("unsupported arity")
    if candidate_limit < 1 or max_generations < 0 or beam_size < 1:
        raise ValueError("invalid search budget")
    rng = random.Random(f"adaptive-basis|{inputs}|{seed}|{strategy}")
    start = Candidate((), None, training_score(training, inputs, ()), 0)
    seen = {(): start}
    beam = [start]
    prescreen_probes = 0
    evaluated_ops = 0
    for generation in range(1, max_generations + 1):
        if len(seen) >= candidate_limit:
            break
        proposed = []
        for parent in beam:
            # Decode only training data; held-out family never reaches this function.
            values = tuple(apply_program(t.target, inputs, parent.program) for t in training)
            axis = [Op("axis", k) for k in range(inputs)]
            shear = [Op("shear", target, source)
                     for source in range(1 << inputs)
                     for target in range(1 << inputs)
                     if target != source]
            if strategy == "guided":
                ranked = sorted(
                    shear,
                    key=lambda op: (-_shear_signal(values, inputs, op.source, op.target),
                                    op.source, op.target),
                )
                prescreen_probes += len(shear) * len(values)
                picks = axis + ranked[:12]
            else:
                picks = axis + rng.sample(shear, min(12, len(shear)))
            for op in picks:
                program = parent.program + (op,)
                # Double-application of the same involution cancels immediately.
                if len(program) >= 2 and program[-1] == program[-2]:
                    continue
                if program in seen or len(seen) >= candidate_limit:
                    continue
                sc = training_score(training, inputs, program)
                evaluated_ops += len(training) * len(program)
                result = Candidate(program, parent.program, sc, generation)
                seen[program] = result
                proposed.append(result)
        if not proposed:
            break
        beam = sorted(
            [*beam, *proposed],
            key=lambda node: (node.score, len(node.program), node.program)
        )[:beam_size]
    winner = min(seen.values(), key=lambda node: (node.score, len(node.program), node.program))
    return winner, {"candidates": seen, "prescreen_probes": prescreen_probes,
                    "evaluated_transform_applications": evaluated_ops}


def trial(*, seeds=(0, 1, 2)) -> dict:
    report = []
    for inputs in range(3, base.MAX_INPUTS + 1):
        train = base.tasks_for(base.FAMILIES_TRAIN, inputs)
        evaluation = base.tasks_for(base.FAMILIES_EVAL, inputs)
        identity = bits_for(evaluation, inputs, ())
        full = tuple(Op("axis", axis) for axis in range(inputs))
        full_bits = bits_for(evaluation, inputs, full)
        for seed in seeds:
            selected, history = discover(train, inputs, strategy="guided", seed=seed)
            random_selected, random_history = discover(
                train, inputs, strategy="random", seed=seed,
                candidate_limit=len(history["candidates"]))
            for t in (*train, *evaluation):
                transformed = apply_program(t.target, inputs, selected.program)
                if invert_program(transformed, inputs, selected.program) != t.target:
                    raise AssertionError("noninvertible operation sequence")
                if invert_program(base.decode(base.encode(transformed, inputs), inputs),
                                  inputs, selected.program) != t.target:
                    raise AssertionError("codec round trip failed")
            report.append({
                "arity": inputs,
                "seed": seed,
                "train_task_count": len(train),
                "evaluation_task_count": len(evaluation),
                "identity_evaluation_bits": identity,
                "full_mobius_evaluation_bits": full_bits,
                "guided_evaluation_bits": bits_for(evaluation, inputs, selected.program),
                "random_evaluation_bits": bits_for(evaluation, inputs, random_selected.program),
                "guided_train_bits_with_descriptor": selected.score,
                "random_train_bits_with_descriptor": random_selected.score,
                "guided_program": [(op.kind, op.target, op.source) for op in selected.program],
                "random_program": [(op.kind, op.target, op.source) for op in random_selected.program],
                "guided_candidate_evaluations": len(history["candidates"]),
                "random_candidate_evaluations": len(random_history["candidates"]),
                "guided_prescreen_probes": history["prescreen_probes"],
                "random_prescreen_probes": random_history["prescreen_probes"],
                "guided_evaluated_transform_applications":
                    history["evaluated_transform_applications"],
                "random_evaluated_transform_applications":
                    random_history["evaluated_transform_applications"],
            })
    return {
        "schema": "genesis-adaptive-basis-development-v1",
        "status": "DEVELOPMENT_ONLY_NOT_BLIND",
        "human_specified_primitives": ["axis", "shear"],
        "seeds": list(seeds),
        "training_families": base.FAMILIES_TRAIN,
        "evaluation_families": base.FAMILIES_EVAL,
        "evaluation_data_previously_exposed": True,
        "metrics_not_measured": ["latency", "CPU", "energy", "general RSI"],
        "rows": report,
    }


if __name__ == "__main__":
    import json
    print(json.dumps(trial(), indent=2))
