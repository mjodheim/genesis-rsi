"""Container side of the self-improving improver: tasks, their scores, and the run of one improver.

This file is copied into a container without network and run there next to model-written code.
It uses the standard library only and never imports Genesis.

A *task* asks for a Python program and scores it. Twelve families of ordinary tasks ask for
``solve(instance)``; each draws its instances from a seed, has a trivial baseline answer and a
cost to minimise. The quality of a program on one instance is ``1 - cost / baseline cost``,
floored at zero; an invalid answer, an exception or a timeout scores zero. One more family,
``improver``, asks for an improver itself and scores it by the quality of what it returns on
ordinary tasks: an improver handed that task is improving improvers, its own source included.

An *improver* is a module defining ``improve(task, lm, budget) -> str``. ``task`` gives a
description, an initial program and ``evaluate(source)``; ``lm(prompt)`` asks the language model,
which lives outside the container and is reached over the standard streams; ``budget`` says what
is left. The host counts every model request and scores what is returned again, in a fresh
container, on instances the improver never saw: nothing computed here is trusted there.

    run         one improver on one task; requests to the model go out as JSON lines
    score       qualities of one program on given seeds
"""
from __future__ import annotations

import json
import math
import os
import random
import resource
import subprocess
import sys
import threading
import time

SOLVE_SECONDS = 2.0
MEMORY_BYTES = 1 << 30
FAMILIES: dict = {}


def family(name: str, role: str, description: str):
    def register(cls):
        FAMILIES[name] = {"role": role, "description": description.strip(), "gen": cls.gen, "cost": cls.cost,
                          "baseline": cls.baseline}
        return cls
    return register


def _rng(name: str, seed: int) -> random.Random:
    return random.Random(f"{name}|{seed}")


def _permutation(answer, n: int) -> list:
    answer = [int(item) for item in answer]
    if sorted(answer) != list(range(n)):
        raise ValueError("not a permutation of the indices")
    return answer


@family("tsp", "development", """
Travelling salesman. `instance["points"]` is a list of [x, y]. Return a list with every point index
exactly once; the cost is the length of the closed tour in that order.""")
class _Tsp:
    @staticmethod
    def gen(seed):
        rng = _rng("tsp", seed)
        return {"points": [[rng.randrange(1000), rng.randrange(1000)] for _ in range(100)]}, None

    @staticmethod
    def cost(public, secret, answer):
        points = public["points"]
        order = _permutation(answer, len(points))
        return sum(math.dist(points[a], points[b]) for a, b in zip(order, order[1:] + order[:1]))

    @staticmethod
    def baseline(public):
        return list(range(len(public["points"])))


@family("binpack", "development", """
Bin packing. `instance["items"]` is a list of integer sizes and `instance["capacity"]` the size of a bin.
Return a list of bins, each a list of item indices; every item appears once and no bin exceeds the
capacity. The cost is the number of bins.""")
class _BinPack:
    @staticmethod
    def gen(seed):
        rng = _rng("binpack", seed)
        return {"capacity": 150, "items": [rng.randrange(20, 101) for _ in range(120)]}, None

    @staticmethod
    def cost(public, secret, answer):
        items = public["items"]
        bins = [[int(i) for i in group] for group in answer if len(group)]
        _permutation([i for group in bins for i in group], len(items))
        if any(sum(items[i] for i in group) > public["capacity"] for group in bins):
            raise ValueError("a bin exceeds the capacity")
        return len(bins)

    @staticmethod
    def baseline(public):
        return [[i] for i in range(len(public["items"]))]


@family("coloring", "development", """
Graph colouring. `instance["n"]` vertices, `instance["edges"]` a list of [u, v]. Return a list of n integers,
the colour of each vertex; adjacent vertices must differ. The cost is the number of distinct colours.""")
class _Coloring:
    @staticmethod
    def gen(seed):
        rng = _rng("coloring", seed)
        n = 70
        return {"n": n, "edges": [[u, v] for u in range(n) for v in range(u + 1, n) if rng.random() < 0.2]}, None

    @staticmethod
    def cost(public, secret, answer):
        colours = [int(item) for item in answer]
        if len(colours) != public["n"] or any(colours[u] == colours[v] for u, v in public["edges"]):
            raise ValueError("not a proper colouring")
        return len(set(colours))

    @staticmethod
    def baseline(public):
        return list(range(public["n"]))


