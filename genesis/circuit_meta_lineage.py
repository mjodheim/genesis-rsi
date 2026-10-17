"""Lineage of generations for the circuit engine: a library and the procedure that builds it.

A generation state is a JSON-serialisable record: index, library (Engine.record()), procedure
(circuit_procedure.to_record), fingerprint of the parent state, own fingerprint, spending per post,
the flags exhausted and adopted, the fingerprints of the evaluated candidates and the scores.
verify_lineage refuses a chain whose content or parent fingerprint was altered.

step(state, tasks, task_budget, meter, rng) runs in two stages under ONE meter:
(a) the inherited procedure guides engine.improved_by and yields the next library;
(b) the SAME inherited procedure searches the next procedure (the recursion).

Stage (b), choices documented here (fixed by this module, not frozen by any protocol):
- a lot of LOT candidates is drawn from rng; each draw applies one or two successive
  circuit_procedure.mutate calls to the inherited procedure (two means "composed");
- candidates are identified by their procedure_digest; draws equal to the parent are dropped;
- traits come from circuit_procedure.traits_of(support, arity, nands, composed) with
  support = number of draws of the lot with the same digest, capped at SUPPORT_CAP,
  arity = 2 + min(2, 4 * size // (MAX_STEPS + 1)), nands = 1 + min(7, 8 * size // (MAX_STEPS + 1))
  where size is the number of steps of the candidate, composed = the first draw of that digest
  applied two mutations (more than one mutation away from the parent);
- the inherited procedure is run by circuit_procedure.run on these traits, one run per
  distinct candidate, in order of first draw; its gates (one unit per step) are charged to the
  meter before each run and counted in the post "procedure";
- admitted candidates are ordered by decreasing priority (ties keep the order of first draw)
  and the first SEED_PROCEDURE["tried"] of them are evaluated;
- each evaluation plays improved_by with the candidate on the current library and the learning
  tasks, on a share of the remaining meter (remaining // candidates left), charged to the same meter;
- the score is (tasks solved, -evaluations) on the learning tasks only. The parent's score is that
  of stage (a). A candidate whose evaluation ran out of meter is not scored. The best candidate is
  adopted only if its score is strictly above the parent's; otherwise the parent is handed on unchanged.
- when the meter runs out, work stops, nothing is exceeded and the record says exhausted=True.
  When stage (a) is exhausted, stage (b) is skipped (the parent's score would be incomplete).

The baseline evaluation of the current library (stage a, before improved_by) is metered too: it runs
through engine._metered_attempt under the same meter and its evaluations are counted in the post
"evaluations". If the meter cannot pay for one full evaluation, the child keeps the library and the
procedure unchanged, with exhausted=True, adopted=False, score=None and parent_score=None, and
improved_by is not called; such a state passes verify_state.

Limits: the scale of one unit per synthesis NAND is not frozen; the improvement of the improver is not measured here.

Reloaded states: Engine has no from_record, so a state rebuilt from JSON carries no live library and
step refuses it with LineageError (it can still be verified). verify_state checks the types and shapes
of every field (booleans, list of strings, scores as None or two integers, library as a list of component records),
but the library is NOT reconstructed: only the integrity of the digest, the chain and the field shapes
are guaranteed, not that the library content is a genuine Engine record.
"""

import json
import random

from genesis import circuit_engine as engine
from genesis import circuit_procedure as cp
from genesis import circuit_tasks as ctasks
from genesis.circuit_engine import Engine, Meter
from genesis.trust_root import digest_of

SCHEMA = "genesis-circuit-meta-lineage-v1"
POSTS = ("procedure", "synthesis", "evaluations")
LOT = 16
SUPPORT_CAP = 8
FIELDS = frozenset(
    ("schema", "index", "library", "procedure", "parent", "digest", "spent", "exhausted", "adopted", "evaluated", "parent_score", "score")
)


class LineageError(ValueError):
    """A state, a chain or an argument is refused."""


class State(dict):
    """A state record; ``engine`` is the live library and is not part of the record."""

    engine = None


class _Share(Meter):
    """A slice of a parent meter: every unit spent here is charged to the parent as well."""

    def __init__(self, parent, limit):
        super().__init__(limit)
        self._parent = parent

    def charge(self, amount):
        if not super().charge(amount):
            return False
        if not self._parent.charge(amount):
            raise LineageError("a share went past its parent meter")
        return True


def _plain(value):
    try:
        return json.loads(json.dumps(value, sort_keys=True))
    except (TypeError, ValueError) as error:
        raise LineageError(f"not serialisable: {error}") from error


def _seal(body, live):
    content = _plain({key: value for key, value in body.items() if key != "digest"})
    state = State(content)
    state["digest"] = digest_of(content)
    state.engine = live
    return state


