"""Procédure d'amélioration héritée : un petit circuit NAND à sorties multiples.

Le circuit lit des traits binaires d'un composant candidat et en déduit sa
priorité (entier, bits de poids fort en premier) et son admission. Les indices
de signaux suivent Component.steps : 0..n_inputs-1 sont les traits, n_inputs+k
est la sortie du pas k. Hors réseau, sans modèle, sans horloge.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Iterable, Sequence

from genesis.trust_root import digest_of

SCHEMA = "genesis-circuit-procedure-v1"
MAX_STEPS = 64
MAX_PRIORITY_BITS = 16


class ProcedureError(ValueError):
    """Procédure invalide, altérée ou mal typée."""


# Traits : fonctions binaires pures de (support, arity, nands, composed), ordre fixe.
TRAITS = (
    ("support>=2", lambda s, a, n, c: s >= 2),
    ("support>=3", lambda s, a, n, c: s >= 3),
    ("support>=4", lambda s, a, n, c: s >= 4),
    ("support>=6", lambda s, a, n, c: s >= 6),
    ("arity==3", lambda s, a, n, c: a == 3),
    ("arity>=4", lambda s, a, n, c: a >= 4),
    ("nands>=2", lambda s, a, n, c: n >= 2),
    ("nands>=4", lambda s, a, n, c: n >= 4),
    ("nands>=6", lambda s, a, n, c: n >= 6),
    ("composed", lambda s, a, n, c: bool(c)),
)
TRAIT_NAMES = tuple(name for name, _ in TRAITS)


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def traits_of(support: int, arity: int, nands: int, composed: bool) -> tuple[int, ...]:
    """Traits binaires d'un candidat ; n'accepte que des entiers ou des booléens."""
    for value in (support, arity, nands, composed):
        if not isinstance(value, int):
            raise TypeError("traits_of n'accepte que des entiers ou des booléens")
    return tuple(int(bool(fn(support, arity, nands, composed))) for _, fn in TRAITS)


@dataclasses.dataclass(frozen=True)
class Procedure:
    n_inputs: int
    steps: tuple
    priority_outputs: tuple
    admit_output: int


def validate(procedure: Procedure) -> None:
    if not isinstance(procedure, Procedure):
        raise ProcedureError("ce n'est pas une Procedure")
    n = procedure.n_inputs
    if not _is_int(n) or n != len(TRAITS):
        raise ProcedureError("n_inputs doit valoir len(TRAITS)")
    if not isinstance(procedure.steps, (tuple, list)) or len(procedure.steps) > MAX_STEPS:
        raise ProcedureError("steps invalide ou circuit trop grand")
    for k, step in enumerate(procedure.steps):
        if not isinstance(step, (tuple, list)) or len(step) != 2 or not all(_is_int(r) for r in step):
            raise ProcedureError(f"pas {k} mal formé")
        if not all(0 <= r < n + k for r in step):
            raise ProcedureError(f"pas {k} : référence hors bornes ou non antérieure")
    total = n + len(procedure.steps)
    outs = procedure.priority_outputs
    if not isinstance(outs, (tuple, list)) or not 2 <= len(outs) <= MAX_PRIORITY_BITS:
        raise ProcedureError("priority_outputs : 2 à 16 indices requis")
    if not all(_is_int(o) and 0 <= o < total for o in outs):
        raise ProcedureError("priority_outputs : sortie invalide")
    if not _is_int(procedure.admit_output) or not 0 <= procedure.admit_output < total:
        raise ProcedureError("admit_output invalide")


def run(procedure: Procedure, traits: Sequence[int]) -> tuple[int, bool, int]:
    """Évalue la procédure ; gate_count = nombre de NAND exécutés."""
    validate(procedure)
    if not isinstance(traits, (tuple, list)) or len(traits) != procedure.n_inputs:
        raise ProcedureError("vecteur de traits de mauvaise longueur")
    if not all(_is_int(t) and t in (0, 1) for t in traits):
        raise ProcedureError("les traits doivent valoir 0 ou 1")
    signals = list(traits)
    for i, j in procedure.steps:
        signals.append(1 - (signals[i] & signals[j]))
    priority = 0
    for o in procedure.priority_outputs:
        priority = (priority << 1) | signals[o]
    return priority, bool(signals[procedure.admit_output]), len(procedure.steps)


def rank(procedure: Procedure, candidates: Iterable[Sequence]) -> list:
    """Candidats (clé, support, arity, nands, composed) admis, triés par priorité
    décroissante puis clé stable ; renvoie [(clé, priorité)]."""
    scored = []
    for key, support, arity, nands, composed in candidates:
        priority, admit, _ = run(procedure, traits_of(support, arity, nands, composed))
        if admit:
            scored.append((key, priority))
    return sorted(scored, key=lambda item: (-item[1], str(item[0])))


def _body(p: Procedure) -> dict:
    return {
        "schema": SCHEMA,
        "traits": list(TRAIT_NAMES),
        "n_inputs": p.n_inputs,
        "steps": [[i, j] for i, j in p.steps],
        "priority_outputs": list(p.priority_outputs),
        "admit_output": p.admit_output,
    }


def to_record(p: Procedure) -> dict:
    validate(p)
    body = _body(p)
    return {**body, "procedure_digest": digest_of(body)}


def from_record(rec: Any) -> Procedure:
    keys = {"schema", "traits", "n_inputs", "steps", "priority_outputs", "admit_output", "procedure_digest"}
    if not isinstance(rec, dict) or set(rec) != keys:
        raise ProcedureError("enregistrement mal formé")
    steps, outs = rec["steps"], rec["priority_outputs"]
    if not isinstance(steps, list) or not isinstance(outs, list) or not all(isinstance(s, list) for s in steps):
        raise ProcedureError("steps ou sorties mal formés")
    p = Procedure(rec["n_inputs"], tuple(tuple(s) for s in steps), tuple(outs), rec["admit_output"])
    validate(p)
    if to_record(p) != rec:
        raise ProcedureError("schéma, traits ou empreinte altérés")
    return p


class _Builder:
    def __init__(self):
        self.steps = []

    def nand(self, a, b):
        self.steps.append((a, b))
        return len(TRAITS) + len(self.steps) - 1

    def not_(self, a):
        return self.nand(a, a)

    def and_(self, a, b):
        return self.not_(self.nand(a, b))

    def or_(self, a, b):
        return self.nand(self.not_(a), self.not_(b))


def seed_procedure() -> Procedure:
    """Approximation grossière : priorité à 2 bits croissante avec le support ; admission si support>=2 et arity<4."""
    b = _Builder()
    s2, s3, s4, a4 = 0, 1, 2, 5
    low = b.or_(b.and_(s2, b.not_(s3)), s4)
    g = b.nand(s2, b.not_(a4))
    admit = b.not_(g)
    return Procedure(len(TRAITS), tuple(b.steps), (s3, low), admit)


def random_procedure(rng: Any, n_steps: int) -> Procedure:
    """Témoin aléatoire valide par construction, reproductible avec la graine de rng."""
    if not _is_int(n_steps) or not 0 <= n_steps <= MAX_STEPS:
        raise ProcedureError("n_steps hors bornes")
    n = len(TRAITS)
    steps = tuple((rng.randrange(n + k), rng.randrange(n + k)) for k in range(n_steps))
    total = n + n_steps
    outs = tuple(rng.randrange(total) for _ in range(3))
    p = Procedure(n, steps, outs, rng.randrange(total))
    validate(p)
    return p


def mutate(procedure: Procedure, rng: Any) -> Procedure:
    """Mutation de portes et de câblage, toujours valide : recâble une entrée d'un pas vers une
    référence antérieure, ajoute ou retire le dernier pas (dans la limite de MAX_STEPS), ou change
    une sortie de priorité ou l'admission. Reproductible avec la graine de rng ; l'original n'est
    pas modifié."""
    validate(procedure)
    n = procedure.n_inputs
    steps = [tuple(step) for step in procedure.steps]
    outs = list(procedure.priority_outputs)
    admit = procedure.admit_output
    operations = ["priority", "admit"]
    if steps:
        operations += ["rewire", "shrink"]
    if len(steps) < MAX_STEPS:
        operations.append("grow")
    operation = rng.choice(operations)
    if operation == "rewire":
        k, side = rng.randrange(len(steps)), rng.randrange(2)
        step = list(steps[k])
        step[side] = rng.randrange(n + k)
        steps[k] = tuple(step)
    elif operation == "grow":
        bound = n + len(steps)
        steps.append((rng.randrange(bound), rng.randrange(bound)))
    elif operation == "shrink":
        steps.pop()
        total = n + len(steps)
        outs = [o if o < total else rng.randrange(total) for o in outs]
        if admit >= total:
            admit = rng.randrange(total)
    elif operation == "priority":
        outs[rng.randrange(len(outs))] = rng.randrange(n + len(steps))
    else:
        admit = rng.randrange(n + len(steps))
    result = Procedure(n, tuple(steps), tuple(outs), admit)
    validate(result)
    return result


def replay_digest(procedure: Procedure, cases: Iterable[Sequence[int]]) -> str:
    """Empreinte des sorties sur une liste fixe de vecteurs de traits."""
    outputs = []
    for case in cases:
        priority, admit, gates = run(procedure, case)
        outputs.append([priority, int(admit), gates])
    return digest_of({"schema": SCHEMA + "-replay", "outputs": outputs})