@family("tardiness", "development", """
Single machine scheduling. `instance["jobs"]` is a list of [duration, due date, weight]. Return the job indices
in processing order; the cost is 1 plus the sum over jobs of weight * max(0, completion time - due date).""")
class _Tardiness:
    @staticmethod
    def gen(seed):
        rng = _rng("tardiness", seed)
        jobs = [[rng.randrange(1, 30), 0, rng.randrange(1, 10)] for _ in range(50)]
        total = sum(job[0] for job in jobs)
        for job in jobs:
            job[1] = rng.randrange(job[0], max(job[0] + 1, int(total * 0.6)))
        return {"jobs": jobs}, None

    @staticmethod
    def cost(public, secret, answer):
        jobs, clock, late = public["jobs"], 0, 0
        for index in _permutation(answer, len(jobs)):
            clock += jobs[index][0]
            late += jobs[index][2] * max(0, clock - jobs[index][1])
        return 1 + late

    @staticmethod
    def baseline(public):
        return list(range(len(public["jobs"])))


def _expression(rng: random.Random, depth: int):
    if depth == 0 or rng.random() < 0.2:
        return rng.choice([("x", 0), ("x", 1), ("c", round(rng.uniform(-3, 3), 2))])
    kind = rng.choice(["add", "mul", "sin", "sq", "add", "mul"])
    if kind in ("sin", "sq"):
        return (kind, _expression(rng, depth - 1))
    return (kind, _expression(rng, depth - 1), _expression(rng, depth - 1))


def _value(node, x) -> float:
    kind = node[0]
    if kind == "x":
        return x[node[1]]
    if kind == "c":
        return node[1]
    if kind == "sin":
        return math.sin(_value(node[1], x))
    if kind == "sq":
        return _value(node[1], x) ** 2
    left, right = _value(node[1], x), _value(node[2], x)
    return left + right if kind == "add" else left * right


@family("regression", "development", """
Regression. `instance["train"]` is a list of [x0, x1, y] and `instance["queries"]` a list of [x0, x1]. The y
values come from one unknown formula built from +, *, sin, squares and constants, with slight noise. Return
a list with one predicted y per query; the cost is the mean squared error.""")
class _Regression:
    @staticmethod
    def gen(seed):
        rng = _rng("regression", seed)
        formula = _expression(rng, 3)
        draw = lambda: [round(rng.uniform(-2, 2), 3), round(rng.uniform(-2, 2), 3)]  # noqa: E731
        train = [draw() for _ in range(80)]
        queries = [draw() for _ in range(40)]
        return ({"train": [[*x, round(_value(formula, x) + rng.gauss(0, 0.02), 4)] for x in train], "queries": queries},
                [_value(formula, x) for x in queries])

    @staticmethod
    def cost(public, secret, answer):
        predicted = [float(item) for item in answer]
        if len(predicted) != len(secret) or not all(math.isfinite(item) for item in predicted):
            raise ValueError("one finite prediction per query is required")
        return 1e-6 + sum((a - b) ** 2 for a, b in zip(predicted, secret)) / len(secret)

    @staticmethod
    def baseline(public):
        mean = sum(row[2] for row in public["train"]) / len(public["train"])
        return [mean] * len(public["queries"])


@family("qap", "development", """
Quadratic assignment. `instance["flow"]` and `instance["distance"]` are n x n matrices. Return a list p with
every location index exactly once (facility i goes to location p[i]); the cost is the sum over i, j of
flow[i][j] * distance[p[i]][p[j]].""")
class _Qap:
    @staticmethod
    def gen(seed):
        rng = _rng("qap", seed)
        n = 25
        square = lambda top: [[0 if i == j else rng.randrange(top) for j in range(n)] for i in range(n)]  # noqa: E731
        return {"flow": square(10), "distance": square(100)}, None

    @staticmethod
    def cost(public, secret, answer):
        flow, distance = public["flow"], public["distance"]
        p = _permutation(answer, len(flow))
        return 1 + sum(flow[i][j] * distance[p[i]][p[j]] for i in range(len(p)) for j in range(len(p)))

    @staticmethod
    def baseline(public):
        return list(range(len(public["flow"])))


