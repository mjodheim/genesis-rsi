"""A second way to a language model: the Codex command-line client, under a subscription.

``improver_lineage.Model`` pays per request through a metered endpoint. Here a request is one run
of ``codex exec`` in an empty directory, read-only, told to answer in text and run nothing. No
price is known per request, so what is bounded is the number of requests per day, counted from
the journal; the quota behind the subscription is shared with other uses of the same account.

This channel is looser than the metered one and a plan that uses it must say so: the client is
an agent, the answer size and the sampling temperature are its own, and its system prompt is
not ours. The model and its reasoning effort are passed explicitly and recorded.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
import threading
from typing import Callable, Sequence

from genesis.repair_lineage import BudgetExhausted, ModelUnavailable
from genesis.trust_root import digest_of

MODEL = "gpt-6.1-sol"
EFFORT = "low"
PREAMBLE = ("Answer with text only. Do not run any command, tool or search, and do not read or write any file: "
            "everything you need is in this message.\n\n")
QUOTA = re.compile(r"usage limit|quota|rate limit|too many requests|\b429\b", re.I)


def command(output: Path, *, model: str = MODEL, effort: str = EFFORT, codex: str = "codex") -> list[str]:
    """The exact argv of one request. Pure, so the flags can be tested."""
    return [codex, "exec", "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "-c", f"model_reasoning_effort={effort}", "-o", str(output), "-"]


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class CodexModel:
    """``model(prompt, temperature) -> str`` with a ceiling on requests per UTC day."""

    def __init__(self, journal_path: Path, label: dict, *, per_day: int, timeout: int = 600,
                 runner: Callable[[Sequence[str], str, Path, int], tuple[int, str]] | None = None):
        self.path, self.label, self.per_day, self.timeout = Path(journal_path), label, per_day, timeout
        self.runner = runner or self._run
        self.lock = _LOCKS.setdefault(str(self.path), threading.Lock())

    @staticmethod
    def _run(argv: Sequence[str], prompt: str, directory: Path, timeout: int) -> tuple[int, str]:
        done = subprocess.run(list(argv), input=prompt, cwd=directory, capture_output=True, text=True, timeout=timeout)
        return done.returncode, (done.stdout + done.stderr)[-6000:]

    def used_today(self) -> int:
        if not self.path.exists():
            return 0
        day = today()
        return sum(json.loads(line).get("day") == day for line in self.path.read_text(encoding="utf-8").splitlines())

    def _record(self, record: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({**self.label, **record}, sort_keys=True) + "\n")

    def __call__(self, prompt: str, temperature) -> str:
        with self.lock:
            if self.used_today() >= self.per_day:
                raise BudgetExhausted(f"{self.per_day} requests already made today")
            # The request is written down before it is made: a crash never hides one.
            self._record({"day": today(), "prompt_digest": digest_of(prompt), "state": "sent"})
        with tempfile.TemporaryDirectory(prefix="genesis-codex-") as scratch:
            output = Path(scratch) / "answer.txt"
            try:
                code, log = self.runner(command(output), PREAMBLE + prompt, Path(scratch), self.timeout)
            except subprocess.TimeoutExpired:
                code, log = -1, "timeout"
            text = output.read_text(encoding="utf-8", errors="replace") if output.is_file() else ""
        tokens = re.search(r"tokens used\s*\n?\s*([\d,]+)", log)
        with self.lock:
            self._record({"prompt_digest": digest_of(prompt), "state": "answered" if text else "failed",
                          "exit": code, "answer_characters": len(text),
                          "tokens_used": int(tokens.group(1).replace(",", "")) if tokens else None})
        if not text and QUOTA.search(log):
            raise ModelUnavailable("the subscription refused the request")
        return text


_LOCKS: dict = {}
