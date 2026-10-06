#!/usr/bin/env python3
"""Frozen L10-A evaluator for BurntSushi/ripgrep issue #278."""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import tempfile

IMAGE = "rust@sha256:1f0dbad1df66647807e6952d1db85d0b2bda7606cb2139d82517e4f009967376"

def docker(workspace: pathlib.Path, args: list[str], *, extra_mount: tuple[pathlib.Path, str] | None = None) -> subprocess.CompletedProcess[str]:
    command = [
        "docker", "run", "--rm",
        "--network", "bridge",
        "--memory", "2g", "--cpus", "2", "--pids-limit", "512",
        "-v", f"{workspace.resolve()}:/workspace",
        "-w", "/workspace",
    ]
    if extra_mount is not None:
        source, target = extra_mount
        command += ["-v", f"{source.resolve()}:{target}"]
    command += [IMAGE, *args]
    return subprocess.run(command, text=True, capture_output=True, check=False)

def regression(workspace: pathlib.Path) -> int:
    result = docker(workspace, ["cargo", "test", "--locked", "-p", "ignore"])
    if result.returncode:
        print(result.stdout[-12000:])
        print(result.stderr[-12000:])
    return result.returncode

def objective(workspace: pathlib.Path) -> int:
    built = docker(workspace, ["cargo", "build", "--locked", "--bin", "rg"])
    if built.returncode:
        print(built.stdout[-12000:])
        print(built.stderr[-12000:])
        return 2

    with tempfile.TemporaryDirectory(prefix="l10-rg-278-") as raw:
        root = pathlib.Path(raw)
        cwd = root / "cwd"
        test = root / "test"
        foo = test / "foo"
        cwd.mkdir()
        foo.mkdir(parents=True)
        (test / ".gitignore").write_text(".*\n", encoding="utf-8")
        (foo / "bar").write_text("baz\n", encoding="utf-8")

        first = docker(
            workspace,
            ["bash", "-lc", "cd /case/cwd && /workspace/target/debug/rg baz ../test"],
            extra_mount=(root, "/case"),
        )
        second = docker(
            workspace,
            ["bash", "-lc", "cd /case/cwd && /workspace/target/debug/rg baz ../test/foo"],
            extra_mount=(root, "/case"),
        )

        # Issue #278 reports inconsistent ignore behavior solely because the search
        # root changes. The objective is consistency: both invocations must make
        # the same search decision and produce the same match-set semantics.
        first_lines = [line for line in first.stdout.splitlines() if line.strip()]
        second_lines = [line for line in second.stdout.splitlines() if line.strip()]
        first_found = any("baz" in line for line in first_lines)
        second_found = any("baz" in line for line in second_lines)
        ok = first_found == second_found
        print({
            "first_returncode": first.returncode,
            "second_returncode": second.returncode,
            "first_found": first_found,
            "second_found": second_found,
        })
        return 0 if ok else 1

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("regression", "objective"))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    if args.mode == "regression":
        return regression(args.workspace)
    return objective(args.workspace)

if __name__ == "__main__":
    raise SystemExit(main())