@family("maxcut", "held_out", """
Maximum cut. `instance["n"]` vertices, `instance["edges"]` a list of [u, v, weight]. Return a list of n values,
each 0 or 1, the side of each vertex; the cost is 1 plus the total weight of the edges that are NOT cut.""")
class _MaxCut:
    @staticmethod
    def gen(seed):
        rng = _rng("maxcut", seed)
        n = 80
        return {"n": n, "edges": [[u, v, rng.randrange(1, 11)] for u in range(n) for v in range(u + 1, n)
                                  if rng.random() < 0.1]}, None

    @staticmethod
    def cost(public, secret, answer):
        side = [int(item) for item in answer]
        if len(side) != public["n"] or any(item not in (0, 1) for item in side):
            raise ValueError("one side, 0 or 1, per vertex is required")
        return 1 + sum(weight for u, v, weight in public["edges"] if side[u] == side[v])

    @staticmethod
    def baseline(public):
        return [0] * public["n"]


@family("setcover", "held_out", """
Set cover. `instance["universe"]` is the number of elements (0..universe-1) and `instance["sets"]` a list of
lists of elements. Return a list of set indices whose union is the whole universe; the cost is how many.""")
class _SetCover:
    @staticmethod
    def gen(seed):
        rng = _rng("setcover", seed)
        universe = 150
        sets = [sorted(rng.sample(range(universe), rng.randrange(5, 25))) for _ in range(70)]
        for element in range(universe):
            if not any(element in group for group in sets):
                sets[rng.randrange(len(sets))].append(element)
        return {"universe": universe, "sets": sets}, None

    @staticmethod
    def cost(public, secret, answer):
        chosen = sorted({int(item) for item in answer})
        if any(not 0 <= item < len(public["sets"]) for item in chosen):
            raise ValueError("unknown set")
        if len({element for item in chosen for element in public["sets"][item]}) != public["universe"]:
            raise ValueError("the universe is not covered")
        return len(chosen)

    @staticmethod
    def baseline(public):
        return list(range(len(public["sets"])))