def seal(body):
    """State made of ``body`` (its digest, if any, is recomputed)."""
    return _seal(body, None)


def initial_state():
    """Generation 0: empty library, ancestral (seed) procedure, no parent."""
    live = Engine()
    return _seal(
        {
            "schema": SCHEMA,
            "index": 0,
            "library": live.record(),
            "procedure": cp.to_record(cp.seed_procedure()),
            "parent": None,
            "spent": dict.fromkeys(POSTS, 0),
            "exhausted": False,
            "adopted": False,
            "evaluated": [],
            "parent_score": None,
            "score": None,
        },
        live,
    )


def verify_state(state):
    """Refuse a state whose fields, own fingerprint, spending or procedure are not sound."""
    if not isinstance(state, dict) or set(state) != FIELDS or state["schema"] != SCHEMA:
        raise LineageError("unexpected state fields")
    body = {key: value for key, value in state.items() if key != "digest"}
    recomputed = digest_of(_plain(body))
    if recomputed != state["digest"]:
        raise LineageError(
            "own fingerprint does not match the content: "
            f"stored={state['digest']!r}, recomputed={recomputed!r}"
        )
    index, spent = state["index"], state["spent"]
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        raise LineageError("bad index")
    if not isinstance(spent, dict) or set(spent) != set(POSTS):
        raise LineageError("bad spending posts")
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in spent.values()):
        raise LineageError("bad spending")
    for flag in ("adopted", "exhausted"):
        if not isinstance(state[flag], bool):
            raise LineageError(f"{flag} must be a boolean")
    evaluated = state["evaluated"]
    if not isinstance(evaluated, list) or not all(isinstance(item, str) for item in evaluated):
        raise LineageError("evaluated must be a list of strings")
    for name in ("score", "parent_score"):
        value = state[name]
        if value is None:
            continue
        if not (isinstance(value, list) and len(value) == 2 and all(isinstance(item, int) and not isinstance(item, bool) for item in value)):
            raise LineageError(f"{name} must be None or a list of two integers")
    library = state["library"]
    if not isinstance(library, list) or not all(isinstance(item, dict) for item in library):
        raise LineageError("library must be a list of dictionaries")
    _plain(library)
    try:
        cp.from_record(state["procedure"])
    except cp.ProcedureError as error:
        raise LineageError(f"procedure refused: {error}") from error


def verify_lineage(states):
    """True if every state is sound, indices are consecutive and each parent fingerprint is the previous digest."""
    previous = None
    for position, state in enumerate(states):
        verify_state(state)
        if position == 0:
            if state["index"] != 0 or state["parent"] is not None:
                raise LineageError(
                    "the first generation must have index 0 and no parent (it must be a root): "
                    f"index={state['index']!r}, parent={state['parent']!r}"
                )
        elif state["index"] != previous["index"] + 1 or state["parent"] != previous["digest"]:
            raise LineageError(f"generation {state['index']} does not descend from its predecessor")
        previous = state
    return True


def _engine_of(state):
    live = getattr(state, "engine", None)
    if live is None:
        raise LineageError(
            "no live library for this state: Engine has no from_record, "
            "so a state reloaded from JSON cannot be stepped"
        )
    if _plain(live.record()) != state["library"]:
        raise LineageError("the library does not match its record")
    return live


def _learn_tasks(tasks):
    given = list(tasks)
    if not given:
        raise LineageError("no task given")
    refused = set(ctasks.HELD_OUT) | set(getattr(ctasks, "CONTROL", ()))
    allowed = set(ctasks.LEARN)
    for task in given:
        if task.family in refused or task.family not in allowed:
            raise LineageError(f"task {task.name!r} (family {task.family!r}) is not a learning task")
    return given


