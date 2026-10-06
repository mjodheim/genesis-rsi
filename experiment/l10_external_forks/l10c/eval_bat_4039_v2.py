#!/usr/bin/env python3
"""Frozen external evaluator for sharkdp/bat issue #4039."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import tempfile

IMAGE_ID = "sha256:e37db5048d151226b42e51e9382d5837c879f18cfca90e05c713b3b0da2bbe7f"
INPUT_TEXT = "line1\nline2\nline3\n"
PANIC_MARKERS = ("thread 'main' panicked", "panicked at", "capacity overflow")

def _docker(
    workspace: pathlib.Path,
    target: pathlib.Path,
    argv: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess[str]:
    command = [
        "docker", "run", "--rm", "-i",
        "--network", "none",
        "--memory", "3g", "--cpus", "2", "--pids-limit", "512",
        "-e", "CARGO_TARGET_DIR=/target",
        "-e", "CARGO_NET_OFFLINE=true",
        "-v", f"{workspace.resolve()}:/workspace:ro",
        "-v", f"{target.resolve()}:/target:rw",
        "-w", "/workspace",
        IMAGE_ID,
        *argv,
    ]
    return subprocess.run(
        command,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )

def _restore_target_owner(target: pathlib.Path) -> None:
    uid = str(__import__("os").getuid())
    gid = str(__import__("os").getgid())
    completed = subprocess.run(
        [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{target.resolve()}:/target:rw",
            IMAGE_ID,
            "chown", "-R", f"{uid}:{gid}", "/target",
        ],
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "could not restore disposable target ownership: "
            + (completed.stderr or completed.stdout)[-2000:]
        )

def _has_panic(result: subprocess.CompletedProcess[str]) -> bool:
    combined = (result.stdout + "\n" + result.stderr).lower()
    return any(marker in combined for marker in PANIC_MARKERS)

def _tail(value: str, limit: int = 12000) -> str:
    return value[-limit:]

def regression(workspace: pathlib.Path) -> int:
    with tempfile.TemporaryDirectory(prefix="l10-bat-regression-") as raw:
        target = pathlib.Path(raw)
        result = _docker(
            workspace,
            target,
            ["cargo", "test", "--locked", "--offline", "--lib"],
            timeout=900,
        )
        _restore_target_owner(target)
        print("REGRESSION_RETURN_CODE", result.returncode)
        if result.stdout:
            print(_tail(result.stdout))
        if result.stderr:
            print(_tail(result.stderr))
        return result.returncode

def objective(workspace: pathlib.Path) -> int:
    with tempfile.TemporaryDirectory(prefix="l10-bat-objective-") as raw:
        target = pathlib.Path(raw)

        build = _docker(
            workspace,
            target,
            ["cargo", "build", "--locked", "--offline", "--quiet", "--bin", "bat"],
            timeout=900,
        )
        if build.returncode != 0:
            _restore_target_owner(target)
            print("BUILD_FAILED", build.returncode)
            print(_tail(build.stdout))
            print(_tail(build.stderr))
            return 2

        binary = "/target/debug/bat"
        common = ["--style=plain", "--color=never", "--paging=never"]

        control = _docker(
            workspace,
            target,
            [binary, "--line-range", ":-2", *common],
            input_text=INPUT_TEXT,
            timeout=60,
        )
        control_ok = (
            control.returncode == 0
            and not _has_panic(control)
            and control.stdout == "line1\n"
        )

        huge = _docker(
            workspace,
            target,
            [binary, "--line-range", ":-999999999999999999", *common],
            input_text=INPUT_TEXT,
            timeout=60,
        )
        huge_text = (huge.stdout + "\n" + huge.stderr).lower()
        huge_no_panic = not _has_panic(huge)

        if huge.returncode == 0:
            output_lines = [line for line in huge.stdout.splitlines() if line]
            huge_graceful = set(output_lines).issubset({"line1", "line2", "line3"})
        else:
            huge_graceful = (
                huge.returncode in {1, 2}
                and any(token in huge_text for token in ("error", "invalid", "line range", "range"))
            )

        _restore_target_owner(target)
        print({
            "control_returncode": control.returncode,
            "control_stdout": control.stdout,
            "control_stderr": control.stderr,
            "control_ok": control_ok,
            "huge_returncode": huge.returncode,
            "huge_stdout": huge.stdout,
            "huge_stderr": huge.stderr,
            "huge_no_panic": huge_no_panic,
            "huge_graceful": huge_graceful,
        })

        return 0 if (control_ok and huge_no_panic and huge_graceful) else 1

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("regression", "objective"))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    return regression(args.workspace) if args.mode == "regression" else objective(args.workspace)

if __name__ == "__main__":
    raise SystemExit(main())