@family("knapsack", "held_out", """
Multi-dimensional knapsack. `instance["items"]` is a list of [value, w0, w1, w2] and `instance["capacity"]` is
[c0, c1, c2]. Return a list of distinct item indices whose total weight respects every capacity; the cost is
1 plus the total value of the items left out.""")
class _Knapsack:
    @staticmethod
    def gen(seed):
        rng = _rng("knapsack", seed)
        items = [[rng.randrange(10, 100), rng.randrange(5, 40), rng.randrange(5, 40), rng.randrange(5, 40)]
                 for _ in range(60)]
        return {"items": items, "capacity": [sum(item[d] for item in items) // 3 for d in (1, 2, 3)]}, None

    @staticmethod
    def cost(public, secret, answer):
        items = public["items"]
        chosen = sorted({int(item) for item in answer})
        if len(chosen) != len(list(answer)) or any(not 0 <= item < len(items) for item in chosen):
            raise ValueError("distinct known items are required")
        if any(sum(items[i][d] for i in chosen) > public["capacity"][d - 1] for d in (1, 2, 3)):
            raise ValueError("a capacity is exceeded")
        return 1 + sum(item[0] for item in items) - sum(items[i][0] for i in chosen)

    @staticmethod
    def baseline(public):
        return []


@family("jobshop", "held_out", """
Job shop. `instance["jobs"]` is a list of jobs, each a list of [machine, duration] operations to run in that
order. Return a list of job indices in which job j appears once per operation of job j: reading it left to
right, each occurrence schedules the next operation of that job as early as its machine and its job allow.
The cost is the makespan.""")
class _JobShop:
    @staticmethod
    def gen(seed):
        rng = _rng("jobshop", seed)
        machines = 6
        return {"jobs": [[[machine, rng.randrange(1, 20)] for machine in rng.sample(range(machines), machines)]
                         for _ in range(8)]}, None

    @staticmethod
    def cost(public, secret, answer):
        jobs = public["jobs"]
        sequence = [int(item) for item in answer]
        if sorted(sequence) != sorted(j for j, job in enumerate(jobs) for _ in job):
            raise ValueError("each job must appear once per operation")
        step, job_free, machine_free = [0] * len(jobs), [0] * len(jobs), {}
        for j in sequence:
            machine, duration = jobs[j][step[j]]
            end = max(job_free[j], machine_free.get(machine, 0)) + duration
            job_free[j] = machine_free[machine] = end
            step[j] += 1
        return max(job_free)

    @staticmethod
    def baseline(public):
        return [j for j, job in enumerate(public["jobs"]) for _ in job]


@family("cluster", "held_out", """
Clustering. `instance["points"]` is a list of [x, y] and `instance["k"]` the number of clusters. Return a list
with one label in 0..k-1 per point; the cost is 1 plus the sum of squared distances of the points to the
mean of their cluster.""")
class _Cluster:
    @staticmethod
    def gen(seed):
        rng = _rng("cluster", seed)
        centres = [[rng.uniform(0, 100), rng.uniform(0, 100)] for _ in range(6)]
        points = [[round(rng.gauss(c[0], 9), 2), round(rng.gauss(c[1], 9), 2)] for c in centres for _ in range(25)]
        rng.shuffle(points)
        return {"points": points, "k": 6}, None

    @staticmethod
    def cost(public, secret, answer):
        points, labels = public["points"], [int(item) for item in answer]
        if len(labels) != len(points) or any(not 0 <= item < public["k"] for item in labels):
            raise ValueError("one label in 0..k-1 per point is required")
        total = 1.0
        for label in set(labels):
            members = [p for p, own in zip(points, labels) if own == label]
            cx, cy = sum(p[0] for p in members) / len(members), sum(p[1] for p in members) / len(members)
            total += sum((p[0] - cx) ** 2 + (p[1] - cy) ** 2 for p in members)
        return total

    @staticmethod
    def baseline(public):
        return [0] * len(public["points"])


@family("sequence", "held_out", """
Sequence prediction. `instance["prefix"]` holds the first terms of an integer sequence produced by one hidden
rule (a polynomial, a linear recurrence, a geometric rule, or two such sequences interleaved) and
`instance["count"]` says how many further terms to predict. Return that many integers; the cost is 1 plus the
sum over the predicted terms of min(|error|, 1000).""")
class _Sequence:
    @staticmethod
    def _one(rng, length):
        kind = rng.choice(["poly", "recurrence", "geometric"])
        if kind == "poly":
            c = [rng.randrange(-5, 6) for _ in range(rng.randrange(2, 5))]
            return [sum(k * n ** i for i, k in enumerate(c)) for n in range(length)]
        if kind == "geometric":
            a, r, b = rng.randrange(1, 5), rng.choice([2, 3, -2]), rng.randrange(-5, 6)
            return [a * r ** min(n, 40) + b * n for n in range(length)]
        order = rng.randrange(2, 4)
        c, terms = [rng.choice([-2, -1, 1, 1, 2]) for _ in range(order)], [rng.randrange(-3, 4) for _ in range(order)]
        while len(terms) < length:
            terms.append(sum(k * t for k, t in zip(c, terms[-order:])))
        return terms[:length]

    @staticmethod
    def gen(seed):
        rng = _rng("sequence", seed)
        length, count = 24, 8
        if rng.random() < 0.3:
            first, second = _Sequence._one(rng, length), _Sequence._one(rng, length)
            terms = [item for pair in zip(first, second) for item in pair][:length]
        else:
            terms = _Sequence._one(rng, length)
        return {"prefix": terms[:length - count], "count": count}, terms[length - count:]

    @staticmethod
    def cost(public, secret, answer):
        predicted = [int(item) for item in answer]
        if len(predicted) != len(secret):
            raise ValueError("wrong number of terms")
        return 1 + sum(min(abs(a - b), 1000) for a, b in zip(predicted, secret))

    @staticmethod
    def baseline(public):
        return [0] * public["count"]


# --------------------------------------------------------------------------- scoring one program

# The program runs in a process that holds neither this module nor the hidden answers: it receives the
# public instances and gives its answers back; costs are computed here. The runtime file stays readable
# inside the container, so a program naming it is refused and promoted improvers are to be read.
FORBIDDEN = ("improver_runtime",)
_SOLVER = r"""
import json, signal, sys
request = json.loads(sys.stdin.read())
out, sys.stdout = sys.stdout, sys.stderr
class Deadline(BaseException): pass
def alarm(signum, frame): raise Deadline()
signal.signal(signal.SIGALRM, alarm)
rows = []
try:
    namespace = {"__name__": "solution"}
    exec(compile(request["source"], "solution.py", "exec"), namespace)
    solve = namespace["solve"]
except BaseException as error:
    rows = [{"error": f"{type(error).__name__}: {error}"[:300]} for _ in request["instances"]]
else:
    for instance in request["instances"]:
        signal.setitimer(signal.ITIMER_REAL, request["seconds"])
        try:
            answer = solve(instance)
            signal.setitimer(signal.ITIMER_REAL, 0)
            json.dumps(answer)
            rows.append({"answer": answer})
        except Deadline:
            rows.append({"error": "timeout after %g s" % request["seconds"]})
        except BaseException as error:
            rows.append({"error": f"{type(error).__name__}: {error}"[:300]})
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
out.write(json.dumps(rows))
"""


def _limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))


