# Defects4J validation boundary

Validating a repair candidate means compiling it and running a project's test suite. The candidate
is therefore code that executes, and it must be treated as untrusted. `genesis/defects4j_sandbox.py`
is the only supported way to run Defects4J from Genesis.

## What the boundary is

Each Defects4J command runs in its own container, removed when it exits:

| Property | How it is enforced |
| --- | --- |
| No network | `--network none`: the container has a loopback interface and nothing else |
| Benchmark cannot be altered | `--read-only` root filesystem; Defects4J is baked into the image |
| One writable host path | the caller's workspace, bind-mounted at `/work`; `/tmp` is a size-capped tmpfs |
| No privilege | `--cap-drop ALL`, `no-new-privileges`, the operator's own non-root uid |
| Bounded resources | memory (swap disabled), CPU share, process count, wall-clock deadline |

Directories are named relative to the workspace and are refused if they are absolute, contain `..`
or are not plain names. `failing_tests` is written by code that ran in the container; the host reads
it only when it is a regular file, never through a symbolic link.

## What the boundary is not

The isolation is the container runtime's. A kernel or runtime escape is out of scope, and the
default runtime shares the host kernel. Treat the boundary as protection against a candidate that
misbehaves, not against an adversary with a container-escape exploit.

## Building the image

```
docker build -t genesis-defects4j:8c16da8 deploy/defects4j
```

The build needs network access once, to fetch Defects4J at the pinned revision
`8c16da8230843cdc918eaf4ddb449637f02b83c6` and the project repositories its `init.sh` downloads.
Containers never have it.

## Checking it

```
python scripts/check_defects4j_sandbox.py --smoke
```

prints the sealed probe (what the container could and could not do) and, with `--smoke`, checks out
the buggy version of Lang-1, compiles it, runs its relevant tests and verifies that exactly the
recorded triggering test fails. The command exits non-zero if any isolation check fails.

## Use

```python
from pathlib import Path
from genesis.defects4j_sandbox import Defects4JSandbox

sandbox = Defects4JSandbox(Path("/srv/genesis/trial-17"))
assert sandbox.probe()["isolated"]
sandbox.checkout("Lang", 1, "b", "lang-1b")
compiled = sandbox.compile("lang-1b")
tested = sandbox.test("lang-1b")
failing = sandbox.failing_tests("lang-1b")
evidence = [compiled.record(), tested.record()]
```

A study that reports results obtained through the boundary should store the probe next to them.

## Status

The G11 and V2.1 study scripts predate this module and call a host installation by absolute path.
They have not been ported, and no recorded result was produced through this boundary.
