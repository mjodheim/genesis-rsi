"""The Defects4J boundary: what it asks the runtime for, what it refuses, and what it observes."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess

import pytest

from genesis.defects4j_sandbox import (
    DEFECTS4J_REVISION, IMAGE, Defects4JSandbox, Defects4JSandboxError, SandboxLimits,
)


def _fake_docker(tmp_path: Path, body: str) -> str:
    """A stand-in runtime that records its argv, so the boundary is testable without Docker."""
    path = tmp_path / "docker"
    path.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$@\" >> '{tmp_path}/argv'\n{body}\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def _workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace


def test_every_container_is_started_without_network_privilege_or_writable_root(tmp_path) -> None:
    sandbox = Defects4JSandbox(_workspace(tmp_path), limits=SandboxLimits(memory_megabytes=1024, cpus=1.5, processes=64))
    command = sandbox.container_command(["defects4j", "info", "-p", "Lang"], name="probe")

    def value_after(flag: str) -> str:
        return command[command.index(flag) + 1]

    assert value_after("--network") == "none"
    assert "--read-only" in command
    assert value_after("--cap-drop") == "ALL"
    assert value_after("--security-opt") == "no-new-privileges"
    assert value_after("--user") == f"{os.getuid()}:{os.getgid()}"
    assert value_after("--memory") == value_after("--memory-swap") == "1024m"
    assert value_after("--cpus") == "1.5"
    assert value_after("--pids-limit") == "64"
    assert "--privileged" not in command
    assert command[-5:] == [IMAGE, "defects4j", "info", "-p", "Lang"]


def test_the_workspace_is_the_only_host_path_exposed(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    command = Defects4JSandbox(workspace).container_command(["true"], name="probe")
    mounts = [command[index + 1] for index, item in enumerate(command) if item in ("--mount", "--volume", "-v")]
    assert mounts == [f"type=bind,source={workspace.resolve()},target=/work"]
    assert "docker.sock" not in " ".join(command)


@pytest.mark.parametrize("directory", ["/etc", "../outside", "a/../../b", "", "a b", "-w", ".hidden"])
def test_a_directory_that_leaves_the_workspace_is_refused(tmp_path, directory) -> None:
    sandbox = Defects4JSandbox(_workspace(tmp_path), docker=_fake_docker(tmp_path, "exit 0"))
    with pytest.raises(Defects4JSandboxError):
        sandbox.compile(directory)
    assert not (tmp_path / "argv").exists(), "a refused request must not reach the runtime"


def test_the_home_directory_and_filesystem_root_are_never_a_workspace(tmp_path) -> None:
    for forbidden in (Path("/"), Path.home()):
        with pytest.raises(Defects4JSandboxError):
            Defects4JSandbox(forbidden)
    with pytest.raises(Defects4JSandboxError):
        Defects4JSandbox(tmp_path / "missing")


@pytest.mark.parametrize(
    "arguments",
    [("Lang;id", 1, "b"), ("Lang", 0, "b"), ("Lang", True, "b"), ("Lang", 1, "x"), ("Lang", "1", "b")],
)
def test_checkout_rejects_anything_but_a_project_a_bug_number_and_a_side(tmp_path, arguments) -> None:
    sandbox = Defects4JSandbox(_workspace(tmp_path), docker=_fake_docker(tmp_path, "exit 0"))
    with pytest.raises(Defects4JSandboxError):
        sandbox.checkout(*arguments, "case")


def test_verbs_translate_to_defects4j_commands_on_container_paths(tmp_path) -> None:
    sandbox = Defects4JSandbox(_workspace(tmp_path), docker=_fake_docker(tmp_path, "echo done"))
    assert sandbox.checkout("Lang", 12, "b", "lang-12/buggy").command == (
        "defects4j", "checkout", "-p", "Lang", "-v", "12b", "-w", "/work/lang-12/buggy")
    assert sandbox.compile("case").command == ("defects4j", "compile", "-w", "/work/case")
    assert sandbox.test("case", single_test="org.x.FooTest::testBar", relevant_only=True).command == (
        "defects4j", "test", "-w", "/work/case", "-t", "org.x.FooTest::testBar", "-r")
    assert sandbox.export("case", "cp.test").command[-3:] == ("export", "cp.test", "/work/case")
    with pytest.raises(Defects4JSandboxError):
        sandbox.test("case", single_test="Foo; rm -rf /")


def test_a_run_reports_exit_status_and_output_and_seals_its_record(tmp_path) -> None:
    sandbox = Defects4JSandbox(_workspace(tmp_path), docker=_fake_docker(tmp_path, "echo compiled; exit 3"))
    run = sandbox.compile("case")
    assert (run.returncode, run.timed_out, run.ok) == (3, False, False)
    assert "compiled" in run.output
    record = run.record()
    assert record["returncode"] == 3 and len(record["run_digest"]) == 64
    assert "output" not in record, "the record carries a digest of the output, not megabytes of log"


def test_a_run_past_its_deadline_is_killed_by_container_name(tmp_path) -> None:
    body = 'case "$1" in run) exec sleep 30;; esac'
    sandbox = Defects4JSandbox(_workspace(tmp_path), docker=_fake_docker(tmp_path, body))
    run = sandbox.execute(["sleep", "30"], timeout_seconds=1)
    assert run.timed_out and run.returncode is None and not run.ok
    argv = (tmp_path / "argv").read_text(encoding="utf-8").split("\n")
    name = argv[argv.index("--name") + 1]
    assert name.startswith("genesis-d4j-")
    assert argv[argv.index("kill") + 1] == name


def test_failing_tests_are_read_from_a_regular_file_only(tmp_path) -> None:
    workspace = _workspace(tmp_path)
    sandbox = Defects4JSandbox(workspace)
    case = workspace / "case"
    case.mkdir()
    (case / "failing_tests").write_text(
        "--- org.x.FooTest::testBar\njunit.framework.AssertionFailedError\n\tat org.x.FooTest.testBar\n"
        "--- org.x.BazTest::testQux\n", encoding="utf-8")
    assert sandbox.failing_tests("case") == ["org.x.FooTest::testBar", "org.x.BazTest::testQux"]

    secret = tmp_path / "secret"
    secret.write_text("--- host.Secret::leaked\n", encoding="utf-8")
    (case / "failing_tests").unlink()
    (case / "failing_tests").symlink_to(secret)
    with pytest.raises(Defects4JSandboxError):
        sandbox.failing_tests("case")


def test_the_probe_verdict_is_computed_from_what_the_container_reports(tmp_path) -> None:
    healthy = "\n".join([
        "uid=1000", "root_writable=no", "work_writable=yes", "interfaces=lo,", "network=no", "dns=no",
        "capabilities=0000000000000000", "no_new_privs=1", f"revision={DEFECTS4J_REVISION}",
    ])
    for report, expected, broken in [
        (healthy, True, None),
        (healthy.replace("interfaces=lo,", "interfaces=eth0,lo,"), False, "no_network_interface_but_loopback"),
        (healthy.replace("network=no", "network=yes"), False, "no_outbound_connection"),
        (healthy.replace("uid=1000", "uid=0"), False, "unprivileged_uid"),
        (healthy.replace("root_writable=no", "root_writable=yes"), False, "root_filesystem_read_only"),
        (healthy.replace("0000000000000000", "00000000a80425fb"), False, "no_capability"),
        ("", False, "container_started"),
    ]:
        root = tmp_path / str(abs(hash(report)))
        root.mkdir()
        body = f"cat <<'REPORT'\n{report}\nREPORT\n" + ("exit 0" if report else "exit 125")
        probe = Defects4JSandbox(_workspace(root), docker=_fake_docker(root, body)).probe()
        assert probe["isolated"] is expected
        if broken:
            assert probe["checks"][broken] is False


def _image_available() -> bool:
    if shutil.which("docker") is None:
        return False
    inspected = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    return inspected.returncode == 0


@pytest.mark.skipif(not _image_available(), reason=f"requires the {IMAGE} image (deploy/defects4j)")
def test_the_real_boundary_holds_and_reproduces_a_known_bug(tmp_path) -> None:
    """End to end against the real runtime: isolation observed, then Lang-1 fails exactly its trigger."""
    sandbox = Defects4JSandbox(_workspace(tmp_path))
    probe = sandbox.probe()
    assert probe["isolated"], probe["checks"]

    assert sandbox.checkout("Lang", 1, "b", "lang-1b").ok
    assert sandbox.compile("lang-1b").ok
    tested = sandbox.test("lang-1b", relevant_only=True)
    assert tested.ok, tested.output[-2000:]
    assert sandbox.failing_tests("lang-1b") == ["org.apache.commons.lang3.math.NumberUtilsTest::TestLang747"]
    assert sandbox.export("lang-1b", "dir.src.classes").output == "src/main/java"
    owners = {path.stat().st_uid for path in (tmp_path / "workspace").rglob("*")}
    assert owners == {os.getuid()}, "the container must not leave files the operator cannot delete"