def evaluated(source: str, name: str, seeds: list) -> list:
    """Qualities of ``source`` on ``seeds``: quality in [0, 1] per instance, and what went wrong at zero."""
    failed = lambda why: [{"seed": seed, "quality": 0.0, "cost": None, "error": why} for seed in seeds]  # noqa: E731
    if not isinstance(source, str) or len(source) > 200_000:
        return failed("the program must be text of at most 200000 characters")
    if any(word in source for word in FORBIDDEN):
        return failed("the program may not reach into the scoring runtime")
    spec = FAMILIES[name]
    instances = [spec["gen"](seed) for seed in seeds]
    try:
        done = subprocess.run([sys.executable, "-I", "-c", _SOLVER], preexec_fn=_limits,
                              input=json.dumps({"source": source, "instances": [public for public, _ in instances],
                                                "seconds": SOLVE_SECONDS}),
                              capture_output=True, text=True, timeout=len(seeds) * (SOLVE_SECONDS + 1) + 10)
        answers = json.loads(done.stdout)
        if len(answers) != len(seeds):
            raise ValueError
    except subprocess.TimeoutExpired:
        return failed("timeout")
    except ValueError:
        return failed("the program ended without a result")
    rows = []
    for seed, (public, secret), given in zip(seeds, instances, answers):
        row = {"seed": seed, "quality": 0.0, "cost": None, "error": given.get("error")}
        if row["error"] is None:
            try:
                base = spec["cost"](public, secret, spec["baseline"](public))
                cost = float(spec["cost"](public, secret, given["answer"]))
                if not math.isfinite(cost):
                    raise ValueError("cost is not finite")
                row.update(quality=round(max(0.0, 1 - cost / base), 6), cost=round(cost, 4))
            except Exception as error:  # noqa: BLE001 - an invalid answer scores zero
                row["error"] = f"{type(error).__name__}: {error}"[:300]
        rows.append(row)
    return rows


def baseline_source(name: str) -> str:
    return ("def solve(instance):\n    # trivial answer: quality 0 by definition\n"
            + {"tsp": "    return list(range(len(instance['points'])))",
               "binpack": "    return [[i] for i in range(len(instance['items']))]",
               "coloring": "    return list(range(instance['n']))",
               "tardiness": "    return list(range(len(instance['jobs'])))",
               "regression": ("    mean = sum(row[2] for row in instance['train']) / len(instance['train'])\n"
                              "    return [mean] * len(instance['queries'])"),
               "qap": "    return list(range(len(instance['flow'])))",
               "maxcut": "    return [0] * instance['n']",
               "setcover": "    return list(range(len(instance['sets'])))",
               "knapsack": "    return []",
               "jobshop": "    return [j for j, job in enumerate(instance['jobs']) for _ in job]",
               "cluster": "    return [0] * len(instance['points'])",
               "sequence": "    return [0] * instance['count']"}[name] + "\n")


# --------------------------------------------------------------------------- the model, over a stream

class BudgetExhausted(RuntimeError):
    """No model request or evaluation is left."""


class Link:
    """Requests and answers as JSON lines over two streams; safe to use from several threads."""

    def __init__(self, reader, writer):
        self.reader, self.writer = reader, writer
        self.lock, self.waiting, self.count = threading.Lock(), {}, 0
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        for line in self.reader:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            slot = self.waiting.pop(message.get("id"), None)
            if slot:
                slot[1].append(message)
                slot[0].set()
        for slot in list(self.waiting.values()):
            slot[0].set()

    def send(self, message: dict) -> None:
        with self.lock:
            self.writer.write(json.dumps(message) + "\n")
            self.writer.flush()

    def ask(self, payload: dict) -> dict:
        with self.lock:
            self.count += 1
            identity = self.count
            slot = (threading.Event(), [])
            self.waiting[identity] = slot
            self.writer.write(json.dumps({"id": identity, **payload}) + "\n")
            self.writer.flush()
        slot[0].wait()
        if not slot[1]:
            raise BudgetExhausted("the model is no longer reachable")
        return slot[1][0]


