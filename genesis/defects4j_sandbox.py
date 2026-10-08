"""Defects4J behind a container boundary with no network.

Validating a repair candidate means compiling it and running the project test suite, so the
candidate is untrusted code that executes. Until now ``defects4j compile`` and ``defects4j test``
ran directly on the host, as the operator's own user, with the network up. This module is the only
place that should start them from now on.

Every command runs in a fresh container that has:

* no network (``--network none``);
* a read-only root filesystem, with the benchmark baked into the image;
* one writable bind mount, the caller's workspace, and a size-capped ``/tmp``;
* no Linux capability, no privilege escalation, an unprivileged uid;
* a memory, CPU, process-count and wall-clock ceiling.

The boundary is the container runtime's, not this module's: a kernel or runtime escape is out of
scope, and :func:`Defects4JSandbox.probe` reports what was actually enforced rather than what was
requested. Results never claim more isolation than the probe observed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import subprocess
import time
from typing import Sequence

from genesis.trust_root import digest_of

IMAGE = "genesis-defects4j:8c16da8"
DEFECTS4J_REVISION = "8c16da8230843cdc918eaf4ddb449637f02b83c6"
RESULT_SCHEMA = "genesis-defects4j-sandbox-run-v1"
PROBE_SCHEMA = "genesis-defects4j-sandbox-probe-v1"

_WORK = PurePosixPath("/work")
_PROJECT = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_TEST_NAME = re.compile(r"^[A-Za-z_][\w.$]*(::[A-Za-z_][\w$]*)?$")
_FAILING = re.compile(r"^---\s+(\S+)\s*$", re.MULTILINE)

# Each probe line is `name=value`. The script only reports; the verdict is computed by the host.
_PROBE_SCRIPT = r"""
echo "uid=$(id -u)"
if touch /defects4j/.probe 2>/dev/null; then echo "root_writable=yes"; else echo "root_writable=no"; fi
if touch /work/.probe 2>/dev/null; then rm -f /work/.probe; echo "work_writable=yes"; else echo "work_writable=no"; fi
echo "interfaces=$(ls /sys/class/net | tr '\n' ',')"
if timeout 5 curl -s -o /dev/null --connect-timeout 3 https://1.1.1.1 2>/dev/null; then echo "network=yes"; else echo "network=no"; fi
if timeout 5 getent hosts github.com >/dev/null 2>&1; then echo "dns=yes"; else echo "dns=no"; fi
echo "capabilities=$(grep CapEff /proc/self/status | awk '{print $2}')"
echo "no_new_privs=$(grep NoNewPrivs /proc/self/status | awk '{print $2}')"
echo "revision=$(cat /defects4j/REVISION 2>/dev/null)"
"""


class Defects4JSandboxError(RuntimeError):
    """Raised when a request cannot be expressed inside the boundary."""


@dataclass(frozen=True)
class SandboxLimits:
    """Ceilings applied to every container. Defaults suit one validation on a shared host."""

    memory_megabytes: int = 4096
    cpus: float = 2.0
    processes: int = 512
    tmp_megabytes: int = 2048
    timeout_seconds: int = 1800


@dataclass(frozen=True)
class SandboxRun:
    """What one container did. ``output`` is stdout and stderr, interleaved."""

    command: tuple[str, ...]
    returncode: int | None
    output: str
    timed_out: bool
    seconds: float
    image: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def record(self) -> dict:
        """A JSON-ready, digest-sealed account of the run for an evidence file."""
        body = {
            "schema": RESULT_SCHEMA,
            "command": list(self.command),
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "seconds": round(self.seconds, 3),
            "image": self.image,
            "output_sha256": digest_of(self.output),
        }
        return {**body, "run_digest": digest_of(body)}


@dataclass(frozen=True)
class Defects4JSandbox:
    """Runs Defects4J commands against checkouts that live under one host workspace."""

    workspace: Path
    image: str = IMAGE
    limits: SandboxLimits = field(default_factory=SandboxLimits)
    docker: str = "docker"

    def __post_init__(self) -> None:
        workspace = Path(self.workspace).resolve()
        if not workspace.is_dir():
            raise Defects4JSandboxError(f"workspace {workspace} is not an existing directory")
        if workspace == Path(workspace.anchor) or workspace == Path.home():
            raise Defects4JSandboxError("refusing to expose the filesystem root or the home directory")
        object.__setattr__(self, "workspace", workspace)

    # -- command construction -------------------------------------------------------------

    def container_command(self, arguments: Sequence[str], *, name: str) -> list[str]:
        """The exact ``docker run`` argv for ``arguments``. Pure, so the flags can be tested."""
        limits = self.limits
        memory = f"{limits.memory_megabytes}m"
        return [
            self.docker, "run", "--rm", "--name", name,
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--pids-limit", str(limits.processes),
            "--memory", memory, "--memory-swap", memory,
            "--cpus", str(limits.cpus),
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--tmpfs", f"/tmp:rw,exec,nosuid,nodev,size={limits.tmp_megabytes}m",
            "--env", "HOME=/tmp",
            "--env", "TZ=America/Los_Angeles",
            "--mount", f"type=bind,source={self.workspace},target={_WORK}",
            "--workdir", str(_WORK),
            self.image,
            *arguments,
        ]

    def _inside(self, directory: str) -> str:
        """Map a workspace-relative directory to its path in the container, or refuse."""
        parts = PurePosixPath(directory).parts
        if not parts or PurePosixPath(directory).is_absolute():
            raise Defects4JSandboxError(f"{directory!r} must be a path relative to the workspace")
        if any(not _SEGMENT.match(part) for part in parts):
            raise Defects4JSandboxError(f"{directory!r} leaves the workspace or is not a plain name")
        return str(_WORK.joinpath(*parts))

    # -- execution ------------------------------------------------------------------------

    def execute(self, arguments: Sequence[str], *, timeout_seconds: int | None = None) -> SandboxRun:
        """Run one argv in a fresh container and wait for it, killing it at the deadline."""
        if not arguments or any(not isinstance(item, str) or "\x00" in item for item in arguments):
            raise Defects4JSandboxError("arguments must be a non-empty list of strings")
        deadline = self.limits.timeout_seconds if timeout_seconds is None else timeout_seconds
        name = f"genesis-d4j-{secrets.token_hex(8)}"
        command = self.container_command(arguments, name=name)
        started = time.monotonic()
        timed_out = False
        try:
            finished = subprocess.run(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, errors="replace", timeout=deadline, check=False,
            )
            returncode, output = finished.returncode, finished.stdout
        except subprocess.TimeoutExpired as expired:
            # Killing the `docker run` client does not stop the container; kill it by name.
            timed_out = True
            subprocess.run(
                [self.docker, "kill", name], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
            )
            partial = expired.stdout or ""
            returncode, output = None, partial if isinstance(partial, str) else partial.decode(errors="replace")
        return SandboxRun(
            command=tuple(arguments), returncode=returncode, output=output, timed_out=timed_out,
            seconds=time.monotonic() - started, image=self.image,
        )

    def defects4j(self, *arguments: str, timeout_seconds: int | None = None) -> SandboxRun:
        return self.execute(["defects4j", *arguments], timeout_seconds=timeout_seconds)

    # -- Defects4J verbs ------------------------------------------------------------------

    def checkout(self, project: str, bug_id: int, version: str, directory: str) -> SandboxRun:
        """Check out the buggy (``b``) or fixed (``f``) version of one bug into ``directory``."""
        if not _PROJECT.match(project):
            raise Defects4JSandboxError(f"{project!r} is not a Defects4J project identifier")
        if not isinstance(bug_id, int) or isinstance(bug_id, bool) or bug_id < 1:
            raise Defects4JSandboxError("bug_id must be a positive integer")
        if version not in ("b", "f"):
            raise Defects4JSandboxError("version must be 'b' (buggy) or 'f' (fixed)")
        return self.defects4j("checkout", "-p", project, "-v", f"{bug_id}{version}", "-w", self._inside(directory))

    def compile(self, directory: str) -> SandboxRun:
        return self.defects4j("compile", "-w", self._inside(directory))

    def test(self, directory: str, *, single_test: str | None = None, relevant_only: bool = False) -> SandboxRun:
        """Run the developer test suite, or one test, or only the tests relevant to the bug."""
        arguments = ["test", "-w", self._inside(directory)]
        if single_test is not None:
            if not _TEST_NAME.match(single_test):
                raise Defects4JSandboxError(f"{single_test!r} is not a test class or class::method")
            arguments += ["-t", single_test]
        if relevant_only:
            arguments.append("-r")
        return self.defects4j(*arguments)

    def export(self, directory: str, prop: str) -> SandboxRun:
        """Read one Defects4J property of a checkout; ``output`` is the bare value."""
        if not re.fullmatch(r"[a-z.]+", prop):
            raise Defects4JSandboxError(f"{prop!r} is not a Defects4J property name")
        # Defects4J prints progress on stderr and the value on stdout without a newline; merged,
        # the two interleave into one unusable line. Only the value is wanted here.
        return self.execute([
            "sh", "-c", 'exec defects4j export -p "$1" -w "$2" 2>/dev/null', "export", prop, self._inside(directory),
        ])

    def failing_tests(self, directory: str) -> list[str]:
        """Tests the last ``test`` run left in ``failing_tests``, read without following links.

        The file is written by code that ran in the container, so it is untrusted: a symbolic link
        there must not make the host read some other file.
        """
        self._inside(directory)
        path = self.workspace / directory / "failing_tests"
        if path.is_symlink() or not path.is_file():
            raise Defects4JSandboxError(f"{directory}/failing_tests is missing or is not a regular file")
        return _FAILING.findall(path.read_text(encoding="utf-8", errors="replace")[:2_000_000])

    # -- self-check -----------------------------------------------------------------------

    def probe(self) -> dict:
        """Observe the boundary from inside a container and say whether it holds."""
        run = self.execute(["sh", "-c", _PROBE_SCRIPT], timeout_seconds=60)
        observed = dict(line.split("=", 1) for line in run.output.splitlines() if "=" in line)
        interfaces = [name for name in observed.get("interfaces", "").split(",") if name]
        checks = {
            "container_started": run.ok,
            "no_network_interface_but_loopback": interfaces == ["lo"],
            "no_outbound_connection": observed.get("network") == "no",
            "no_name_resolution": observed.get("dns") == "no",
            "root_filesystem_read_only": observed.get("root_writable") == "no",
            "workspace_writable": observed.get("work_writable") == "yes",
            "unprivileged_uid": observed.get("uid") not in (None, "", "0"),
            "no_capability": observed.get("capabilities", "").strip("0") == "" and "capabilities" in observed,
            "no_new_privileges": observed.get("no_new_privs") == "1",
            "pinned_benchmark_revision": observed.get("revision") == DEFECTS4J_REVISION,
        }
        body = {
            "schema": PROBE_SCHEMA,
            "image": self.image,
            "observed": observed,
            "checks": checks,
            "isolated": all(checks.values()),
        }
        return {**body, "probe_digest": digest_of(body)}
