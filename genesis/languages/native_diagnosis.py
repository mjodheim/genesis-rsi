"""Bounded zero-LLM diagnosis loop for software repositories.

A1 of the autonomous RSI software track gives Genesis a way to inspect native
tool feedback without asking an external model what it means. The loop is
deliberately conservative:

* fixed language-pack commands;
* argv execution only, never a shell;
* a bounded number of probes with no automatic retries;
* execution in a disposable copy, never the source tree;
* offline-oriented environment defaults;
* content-addressed evidence and normalized failure classes;
* zero external model calls by construction.

This module does not generate repairs. That is A2.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Iterable, Mapping

from genesis.languages import toolchains as language_toolchains
from genesis.trust_root import digest_of

DIAGNOSIS_REPORT_SCHEMA = "genesis-native-diagnosis-report-v1"
PROBE_SCHEMA = "genesis-native-diagnosis-probe-v1"

_COPY_IGNORES = {
    ".git",
    ".gradle",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "bin",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "obj",
    "target",
    "venv",
}

_ERROR_PATTERNS = (
    ("python_syntax_error", re.compile(r"\bSyntaxError\b")),
    ("rust_compile_error", re.compile(r"(^|\n)error(?:\[E\d+\])?:", re.MULTILINE)),
    ("java_compile_error", re.compile(r"\b(?:COMPILATION ERROR|cannot find symbol|incompatible types)\b", re.I)),
    ("csharp_compile_error", re.compile(r"\berror CS\d+\b", re.I)),
    ("go_compile_error", re.compile(r"(^|\n).+\.go:\d+(?::\d+)?:", re.MULTILINE)),
    ("typescript_compile_error", re.compile(r"\berror TS\d+\b")),
    ("test_failure", re.compile(r"\b(?:FAILED|FAILURES?|tests? failed)\b", re.I)),
    ("missing_dependency", re.compile(r"\b(?:not found|No module named|could not resolve|NU\d{4})\b", re.I)),
    ("panic_or_crash", re.compile(r"\b(?:panicked|panic|segmentation fault|fatal error)\b", re.I)),
)


@dataclass(frozen=True)
class Probe:
    language: str
    argv: tuple[str, ...]

    def record(self) -> dict[str, Any]:
        payload = {
            "schema": PROBE_SCHEMA,
            "language": self.language,
            "argv": list(self.argv),
        }
        return {**payload, "probe_digest": digest_of(payload)}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _copy_repository(source: Path, destination: Path) -> None:
    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in _COPY_IGNORES}

    shutil.copytree(source, destination, ignore=ignore, symlinks=False)


def _environment() -> dict[str, str]:
    allowed = ("PATH", "HOME", "TMPDIR", "TEMP", "TMP")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(
        {
            "GENESIS_AUTONOMOUS_DIAGNOSIS": "1",
            "CARGO_NET_OFFLINE": "true",
            "PIP_NO_INDEX": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "NPM_CONFIG_OFFLINE": "true",
            "NPM_CONFIG_AUDIT": "false",
            "NPM_CONFIG_FUND": "false",
            "GONOSUMDB": "*",
            "GOPROXY": "off",
            "DOTNET_NOLOGO": "1",
            "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
        }
    )
    return env


def _classify(text: str, *, exit_code: int | None, timed_out: bool) -> tuple[str, ...]:
    labels: list[str] = []
    if timed_out:
        labels.append("timeout")
    if exit_code is None and not timed_out:
        labels.append("execution_error")
    for name, pattern in _ERROR_PATTERNS:
        if pattern.search(text):
            labels.append(name)
    if exit_code not in (0, None) and not labels:
        labels.append("nonzero_exit")
    if exit_code == 0 and not labels:
        labels.append("clean")
    return tuple(dict.fromkeys(labels))


def plan(root: str | Path, *, max_probes: int = 8) -> tuple[Probe, ...]:
    """Build the bounded native-diagnostic plan for a repository."""
    if max_probes < 1:
        raise ValueError("max_probes must be positive")
    base = Path(root)
    languages = language_toolchains.detect_languages(base)
    probes: list[Probe] = []
    for language in languages:
        language_pack = language_toolchains.pack(language)
        for argv in language_pack.diagnostic_commands:
            if shutil.which(argv[0]) is None:
                continue
            probes.append(Probe(language=language, argv=tuple(argv)))
            if len(probes) >= max_probes:
                return tuple(probes)
    return tuple(probes)


def run(
    root: str | Path,
    *,
    max_probes: int = 8,
    timeout_seconds: int = 90,
    output_limit_bytes: int = 16000,
    stop_after_first_failure: bool = False,
) -> dict[str, Any]:
    """Execute a bounded, no-retry diagnosis pass in a disposable repository copy."""
    if timeout_seconds < 1 or timeout_seconds > 900:
        raise ValueError("timeout_seconds must be in [1, 900]")
    if output_limit_bytes < 512 or output_limit_bytes > 1_000_000:
        raise ValueError("output_limit_bytes must be in [512, 1000000]")

    source = Path(root).resolve()
    if not source.is_dir():
        raise ValueError(f"project root does not exist or is not a directory: {source}")

    probes = plan(source, max_probes=max_probes)
    capabilities = language_toolchains.capability_report(source)
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory(prefix="genesis-native-diagnosis-") as temp:
        workspace = Path(temp) / "workspace"
        _copy_repository(source, workspace)

        for index, probe in enumerate(probes):
            started = time.monotonic()
            stdout = b""
            stderr = b""
            exit_code: int | None = None
            timed_out = False
            execution_problem: str | None = None
            try:
                completed = subprocess.run(
                    probe.argv,
                    cwd=workspace,
                    env=_environment(),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=timeout_seconds,
                    check=False,
                )
                exit_code = int(completed.returncode)
                stdout = completed.stdout or b""
                stderr = completed.stderr or b""
            except subprocess.TimeoutExpired as problem:
                timed_out = True
                stdout = problem.stdout or b""
                stderr = problem.stderr or b""
            except OSError as problem:
                execution_problem = str(problem)
                stderr = execution_problem.encode("utf-8", errors="replace")

            elapsed_ms = int((time.monotonic() - started) * 1000)
            joined = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
            classes = _classify(joined, exit_code=exit_code, timed_out=timed_out)

            results.append(
                {
                    "probe_index": index,
                    "probe": probe.record(),
                    "exit_code": exit_code,
                    "timed_out": timed_out,
                    "elapsed_ms": elapsed_ms,
                    "stdout_sha256": _sha256(stdout),
                    "stderr_sha256": _sha256(stderr),
                    "stdout_length": len(stdout),
                    "stderr_length": len(stderr),
                    "stdout_tail": stdout[-output_limit_bytes:].decode("utf-8", errors="replace"),
                    "stderr_tail": stderr[-output_limit_bytes:].decode("utf-8", errors="replace"),
                    "diagnostic_classes": list(classes),
                    "execution_problem": execution_problem,
                    "passed": exit_code == 0 and not timed_out,
                }
            )

            if stop_after_first_failure and (exit_code != 0 or timed_out):
                break

    failed = [item for item in results if not item["passed"]]
    payload: dict[str, Any] = {
        "schema": DIAGNOSIS_REPORT_SCHEMA,
        "project_root": str(source),
        "languages": list(capabilities["languages"]),
        "capabilities": capabilities["packs"],
        "planned_probe_count": len(probes),
        "executed_probe_count": len(results),
        "max_probes": max_probes,
        "timeout_seconds": timeout_seconds,
        "stop_after_first_failure": stop_after_first_failure,
        "results": results,
        "failure_observed": bool(failed),
        "failure_classes": sorted(
            {
                label
                for item in failed
                for label in item["diagnostic_classes"]
            }
        ),
        "external_model_calls": 0,
        "retry_count": 0,
        "source_tree_execution": False,
        "claim": "A1_NATIVE_DIAGNOSIS_ONLY",
    }
    return {**payload, "report_digest": digest_of(payload)}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for reproducible A1 diagnosis runs."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Genesis zero-LLM native diagnosis")
    parser.add_argument("root", help="repository root")
    parser.add_argument("--max-probes", type=int, default=8)
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--stop-after-first-failure", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = run(
        args.root,
        max_probes=args.max_probes,
        timeout_seconds=args.timeout_seconds,
        stop_after_first_failure=args.stop_after_first_failure,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not report["failure_observed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