class Budget:
    """What one run may still spend. The host enforces the model requests whatever is counted here."""

    def __init__(self, lm_calls: int, evaluations: int, seconds: float):
        self.lm_calls, self.evaluations, self.seconds = lm_calls, evaluations, seconds
        self.lm_calls_used = self.evaluations_used = 0
        self._started, self._lock = time.monotonic(), threading.Lock()

    @property
    def lm_calls_left(self) -> int:
        return max(0, self.lm_calls - self.lm_calls_used)

    @property
    def evaluations_left(self) -> int:
        return max(0, self.evaluations - self.evaluations_used)

    @property
    def seconds_left(self) -> float:
        return max(0.0, self.seconds - (time.monotonic() - self._started))

    def take(self, what: str, amount: int = 1) -> None:
        with self._lock:
            if getattr(self, what) - getattr(self, what + "_used") < amount:
                raise BudgetExhausted(f"no {what} left")
            setattr(self, what + "_used", getattr(self, what + "_used") + amount)


class Result:
    """What one evaluation says: a score (mean quality, higher is better) and readable details."""

    def __init__(self, score: float, details: str):
        self.score, self.details = score, details

    def __repr__(self):
        return f"Result(score={self.score!r})"


class Task:
    """What an improver is given. ``evaluate`` costs one evaluation of the budget."""

    def __init__(self, spec: dict, budget: Budget, link: Link):
        self.spec, self.budget, self.link = spec, budget, link
        self.family = spec["family"]
        if self.family == "improver":
            self.description = IMPROVER_DESCRIPTION.format(
                tasks=len(spec["children"]), families=", ".join(sorted({child["family"] for child in spec["children"]})),
                calls=spec["child_budget"]["lm_calls"], evaluations=spec["child_budget"]["evaluations"],
                run=len(spec["children"]) * spec["child_budget"]["lm_calls"])
            self.initial = spec["initial"]
        else:
            self.description = (FAMILIES[self.family]["description"] + "\n\n" + SOLVER_RULES)
            self.initial = baseline_source(self.family)

    def evaluate(self, source: str) -> Result:
        self.budget.take("evaluations")
        if self.family == "improver":
            return _improver_result(source, self.spec, self.budget, self.link)
        rows = evaluated(source, self.family, self.spec["visible"])
        return Result(sum(row["quality"] for row in rows) / len(rows),
                      "\n".join(f"instance {index}: quality {row['quality']}" + (f", cost {row['cost']}" if row["error"] is None
                                else f", {row['error']}") for index, row in enumerate(rows)))

    def utility(self, source: str) -> float:
        return self.evaluate(source).score


SOLVER_RULES = (
    "Write a Python module (standard library only) defining `solve(instance)`. It is run on several instances of "
    f"the same kind, {SOLVE_SECONDS:g} seconds each on one core; a timeout, an exception or an invalid answer scores 0 on that "
    "instance. The score is the mean over instances of 1 - cost / (cost of the trivial answer), so higher is better.")

IMPROVER_DESCRIPTION = """
The program to improve is itself an improver: a Python module (standard library only) defining
`improve(task, lm, budget) -> str`, which returns the source of a better program for `task`.

What an improver receives:
- `task.description` (text), `task.initial` (source of a valid starting program);
- `task.evaluate(source)` returns an object with `.score` (higher is better) and `.details` (text: per-instance
  results and error messages); `task.utility(source)` returns the score alone. Each call uses one evaluation;
- `lm(prompt)` returns the language model's answer as text (one request of the budget each; at most 4096 tokens
  of answer; it may be called from several threads);
- `budget.lm_calls_left`, `budget.evaluations_left`, `budget.seconds_left`. Going over raises an exception.

An improver is scored by running it on {tasks} tasks it has not seen (kinds: {families}; other kinds will be
used later) with {calls} model requests and {evaluations} evaluations each, and averaging the scores of the
programs it returns, measured on fresh instances. An improver that raises, or returns something that does not
run, scores 0 on that task. Evaluating one improver therefore costs up to {run} of YOUR model requests: they come
out of the same `budget.lm_calls_left`.
""".strip()


