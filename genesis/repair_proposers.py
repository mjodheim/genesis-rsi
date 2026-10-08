"""Candidate sources for the repair bench.

Two proposers with one interface, so that they can be compared at an equal validation budget:

* :func:`strategist_proposer` -- the existing operator families, with no model call;
* :func:`model_proposer` -- a language model asked for exact-text edits, through the ``claude``
  command-line client. Genesis keeps the loop (evidence, validation, verdict); the model only
  proposes.

A public benchmark may be in a model's training data. A model-proposed repair of a Defects4J case
is therefore evidence that the loop works end to end, not evidence that the model reasoned the fix
out. Records carry that caveat explicitly.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Mapping, Sequence

from genesis import repair_strategist
from genesis.repair_bench import Candidate, History, Proposer, apply_edits
from genesis.trust_root import digest_of

MODEL_CALL_SCHEMA = "genesis-model-proposal-call-v1"

_ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["hypothesis", "path", "edits"],
                "properties": {
                    "hypothesis": {"type": "string"},
                    "path": {"type": "string"},
                    "edits": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["search", "replace"],
                            "properties": {"search": {"type": "string"}, "replace": {"type": "string"}},
                        },
                    },
                },
            },
        }
    },
}

_INSTRUCTIONS = """You are repairing a defect in a Java project. Some of its tests fail.

You are given the failing tests, their stack traces, the source of the failing tests and numbered
excerpts of the production code the failures reach. The defect is in the production code, not in
the tests.

Propose {count} DIFFERENT candidate repairs, most likely first. Each candidate must test a distinct
hypothesis about the cause; do not submit variations in formatting.

Rules for every candidate:
- change production code only, in exactly one of the files shown;
- give the file path exactly as shown;
- express the change as one or more edits, each with `search` (text copied character for character
  from the file, WITHOUT the line-number prefix, long enough to occur exactly once in the file) and
  `replace` (the text that takes its place);
- keep the change minimal and make sure the result compiles;
- never modify or delete a test.
"""


_OUTCOMES = {
    "compile": "did not compile",
    "failing_tests": "compiled, but a failing test still fails",
    "full_suite": "made the failing tests pass but broke other tests",
}


def render_prompt(evidence: Mapping, count: int, history: History = ()) -> str:
    """The complete, deterministic prompt for one case. Nothing but buggy-side evidence goes in.

    ``history`` is the arm's own earlier candidates on this case with what the validator observed.
    """
    parts = [_INSTRUCTIONS.format(count=count), "## Failing tests"]
    for trace in evidence["traces"]:
        parts.append(f"### {trace['test']}\n```\n{trace['trace']}\n```")
    parts.append("## Source of the failing tests")
    for excerpt in evidence["test_source"]:
        parts.append(f"### {excerpt['path']}\n```java\n{excerpt['numbered_source']}\n```")
    parts.append("## Production code reached by the failures")
    for excerpt in evidence["production_source"]:
        parts.append(
            f"### {excerpt['path']} (lines {excerpt['first_line']}-{excerpt['last_line']})\n"
            f"```java\n{excerpt['numbered_source']}\n```"
        )
    if history:
        parts.append(
            "## Candidates already tried\n\nNone of these is a repair. Use what each outcome shows about "
            "the defect; do not repeat them."
        )
        for number, (candidate, verdict) in enumerate(history[-8:], 1):
            outcome = _OUTCOMES.get(verdict["stopped_at"], verdict["stopped_at"])
            feedback = f"\n```\n{verdict['feedback']}\n```" if verdict.get("feedback") else ""
            parts.append(f"### Attempt {number}: {outcome}\n{candidate.description}{feedback}")
    return "\n\n".join(parts) + "\n"


_EXPLORE = """
## Reading the project

