# T1 execution incident — 8 October 2026

Status: infrastructure interruption, no sealed trial result and no repair verdict.

The existing preregistration at `01b42ba7` was executed without changing the
proposer, validator, case list or budgets:

```sh
.venv/bin/python scripts/run_repair_bench_trial.py run --name T1 \
  --workspace /home/anthony/genesis-bench/T1 --parallel 2
```

The container probe passed all ten checks. The runner reported:

```text
Cli-8 ABORTED: a model call failed
Math-97 ABORTED: a model call failed
```

It then started checking out Math-39 and Gson-10. The operator stopped the
runner with SIGTERM before allowing the same access failure to propagate
through all 24 cases. These four buggy-side checkout directories exist in the
workspace; no fixed revision was opened and no result or partial JSONL file
was present when the runner stopped. Completed per-arm outcomes, original
model failure bodies and total trial model cost are not recoverable from the
runner's output. No success or zero-cost claim is made for those attempts.

A separate content-free access diagnostic using the preregistered model
returned exit code 1, `terminal_reason=api_error`, HTTP status 429 and
`api_error=usage_limit_reached`. The provider announced reset at 00:40 in
Europe/Brussels. That diagnostic recorded zero input/output tokens and zero
cost; those figures describe only the diagnostic, not the earlier trial calls.

## Resume boundary

The existing runner documents resumption with the same command. All 24 cases
remain consumed by T1's preregistration, even though this execution did not
finish. Resume only after model access works, with the same model and frozen
machinery. Do not substitute another proposer/model and present it as T1.
Preserve this incident with any later result. Do not inspect the fixed revisions
until the trial result is sealed.

The runner drops an aborted case's in-memory call and validation records. A
future trial apparatus should durably retain every attempted call, validation
and cost before proceeding, and validate resume records against the frozen
preregistration. That is an identified apparatus limitation, not a retrospective
change to T1 or a claim that interrupted executions spent no resources.

## Verification before execution

- Repair-bench and sandbox tests: 36 passed, 1 skipped.
- Focused G9/G10, operator-lab, retained-selection and trial-integrity tests:
  23 passed, 3 subtests passed.
- Repository integrity script: passed.

An additional full-suite run was interrupted after 3,100 passed and 8 skipped
in 495.55 seconds, with no reported test failure. It is not a full-suite pass.
The suite modified tracked legacy files under
`experiments/GENESIS/runtime_state`; after all workers exited, the generated
state was retained at `/tmp/genesis-tests-runtime-state-20261008` and the
tracked state restored byte-for-byte from the starting HEAD. Future full-suite
runs should use an isolated checkout to prevent this test side effect from
altering the working repository's runtime state.

This incident report and the navigation update were written with OpenAI Codex
assistance. They introduce no new repair mechanism or scientific acceptance rule.