def lm_of(link: Link, budget: Budget):
    def lm(prompt: str, temperature: float | None = None) -> str:
        budget.take("lm_calls")
        answer = link.ask({"lm": {"prompt": str(prompt)[:120_000], "temperature": temperature}})
        if answer.get("error"):
            raise BudgetExhausted(answer["error"])
        return answer["text"]
    return lm


# --------------------------------------------------------------------------- an improver as the program

def _child(source: str, child: dict, child_budget: dict, link: Link, outer: Budget) -> dict:
    """Run improver ``source`` on one ordinary task in a process of its own; its requests are relayed."""
    spec = {"family": child["family"], "visible": child["visible"], "budget": child_budget}
    process = subprocess.Popen([sys.executable, "-I", os.path.abspath(__file__), "run"], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lock, outcome = threading.Lock(), {}

    def reply(message):
        try:
            outer.take("lm_calls")
            answer = link.ask({"lm": message["lm"]})
        except BudgetExhausted as error:
            answer = {"error": str(error)}
        with lock:
            try:
                process.stdin.write(json.dumps({**answer, "id": message["id"]}) + "\n")
                process.stdin.flush()
            except (OSError, ValueError):
                pass

    def listen():
        for line in process.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if "lm" in message:
                threading.Thread(target=reply, args=(message,), daemon=True).start()
            elif "result" in message:
                outcome.update(message)

    errors: list = []
    threading.Thread(target=lambda: errors.append(process.stderr.read()[-1500:]), daemon=True).start()
    with lock:
        process.stdin.write(json.dumps({"source": source, "spec": spec}) + "\n")
        process.stdin.flush()
    listener = threading.Thread(target=listen, daemon=True)
    listener.start()
    listener.join(min(child_budget["seconds"], outer.seconds_left) + 5)
    if process.poll() is None:
        process.kill()
    solution = outcome.get("result")
    rows = evaluated(solution, child["family"], child["check"]) if isinstance(solution, str) else []
    score = sum(row["quality"] for row in rows) / len(rows) if rows else 0.0
    problem = outcome.get("error") or (None if solution is not None else "no result (crash or timeout)")
    return {"family": child["family"], "score": round(score, 4), "error": problem,
            "stderr": (errors[0] if errors and problem else "")}


def _improver_result(source: str, spec: dict, budget: Budget, link: Link) -> Result:
    children, rows = spec["children"], []
    threads = []
    for child in children:
        thread = threading.Thread(target=lambda c=child: rows.append(_child(source, c, spec["child_budget"], link, budget)))
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    rows.sort(key=lambda row: row["family"])
    lines = [f"task {row['family']}: score {row['score']}" + (f", {row['error']}" if row["error"] else "")
             + (f"\n  stderr: {row['stderr']}" if row["stderr"] else "") for row in rows]
    return Result(sum(row["score"] for row in rows) / len(children), "\n".join(lines))


def _run() -> int:
    protocol = sys.stdout
    sys.stdout = sys.stderr
    request = json.loads(sys.stdin.readline())
    spec = request["spec"]
    given = spec["budget"]
    budget = Budget(given["lm_calls"], given["evaluations"], given["seconds"])
    link = Link(sys.stdin, protocol)
    task = Task(spec, budget, link)
    result, error = task.initial, None
    try:
        namespace: dict = {"__name__": "improver"}
        exec(compile(request["source"], "improver.py", "exec"), namespace)
        answer = namespace["improve"](task, lm_of(link, budget), budget)
        if not isinstance(answer, str):
            raise TypeError("improve must return source text")
        result = answer
    except BaseException as failure:  # noqa: BLE001 - a failed improver returns the initial program
        import traceback
        traceback.print_exc()
        error = f"{type(failure).__name__}: {failure}"[:300]
    link.send({"result": result, "error": error, "lm_calls_used": budget.lm_calls_used,
               "evaluations_used": budget.evaluations_used})
    return 0


def main(argv: list) -> int:
    if argv[1:] == ["run"]:
        return _run()
    if argv[1:] == ["score"]:
        request = json.loads(sys.stdin.read())
        print(json.dumps(evaluated(request["source"], request["family"], request["seeds"])))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