The project's production sources are under `{source}` and its tests under `{tests}`, relative to
the current directory. Before answering you may read and search those files to find where the
defect is. The excerpts above are only a starting point and may not contain it. You cannot run
anything.
"""


def model_proposer(
    model: str, count: int, calls: list[dict], *, explore: bool = False, executable: str = "claude",
    timeout_seconds: int = 900, max_call_usd: float = 1.5, retry_wait_seconds: int = 60,
) -> Proposer:
    """A proposer that asks ``model`` once per round, for at most ``count`` candidates per call.

    Later rounds show the model its earlier candidates and their verdicts. With ``explore`` the
    model may also read and search a copy of the buggy sources and tests (never the repository
    history, which holds the fixed revision). Every call is appended to ``calls``.
    """

    def propose(root: Path, evidence: Mapping, history: History, remaining: int) -> Sequence[Candidate]:
        count_now = max(1, min(count, remaining))
        prompt = render_prompt(evidence, count_now, history)
        source, tests = evidence["source_directory"], evidence["test_directory"]
        if explore:
            prompt += _EXPLORE.format(source=source, tests=tests)
        argv = [
            executable, "-p", prompt, "--output-format", "json",
            "--json-schema", json.dumps(_ANSWER_SCHEMA, sort_keys=True, separators=(",", ":")),
            "--model", model, "--tools", "Read,Glob,Grep" if explore else "", "--restricted",
            "--permission-mode", "dontAsk", "--max-budget-usd", str(max_call_usd),
            "--no-session-persistence", "--disable-slash-commands",
        ]
        record: dict = {
            "schema": MODEL_CALL_SCHEMA, "model": model, "requested": count_now, "round": len(calls) + 1,
            "earlier_attempts_shown": len(history), "explore": explore,
            "prompt_digest": digest_of(prompt), "evidence_digest": evidence["evidence_digest"],
            "benchmark_may_be_in_training_data": True,
        }
        candidates: list[Candidate] = []
        try:
            with tempfile.TemporaryDirectory(prefix="genesis-model-proposer-") as empty:
                if explore:
                    for part in dict.fromkeys((source, tests)):
                        shutil.copytree(root / part, Path(empty) / part, symlinks=True)
                # A call that fails outright (quota, overload) measured nothing about the case:
                # wait and ask once more, and say so in the record either way.
                for attempt in (1, 2):
                    done = subprocess.run(
                        argv, cwd=empty, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, timeout=timeout_seconds, check=False,
                    )
                    raw = json.loads(done.stdout) if done.stdout.strip() else {}
                    answer = raw.get("structured_output") if isinstance(raw, dict) else None
                    if done.returncode == 0 and isinstance(answer, dict):
                        break
                    if attempt == 1:
                        time.sleep(retry_wait_seconds)
            record["attempts"] = attempt
            if done.returncode != 0 or not isinstance(answer, dict):
                record["call_failed"] = True
                record["failure"] = str((raw.get("result") if isinstance(raw, dict) else "") or done.stderr)[:300]
                answer = None
            record.update({
                "returncode": done.returncode,
                "cost_usd": raw.get("total_cost_usd") if isinstance(raw, dict) else None,
                "answer_digest": digest_of(answer) if answer is not None else None,
            })
            for item in (answer or {}).get("candidates", [])[:count_now]:
                if not str(item["path"]).startswith(source.rstrip("/") + "/"):
                    continue  # only production code may change; a "repair" that edits a test is not one
                edits = [(edit["search"], edit["replace"]) for edit in item["edits"]]
                described = f"Hypothesis: {item['hypothesis']}\nFile: {item['path']}\n" + "\n".join(
                    f"- replaced:\n{search}\n  with:\n{replace}" for search, replace in edits
                )
                candidate = apply_edits(root, item["path"], edits, f"model:{model}", described[:2500])
                if candidate is not None:
                    candidates.append(candidate)
            record["returned"] = len((answer or {}).get("candidates", []))
        except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError, TypeError, AttributeError) as error:
            record["error"] = type(error).__name__
            record["call_failed"] = True
        record["applicable"] = len(candidates)
        calls.append(record)
        return candidates

    return propose


def strategist_proposer(count: int) -> Proposer:
    """The existing operator families, focused on the files the failure reaches. No model call."""

    def propose(root: Path, evidence: Mapping, history: History, remaining: int) -> Sequence[Candidate]:
        if history:
            return []  # the ranking is fixed: everything was offered in the first round
        focus = sorted({path for path, _ in evidence["suspect_locations"]})
        if not focus:
            return []
        generated = repair_strategist.generate(
            root, include_prefixes=[evidence["source_directory"]], focus_paths=focus,
            max_candidates=max(count * 8, 80), per_family_budget=max(count * 8, 80),
            composition_fraction=0.4, source_balance_experimental=len(focus) > 1,
            atomic_first_experimental=True, sibling_guard_experimental=True,
            stream_iterator_experimental=True, priority_focus_paths=tuple(focus[:8]),
        )
        return [
            Candidate(path=item["path"], content=item["content_utf8"], origin="strategist",
                      description="Local repair operator: " + str(item.get("operator", "unknown")))
            for item in generated["candidates"][:count]
        ]

    return propose
