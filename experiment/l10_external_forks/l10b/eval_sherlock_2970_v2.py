#!/usr/bin/env python3
"""Frozen external evaluator for Sherlock issue #2970.

Candidate code never receives this source. Both regression and objective run
with Docker network disabled. The objective recreates the reported
LocationParseError at the Future boundary and requires Sherlock to return a
normal UNKNOWN result instead of raising.
"""
from __future__ import annotations

import argparse
import pathlib
import subprocess
import tempfile

IMAGE_ID = "sha256:0c1ab1954c9dd3b8a1f229346b5d5a105d4ed24dbb21657bc0615309d6d0d97b"

OBJECTIVE = r"""
import urllib3.exceptions
import sherlock_project.sherlock as target
from sherlock_project.notify import QueryNotify
from sherlock_project.result import QueryStatus

class FailingFuture:
    def result(self):
        raise urllib3.exceptions.LocationParseError(
            "Failed to parse: 'alice..empretienda.com.ar', label empty or too long"
        )

class FakeSession:
    def __init__(self, *args, **kwargs):
        pass

    def head(self, *args, **kwargs):
        return FailingFuture()

    def get(self, *args, **kwargs):
        return FailingFuture()

    def post(self, *args, **kwargs):
        return FailingFuture()

    def put(self, *args, **kwargs):
        return FailingFuture()

target.SherlockFuturesSession = FakeSession

site_data = {
    "Empretienda AR": {
        "__comment__": "frozen issue 2970 reproduction",
        "errorType": "status_code",
        "url": "https://{}.empretienda.com.ar",
        "urlMain": "https://empretienda.com",
        "username_claimed": "camalote",
    }
}

result = target.sherlock(
    username="alice.",
    site_data=site_data,
    query_notify=QueryNotify(),
)
record = result["Empretienda AR"]
assert record["status"].status is QueryStatus.UNKNOWN, record["status"].status
assert record["url_user"] == "https://alice..empretienda.com.ar"
print("L10_SHERLOCK_2970_OK")
"""

def _run(workspace: pathlib.Path, argv: list[str], authority: pathlib.Path | None = None) -> int:
    command = [
        "docker", "run", "--rm",
        "--network", "none",
        "--memory", "2g", "--cpus", "2", "--pids-limit", "512",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{workspace.resolve()}:/workspace:ro",
        "-w", "/workspace",
    ]
    if authority is not None:
        command += ["-v", f"{authority.resolve()}:/authority:ro"]
    command += [IMAGE_ID, *argv]
    completed = subprocess.run(command, check=False)
    return completed.returncode

def regression(workspace: pathlib.Path) -> int:
    # V2 instrument-only correction: upstream tests expect an installed
    # `sherlock` console script. Provide an equivalent ephemeral shim in /tmp
    # without modifying the candidate workspace or fetching dependencies.
    script = (
        "set -eu; "
        "mkdir -p /tmp/l10bin; "
        "printf '#!/bin/sh\\nexec python -m sherlock_project \"$@\"\\n' "
        "> /tmp/l10bin/sherlock; "
        "chmod +x /tmp/l10bin/sherlock; "
        "PATH=/tmp/l10bin:$PATH "
        "python -m pytest -q "
        "-m 'not online and not validate_targets' "
        "-p no:cacheprovider"
    )
    return _run(workspace, ["sh", "-lc", script])

def objective(workspace: pathlib.Path) -> int:
    with tempfile.TemporaryDirectory(prefix="l10-sherlock-2970-") as raw:
        authority = pathlib.Path(raw)
        (authority / "objective.py").write_text(OBJECTIVE, encoding="utf-8")
        return _run(
            workspace,
            [
                "python", "-I", "-c",
                "import runpy,sys;sys.path.insert(0,'/workspace');"
                "runpy.run_path('/authority/objective.py',run_name='__main__')",
            ],
            authority,
        )

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("regression", "objective"))
    parser.add_argument("workspace", type=pathlib.Path)
    args = parser.parse_args()
    return regression(args.workspace) if args.mode == "regression" else objective(args.workspace)

if __name__ == "__main__":
    raise SystemExit(main())