def _count(name, value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LineageError(f"{name} must be a non-negative integer")
    return value


def _score(solutions):
    solved, evaluations = engine.measure(solutions)
    return (solved, -evaluations)


def _traits(size, count, composed):
    arity = 2 + min(2, 4 * size // (cp.MAX_STEPS + 1))
    nands = 1 + min(7, 8 * size // (cp.MAX_STEPS + 1))
    return cp.traits_of(min(count, SUPPORT_CAP), arity, nands, composed)


def _add(spent, charged):
    for post in POSTS:
        spent[post] += charged.get(post, 0)


def _lot(parent, parent_digest, rng):
    """Distinct candidates in order of first draw: digest -> [candidate, composed, draws]."""
    lot = {}
    for _ in range(LOT):
        depth = 1 + rng.randrange(2)
        candidate = parent
        for _ in range(depth):
            candidate = cp.mutate(candidate, rng)
        digest = cp.to_record(candidate)["procedure_digest"]
        if digest == parent_digest:
            continue
        if digest in lot:
            lot[digest][2] += 1
        else:
            lot[digest] = [candidate, depth > 1, 1]
    return lot


def step(state, tasks, task_budget, meter, rng):
    """Next generation state (see the module docstring); never spends past ``meter``.

    exhausted=True is also set when the share (remaining // candidates left) given to one candidate
    runs out, even if the global meter still has budget.

    Asymmetry: the parent is evaluated (stage a) on the whole meter, each candidate only on a share
    of what remains. The comparison is therefore conservative against the candidates: a candidate is
    adopted only if it beats the parent despite the smaller budget.
    """
    learn = _learn_tasks(tasks)
    _count("task_budget", task_budget)
    verify_state(state)
    current = _engine_of(state)
    parent = cp.from_record(state["procedure"])
    generation = state["index"] + 1
    started = meter.spent
    spent = dict.fromkeys(POSTS, 0)
    spent_eval = {"evaluations": 0}
    baseline = engine._metered_attempt(current, learn, task_budget, meter, spent_eval)
    spent["evaluations"] += spent_eval["evaluations"]
    if baseline is None:
        if sum(spent.values()) != meter.spent - started:
            raise LineageError("the posts do not add up to what the meter was charged")
        return _seal(
            {
                "schema": SCHEMA,
                "index": generation,
                "library": current.record(),
                "procedure": state["procedure"],
                "parent": state["digest"],
                "spent": spent,
                "exhausted": True,
                "adopted": False,
                "evaluated": [],
                "parent_score": None,
                "score": None,
            },
            current,
        )
    library, after, info = engine.improved_by(current, learn, task_budget, baseline, parent, meter, generation=generation)
    _add(spent, info["spent"])
    exhausted = bool(info["exhausted"])
    parent_score = _score(after)
    chosen, chosen_score, evaluated = parent, parent_score, []
    if not exhausted:
        lot = _lot(parent, state["procedure"]["procedure_digest"], rng)
        admitted = []
        for digest, (candidate, composed, draws) in lot.items():
            if not meter.charge(len(parent.steps)):
                exhausted = True
                break
            spent["procedure"] += len(parent.steps)
            priority, admit, _ = cp.run(parent, _traits(len(candidate.steps), draws, composed))
            if admit:
                admitted.append((priority, digest, candidate))
        admitted.sort(key=lambda item: -item[0])
        shortlist = admitted[: engine.SEED_PROCEDURE["tried"]]
        for position, (_, digest, candidate) in enumerate(shortlist):
            if meter.remaining <= 0:
                exhausted = True
                break
            share = _Share(meter, meter.remaining // (len(shortlist) - position))
            _, got, trial = engine.improved_by(current, learn, task_budget, baseline, candidate, share, generation=generation)
            _add(spent, trial["spent"])
            evaluated.append(digest)
            if trial["exhausted"]:
                exhausted = True
            elif _score(got) > chosen_score:
                chosen, chosen_score = candidate, _score(got)
    if sum(spent.values()) != meter.spent - started:
        raise LineageError("the posts do not add up to what the meter was charged")
    return _seal(
        {
            "schema": SCHEMA,
            "index": generation,
            "library": library.record(),
            "procedure": cp.to_record(chosen),
            "parent": state["digest"],
            "spent": spent,
            "exhausted": exhausted,
            "adopted": chosen is not parent,
            "evaluated": evaluated,
            "parent_score": list(parent_score),
            "score": list(chosen_score),
        },
        library,
    )


def run_lineage(generations, tasks, task_budget, per_generation_limit, seed):
    """States of generations 0..generations, from Engine() and the seed procedure.

    Only learning tasks are accepted (a HELD_OUT or CONTROL family raises LineageError). Each
    generation has its own Meter(per_generation_limit) and rng = Random(f"meta|{seed}|{index}"),
    index being the index of the parent state; library AND procedure are handed on.
    """
    _count("generations", generations)
    _count("per_generation_limit", per_generation_limit)
    learn = _learn_tasks(tasks)
    states = [initial_state()]
    for index in range(generations):
        rng = random.Random(f"meta|{seed}|{index}")
        states.append(step(states[-1], learn, task_budget, Meter(per_generation_limit), rng))
    return states


def replace_procedure(state, procedure):
    """Same state with another procedure (e.g. the ancestral one); the library is untouched.

    The result is re-sealed, so it is a sibling of ``state``: same index and parent, new fingerprint.

    The selection outcome described the procedure that was replaced, so adopted, evaluated, score and
    parent_score are reset to neutral values (False, [], None, None). spent and exhausted are kept as
    they are: they describe the generation that was built, not the replacing procedure.
    """
    cp.validate(procedure)
    verify_state(state)
    body = dict(state)
    body["procedure"] = cp.to_record(procedure)
    body["adopted"] = False
    body["evaluated"] = []
    body["score"] = None
    body["parent_score"] = None
    return _seal(body, getattr(state, "engine", None))
