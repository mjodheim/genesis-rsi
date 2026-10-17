# Prevent regression tests from modifying the working research archive

**Engineering observation, 17 October 2026.** A direct invocation of the
repository-wide pytest suite on an otherwise clean, temporary Genesis review
checkout ran 986 passing tests (1 skipped, 2 xfailed) before it was
intentionally interrupted because the full suite would take substantially
longer. During that run, the tests had generated or modified 22 paths
under experiments/GENESIS/runtime_state, including tracked runtime
checkpoint and state files.

The generated test artifacts were backed up outside the repository before
the test checkout was restored to its exact original Git state. This report
does not classify the generated data as a new scientific result.

## Mitigation

The new scripts/run_pytest_isolated.sh helper creates a disposable detached
Git worktree of the source HEAD, executes pytest there with the isolated source
first on PYTHONPATH, reports the number of dirty paths caused by the tests,
and removes the disposable worktree using an exit trap.

Example usage:

    GENESIS_TEST_PYTHON=/path/to/project/python bash scripts/run_pytest_isolated.sh --timeout 300 tests/test_circuit_engine.py

No existing research checkout is cleaned by this script. It refuses to
start if the caller has uncommitted modifications, to avoid inadvertently
testing the wrong source. It is a precaution for developer workstations and
shared VPS checkouts, not an independent validation engine or a substitute
for the official GitHub checks.

## Verification

- Bash syntax check passed.
- Targeted smoke test: 6 passed; zero generated or modified paths reported.
- The caller's worktree stayed clean.
- Disposable test worktree removed automatically.
- This helper does not change frozen protocols, result files, or commit
  citations.

**Still to investigate:** find and isolate the specific test fixtures that
write to tracked runtime_state; the wrapper contains, rather than fixes,
that underlying test side effect.
