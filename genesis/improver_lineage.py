"""Host side of the self-improving improver: run an improver in a container, pay for its model
requests, score what it returns, and decide whether a successor replaces its parent.

A generation is one self-application: the current improver is handed the task "improve this
improver" with its own source as the initial program, and whatever it returns is its candidate
successor. Nothing but the improver decides how the successor is found. The host only judges:
both improvers are run on the same fresh ordinary tasks with the same budget, and the successor
is promoted under a rule fixed in advance.

The model is fixed for a whole lineage and reached only through this module, which counts every
request. Improvers, the programs they write and the scoring of those programs all run in
containers without network; the score that counts is recomputed here, in a fresh container, on
instances the improver never saw.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid
from typing import Callable, Mapping, Sequence

from genesis.repair_lineage import BudgetExhausted, Envelope, Ledger, ModelUnavailable, _send
from genesis.trust_root import digest_of

IMAGE = "python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
RUNTIME = Path(__file__).with_name("improver_runtime.py")
SEED = Path(__file__).with_name("improver_seed.py")
MODEL = "anthropic/claude-haiku-5.5"
OBJECT_BUDGET = {"lm_calls": 6, "evaluations": 10, "seconds": 900}
CHILDREN = 4
META_BUDGET = {"lm_calls": 6 + 6 * CHILDREN * OBJECT_BUDGET["lm_calls"], "evaluations": 6, "seconds": 7200}
VISIBLE, CHECK, HIDDEN = (0, 1, 2), (3, 4), (5, 6, 7, 8, 9)
DEVELOPMENT = ("binpack", "coloring", "qap", "regression", "tardiness", "tsp")
HELD_OUT = ("cluster", "jobshop", "knapsack", "maxcut", "sequence", "setcover")


def seeds(task: int, offsets: Sequence[int]) -> list[int]:
    """Instances of one task. A task owns ten seeds: three shown, two for the improver's own check
    of improvers, five kept by the host."""
    return [task * 10 + offset for offset in offsets]


def object_spec(family: str, task: int) -> dict:
    return {"family": family, "visible": seeds(task, VISIBLE), "budget": dict(OBJECT_BUDGET)}


def meta_spec(source: str, children: Sequence[tuple[str, int]]) -> dict:
    return {"family": "improver", "initial": source, "budget": dict(META_BUDGET), "child_budget": dict(OBJECT_BUDGET),
            "children": [{"family": family, "visible": seeds(task, VISIBLE), "check": seeds(task, CHECK)}
                         for family, task in children]}


def docker_argv(name: str, mode: str, *, cpus: float, docker: str = "docker") -> list[str]:
    """The exact ``docker run`` argv. Pure, so the flags can be tested."""
    return [docker, "run", "--rm", "-i", "--name", name, "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "256", "--memory", "3g", "--memory-swap", "3g",
            "--cpus", str(cpus), "--user", f"{os.getuid()}:{os.getgid()}",
            "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=256m", "--env", "HOME=/tmp", "--env", "PYTHONDONTWRITEBYTECODE=1",
            "--mount", f"type=bind,source={RUNTIME},target=/genesis/improver_runtime.py,readonly",
            "--workdir", "/tmp", IMAGE, "python", "-I", "/genesis/improver_runtime.py", mode]


class Model:
    """The one way to the language model: fixed model, fixed answer size, every request recorded."""

    def __init__(self, ledger: Ledger, journal: Callable[[dict], None], *, model: str = MODEL,
                 transport: Callable | None = None):
        self.envelope = Envelope(model=model, max_tokens=4096)
        self.ledger, self.journal, self.transport = ledger, journal, transport

    def __call__(self, prompt: str, temperature) -> str:
        payload = {"model": self.envelope.model, "messages": [{"role": "user", "content": prompt}],
                   "max_tokens": self.envelope.max_tokens,
                   "provider": {"allow_fallbacks": True, "sort": "price", "max_price": dict(self.envelope.max_price)}}
        if isinstance(temperature, (int, float)) and not isinstance(temperature, bool) and 0 <= temperature <= 1:
            payload["temperature"] = temperature
        raw, cost = _send(payload, self.envelope, self.ledger, self.transport)
        usage = raw.get("usage", {})
        try:
            text = raw["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            text = ""
        self.journal({"cost_usd": cost, "prompt_tokens": usage.get("prompt_tokens"),
                      "completion_tokens": usage.get("completion_tokens"), "prompt_digest": digest_of(prompt),
                      "answer_characters": len(text)})
        return text if isinstance(text, str) else ""


def run_improver(source: str, spec: Mapping, model: Callable[[str, object], str], *, cpus: float = 2,
                 command: Sequence[str] | None = None) -> dict:
    """Run improver ``source`` on the task ``spec``. The model requests it may make are bounded by the
    spec's budget here, whatever the container counts. Returns the program it gave back."""
    name = "genesis-improver-" + uuid.uuid4().hex[:12]
    limit, seconds = spec["budget"]["lm_calls"], spec["budget"]["seconds"]
    process = subprocess.Popen(list(command) if command else docker_argv(name, "run", cpus=cpus),
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    lock, state = threading.Lock(), {"calls": 0, "outcome": None, "stop": None}
    errors: list[str] = []
    threading.Thread(target=lambda: errors.append(process.stderr.read()[-4000:]), daemon=True).start()

    def write(message: dict) -> None:
        with lock:
            try:
                process.stdin.write(json.dumps(message) + "\n")
                process.stdin.flush()
            except (OSError, ValueError):
                pass

    def answer(message: dict) -> None:
        with lock:
            allowed = state["calls"] < limit and state["stop"] is None
            state["calls"] += allowed
        if not allowed:
            return write({"id": message.get("id"), "error": "no model request left"})
        try:
            request = message["lm"]
            write({"id": message.get("id"), "text": model(str(request.get("prompt", ""))[:120_000], request.get("temperature"))})
        except (BudgetExhausted, ModelUnavailable) as error:
            state["stop"] = error
            write({"id": message.get("id"), "error": "the model is unavailable"})

    def listen() -> None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                except ValueError:
                    continue
                if isinstance(message, dict) and "lm" in message:
                    pool.submit(answer, message)
                elif isinstance(message, dict) and "result" in message:
                    state["outcome"] = message
                    break

    started = time.monotonic()
    write({"source": source, "spec": dict(spec)})
    listener = threading.Thread(target=listen, daemon=True)
    listener.start()
    listener.join(seconds + 30)
    timed_out = state["outcome"] is None and process.poll() is None
    if process.poll() is None:
        if not command:
            subprocess.run(["docker", "kill", name], capture_output=True)
        process.kill()
    process.wait()
    if state["stop"] is not None:
        raise state["stop"]
    outcome = state["outcome"] or {}
    solution = outcome.get("result")
    return {"solution": solution if isinstance(solution, str) else None,
            "error": outcome.get("error") or ("timeout" if timed_out else None if outcome else "no result"),
            "lm_calls": state["calls"], "evaluations_used": outcome.get("evaluations_used"),
            "seconds": round(time.monotonic() - started, 1), "stderr": errors[0][-1500:] if errors else ""}


def score(solution: str | None, family: str, instances: Sequence[int], *, command: Sequence[str] | None = None) -> float:
    """Mean quality of ``solution`` on ``instances``, in a fresh container. No program scores zero."""
    if solution is None:
        return 0.0
    name = "genesis-score-" + uuid.uuid4().hex[:12]
    try:
        done = subprocess.run(list(command) if command else docker_argv(name, "score", cpus=1),
                              input=json.dumps({"source": solution, "family": family, "seeds": list(instances)}),
                              capture_output=True, text=True, timeout=120)
        rows = json.loads(done.stdout)
        return round(sum(row["quality"] for row in rows) / len(rows), 6)
    except (subprocess.TimeoutExpired, ValueError, KeyError, TypeError, ZeroDivisionError):
        if not command:
            subprocess.run(["docker", "kill", name], capture_output=True)
        return 0.0


def attempt(source: str, family: str, task: int, model: Callable, **options) -> dict:
    """One improver on one ordinary task, scored on the task's hidden instances."""
    ran = run_improver(source, object_spec(family, task), model, **options)
    return {"family": family, "task": task, "score": score(ran["solution"], family, seeds(task, HIDDEN),
                                                           command=options.get("score_command")),
            "error": ran["error"], "lm_calls": ran["lm_calls"], "seconds": ran["seconds"],
            "solution_digest": digest_of(ran["solution"]) if ran["solution"] else None}


def sign_test(losses: int, wins: int) -> float:
    from math import comb
    total = losses + wins
    return 1.0 if total == 0 else sum(comb(total, k) for k in range(wins, total + 1)) / 2 ** total


def compared(parent: Sequence[Mapping], child: Sequence[Mapping], *, tie: float = 0.005) -> dict:
    """Child against parent on the same tasks: mean scores, and tasks won and lost by more than ``tie``."""
    pairs = {(row["family"], row["task"]): [row["score"], None] for row in parent}
    for row in child:
        pairs[(row["family"], row["task"])][1] = row["score"]
    if any(second is None for _, second in pairs.values()) or len(pairs) != len(child):
        raise ValueError("the two improvers were not run on the same tasks")
    wins = sum(second - first > tie for first, second in pairs.values())
    losses = sum(first - second > tie for first, second in pairs.values())
    families = sorted({family for family, _ in pairs})
    mean = lambda index, family=None: round(sum(pair[index] for key, pair in pairs.items()  # noqa: E731
                                                if family in (None, key[0])) / max(1, sum(family in (None, key[0]) for key in pairs)), 6)
    return {"tasks": len(pairs), "parent_mean": mean(0), "child_mean": mean(1), "wins": wins, "losses": losses,
            "one_sided_exact_sign_test_p": round(sign_test(losses, wins), 6),
            "by_family": {family: {"parent": mean(0, family), "child": mean(1, family)} for family in families}}


def promoted(comparison: Mapping, *, margin: int, level: float) -> bool:
    """The rule of a lineage: more tasks won than lost by ``margin``, a higher mean, and the sign test."""
    return (comparison["wins"] - comparison["losses"] >= margin and comparison["child_mean"] > comparison["parent_mean"]
            and comparison["one_sided_exact_sign_test_p"] <= level)
